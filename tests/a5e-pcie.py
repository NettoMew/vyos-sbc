#!/usr/bin/env python3
"""A5E PCIe contract; optionally audit both compiled DTBs and kernel config."""
import argparse
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KP = ROOT / "boards/a5e/overlay/scripts/package-build/linux-kernel/patches/kernel"
UP = ROOT / "boards/a5e/uboot/patches/always/0050-a5e-linux-pcie-description.patch"
CONFIG = ROOT / "overlay/scripts/package-build/linux-kernel/config/74-allwinner-sun55i.config"
REQUIRED = ("PCI", "PCI_MSI", "PCIE_SUN55I_RC", "AW_INNO_COMBOPHY", "BLK_DEV_NVME")
UBOOT_REQUIRED = ("PCI", "NVME", "NVME_PCI", "CMD_NVME", "PCIE_SUN55I_RC",
                  "PHY_SUN55I_PCIE_USB3", "DM_REGULATOR_FIXED", "SPL_SPI_SUNXI",
                  "MTD", "DM_SPI_FLASH", "SPI_SUNXI", "SPI_FLASH_WINBOND", "CMD_SF",
                  "CMD_CACHE", "CMD_REGULATOR", "CMD_PMIC")


def read_fdt(path):
    """Read flattened DT properties without relying on host fdtget packaging."""
    data = path.read_bytes()
    magic, total, pos, strings = struct.unpack_from('>4I', data)
    assert magic == 0xd00dfeed and total <= len(data), 'invalid FDT header'
    string_size, structure_size = struct.unpack_from('>2I', data, 32)
    end = pos + structure_size
    assert end <= total and strings + string_size <= total
    nodes, stack = {}, []
    while pos < end:
        tag = struct.unpack_from('>I', data, pos)[0]
        pos += 4
        if tag == 1:
            nul = data.index(b'\0', pos, end)
            stack.append(data[pos:nul].decode())
            nodes['/' + '/'.join(stack[1:])] = {}
            pos = (nul + 4) & ~3
        elif tag == 2:
            stack.pop()
        elif tag == 3:
            length, name = struct.unpack_from('>2I', data, pos)
            pos += 8
            assert name < string_size and pos + length <= end
            nul = data.index(b'\0', strings + name, strings + string_size)
            key = data[strings + name:nul].decode()
            nodes['/' + '/'.join(stack[1:])][key] = data[pos:pos + length]
            pos = (pos + length + 3) & ~3
        elif tag == 4:
            continue
        elif tag == 9:
            assert not stack
            return nodes
        else:
            raise AssertionError(f'invalid FDT tag {tag}')
    raise AssertionError('missing FDT end tag')


class SourceContract(unittest.TestCase):
    def test_fdt_reader_checks_structure(self):
        words = lambda *values: struct.pack('>' + 'I' * len(values), *values)
        block = words(1) + b'\0\0\0\0' + words(3, 4, 0) + words(180) + words(2, 9)
        names = b'clock\0'
        header = words(0xd00dfeed, 56 + len(block) + len(names), 56,
                       56 + len(block), 40, 17, 16, 0, len(names), len(block))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.dtb'
            path.write_bytes(header + bytes(16) + block + names)
            self.assertEqual(read_fdt(path), {'/': {'clock': words(180)}})
            bad = bytearray(path.read_bytes())
            bad[0] = 0
            path.write_bytes(bad)
            with self.assertRaises(AssertionError):
                read_fdt(path)

    def test_required_drivers_enabled(self):
        for name in REQUIRED:
            self.assertIn(f"CONFIG_{name}=y", CONFIG.read_text().splitlines())

    def test_firmware_and_kernel_descriptions_match(self):
        def added_nodes(path):
            return [line for line in path.read_text().splitlines()
                    if line.startswith('+') and not line.startswith(('+++', '+#'))]
        self.assertEqual(added_nodes(KP / "173-arm64-dts-a5e-pcie.patch"), added_nodes(UP))

    def test_firmware_tree_not_bypassed(self):
        self.assertIn('BOARD_DTB_OVERRIDE="0"', (ROOT / "boards/a5e/board.conf").read_text())

    def test_correct_linux_binding_and_no_duplicate_power_pin(self):
        for path in (UP, KP / "173-arm64-dts-a5e-pcie.patch"):
            text = path.read_text()
            self.assertIn('compatible = "allwinner,sunxi-pcie-v210-rc"', text)
            self.assertIn('pcie3v3-supply = <&reg_pcie_vcc3v3>', text)
            self.assertIn('"msi", "sii"', text)
            self.assertNotIn('pcie_pwren_pins', text)
            self.assertNotIn('allwinner,sun55i-pcie-v210-rc', text)

    def test_probe_dependencies_and_wake_direction(self):
        text = (KP / "174-pci-sun55i-probe-safety.patch").read_text()
        self.assertIn('"wake", GPIOD_IN', text)
        self.assertIn('PTR_ERR(pci->pcie3v3) != -ENODEV', text)
        self.assertIn('return dev_err_probe', text)

    def test_nvme_firmware_handoff_and_binding(self):
        text = (UP.parent / '0070-a5e-nvme-boot-and-handoff.patch').read_text()
        self.assertIn('+\t\t.compatible = "allwinner,sunxi-pcie-v210-rc"', text)
        self.assertIn('GPIOD_IS_IN', text)
        self.assertIn('+\t.remove\t= nvme_pci_remove,', text)
        self.assertIn('+\t.flags\t= DM_FLAG_OS_PREPARE,', text)
        self.assertIn('+\t.remove\t\t\t= sun55i_pcie_remove,', text)
        self.assertIn('+\t\tgoto free_prp_pool;', text)
        self.assertIn('PCI_COMMAND_MASTER, 0', text)
        fence = (UP.parent / '0071-nvme-failed-probe-dma-fence.patch').read_text()
        self.assertIn('+\tndev->stop_dma = nvme_pci_stop_dma;', fence)
        self.assertIn('+\t\tndev->stop_dma(udev);\n \tfree((void *)ndev->prp_pool);', fence)
        cold = (UP.parent / '0072-a5e-cold-boot-lane-and-nvme-timeout.patch').read_text()
        self.assertIn('"lane-select-supply"', cold)
        self.assertIn('"lane-enable-supply"', cold)
        self.assertIn('nvmeq->dev->stop_dma(nvmeq->dev->udev)', cold)

    def test_sd_rescue_and_nvme_boot_target(self):
        text = (UP.parent / '0065-sunxi-nvme-boot-target.patch').read_text()
        self.assertIn('func(NVME, nvme, 0)', text)
        self.assertNotIn('-\tBOOT_TARGET_DEVICES_MMC(func)', text)
        order = (UP.parent / '0073-a5e-spi-power-and-boot-order.patch').read_text()
        self.assertIn(' \tBOOT_TARGET_DEVICES_MMC(func) \\\n+\tBOOT_TARGET_DEVICES_NVME(func)', order)
        self.assertNotIn('-\tBOOT_TARGET_DEVICES_MMC(func)', order)

    def test_spi_boot_supply_retained_in_both_trees(self):
        firmware = (UP.parent / '0073-a5e-spi-power-and-boot-order.patch').read_text()
        kernel = (KP / '175-arm64-dts-a5e-spi-boot-power.patch').read_text()
        for text in (firmware, kernel):
            self.assertIn('regulator-always-on;', text)
            self.assertIn('regulator-boot-on;', text)
            self.assertIn('reg_cldo1', text)
        self.assertIn('pmic_bus_write(0x9b,', firmware)
        self.assertIn('(reg_val & ~0x1f) | 0x0d', firmware)
        self.assertIn('pmic_bus_write(0x91, reg_val | BIT(0))', firmware)

    def test_handoff_requires_live_link_not_sticky_status(self):
        for path in (KP / '176-pci-sun55i-live-link-state.patch',
                     UP.parent / '0074-a5e-live-pcie-link-state.patch'):
            text = path.read_text()
            self.assertIn('PCIE_LTSSM_CTRL) & PCIE_LINK_TRAINING', text)
            self.assertIn('PCI_EXP_LNKSTA_DLLLA', text)
        speed = (KP / '176-pci-sun55i-live-link-state.patch').read_text()
        self.assertIn('PCI_EXP_LNKSTA_CLS', speed)
        self.assertIn('+\treturn gen;', speed)

    def test_slot_power_and_reset_have_one_owner(self):
        kernel = (KP / '177-pci-a5e-slot-power-reset-sequence.patch').read_text()
        firmware = (UP.parent / '0075-a5e-owned-slot-power-sequence.patch').read_text()
        for text in (kernel, firmware):
            self.assertIn('-\t\tregulator-always-on;', text)
            self.assertIn('-\t\tregulator-boot-on;', text)
            self.assertIn('+\t\tstartup-delay-us = <100000>;', text)
            self.assertIn('+\t\toff-on-delay-us = <100000>;', text)
        self.assertIn('gpiod_direction_output_raw(pci->rst_gpio, 0)', kernel)
        self.assertIn('"reset", GPIOD_ASIS', kernel)
        self.assertIn('.shutdown = sunxi_pcie_plat_shutdown', kernel)
        self.assertIn('gpiod_set_raw_value_cansleep(pci->rst_gpio, 0)', kernel)
        self.assertIn('regulator_set_enable(pci->slot_3v3, false)', firmware)


def check_binaries(config, uboot_config, dtbs):
    for symbol in REQUIRED:
        assert f"CONFIG_{symbol}=y" in config.read_text().splitlines(), symbol
    for symbol in UBOOT_REQUIRED:
        assert f"CONFIG_{symbol}=y" in uboot_config.read_text().splitlines(), symbol
    snapshots = []
    for dtb in dtbs:
        nodes = read_fdt(dtb)
        # BROM reads the SPI flash before SPL can re-enable its supply.
        spi_rails = [props for name, props in nodes.items() if name.endswith('/cldo1')]
        assert len(spi_rails) == 1, 'missing/ambiguous SPI boot supply'
        rail = spi_rails[0]
        assert 'regulator-always-on' in rail and 'regulator-boot-on' in rail
        for prop in ('regulator-min-microvolt', 'regulator-max-microvolt'):
            assert rail[prop] == struct.pack('>I', 1800000), prop
        def get(node, prop, kind='s'):
            raw = nodes[node][prop]
            if kind == 's':
                return raw.rstrip(b'\0').decode().replace('\0', ' ')
            assert len(raw) % 4 == 0
            return struct.unpack('>' + 'I' * (len(raw) // 4), raw)
        def cells(node, prop):
            return list(get(node, prop, 'u'))
        handles = {cells(node, 'phandle')[0]: node for node in nodes if 'phandle' in nodes[node]}
        def references(node, prop, count_property):
            """Resolve mixed zero/one-cell clock specifiers, not raw phandle IDs."""
            values, result = cells(node, prop), []
            while values:
                provider = handles[values.pop(0)]
                count = cells(provider, count_property)[0]
                assert len(values) >= count, (node, prop, provider)
                result.append((provider, values[:count]))
                values = values[count:]
            return result
        pcie, phy = '/soc/pcie@4800000', '/soc/phy@4f00000'
        ccu, pio, rpio = '/soc/clock-controller@2001000', '/soc/pinctrl@2000000', '/soc/pinctrl@7022000'
        assert get(pcie, 'compatible') == 'allwinner,sunxi-pcie-v210-rc'
        assert get(pcie, 'status') == get(phy, 'status') == 'okay'
        assert get(phy, 'compatible') == 'allwinner,inno-combphy'
        assert cells(pcie, 'reg') == [0x4800000, 0x480000]
        assert cells(phy, 'reg') == [0x4f00000, 0x80000, 0x4f80000, 0x80000]
        assert cells(pcie, 'max-link-speed') == [2]
        assert cells(pcie, 'num-lanes') == [1]
        assert cells(phy, 'phy_use_sel') == cells(phy, 'phy_refclk_sel') == [0]
        assert references(pcie, 'phys', '#phy-cells') == [(phy, [2])]
        phy_clocks = references(phy, 'clocks', '#clock-cells')
        rc_clocks = references(pcie, 'clocks', '#clock-cells')
        resets = references(phy, 'resets', '#reset-cells')
        power = references(pcie, 'power-domains', '#power-domain-cells')
        assert phy_clocks == [(ccu, [180]), (ccu, [8])]
        assert rc_clocks == [('/osc24M-clk', []), (ccu, [135])]
        assert resets == [(ccu, [58])]
        assert power == [('/soc/power-controller@7060000', [7])]
        assert references(phy, 'power-domains', '#power-domain-cells') == power
        assert get(phy, 'clock-names') == 'phyclk_ref refclk_par'
        assert get(pcie, 'clock-names') == 'hosc pclk_aux'
        assert get(phy, 'reset-names') == 'phy_rst'
        assert cells(pcie, 'pcie3v3-supply') == cells('/regulator-pcie-vcc3v3', 'phandle')
        assert cells('/regulator-pcie-vcc3v3', 'gpio')[1:] == [0, 11, 0]
        assert cells('/gma340-pcie', 'gpio')[1:] == [1, 6, 0]
        assert cells('/gma340-oe', 'gpio')[1:] == [1, 7, 1]
        assert cells(pcie, 'reset-gpios')[1:] == [7, 11, 0]
        assert cells(pcie, 'wake-gpios')[1:] == [7, 12, 1]
        for node, prop, controller in (
            ('/regulator-pcie-vcc3v3', 'gpio', rpio),
            ('/gma340-pcie', 'gpio', pio), ('/gma340-oe', 'gpio', pio),
            (pcie, 'reset-gpios', pio), (pcie, 'wake-gpios', pio),
        ):
            assert handles[cells(node, prop)[0]] == controller
        props = nodes['/regulator-pcie-vcc3v3']
        assert 'pinctrl-0' not in props, 'duplicate PL11 owner'
        assert 'regulator-always-on' not in props, 'slot cannot be power cycled'
        assert 'regulator-boot-on' not in props, 'slot powers up before PERST owner'
        assert cells('/regulator-pcie-vcc3v3', 'startup-delay-us') == [100000]
        assert cells('/regulator-pcie-vcc3v3', 'off-on-delay-us') == [100000]
        irq = cells(pcie, 'interrupts')
        assert irq[:6] == [0, 107, 4, 0, 106, 4] and len(irq) == 30
        intc = pcie + '/legacy-interrupt-controller'
        assert 'interrupt-controller' in nodes[intc]
        assert cells(intc, '#address-cells') == [0]
        assert cells(intc, '#interrupt-cells') == [1]
        assert cells(pcie, 'interrupt-map-mask') == [0, 0, 0, 7]
        assert cells(pcie, 'interrupt-map') == [
            cell for pin in range(1, 5)
            for cell in [0, 0, 0, pin, cells(intc, 'phandle')[0], pin - 1]
        ]
        # Phandle numbers differ across trees, but all wiring must match.
        snapshots.append([cells(pcie,'ranges'), irq, get(pcie,'interrupt-names'),
                          phy_clocks, rc_clocks, resets, power])
    assert snapshots[0] == snapshots[1], 'kernel/firmware PCIe wiring drift'
    firmware = read_fdt(dtbs[1])
    assert firmware['/soc/spi@4025000']['status'] == b'okay\0'
    assert firmware['/soc/spi@4025000/flash@0']['compatible'] == b'jedec,spi-nor\0'
    for supply, regulator in [('lane-select-supply', '/gma340-pcie'),
                              ('lane-enable-supply', '/gma340-oe')]:
        assert firmware['/soc/pcie@4800000'][supply] == firmware[regulator]['phandle']
    print('A5E_PCIE_COMPILED_CONTRACT_PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-config', type=Path)
    parser.add_argument('--uboot-config', type=Path)
    parser.add_argument('--kernel-dtb', type=Path)
    parser.add_argument('--uboot-dtb', type=Path)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SourceContract))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if any(vars(args).values()):
        if not all(vars(args).values()):
            parser.error('compiled audit requires all four paths')
        check_binaries(args.kernel_config, args.uboot_config, [args.kernel_dtb, args.uboot_dtb])
