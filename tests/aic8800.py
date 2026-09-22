#!/usr/bin/env python3
"""AIC8800 integration contracts; optional audit of both compiled A5E DTBs."""
import argparse
from pathlib import Path
import runpy
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
KP = ROOT / 'boards/a5e/overlay/scripts/package-build/linux-kernel/patches/kernel'
UP = ROOT / 'boards/a5e/uboot/patches/always'
read_fdt = runpy.run_path(str(ROOT / 'tests/a5e-pcie.py'))['read_fdt']


class SourceContract(unittest.TestCase):
    def test_shared_patches_only_touch_sdio(self):
        patches = sorted((ROOT / 'vendor/aic8800').glob('*.patch'))
        self.assertEqual(len(patches), 3)
        for patch in patches:
            text = patch.read_text()
            paths = [line.split()[1] for line in text.splitlines()
                     if line.startswith(('--- a/', '+++ b/'))]
            self.assertTrue(paths, patch)
            self.assertTrue(all('/src/SDIO/' in p for p in paths), patch)

    def test_both_boards_use_shared_driver(self):
        for board in ('a5e', 'm28k'):
            text = (ROOT / f'boards/{board}/board.conf').read_text()
            self.assertIn('BOARD_WIFI_AIC8800="1"', text)
        text = (ROOT / 'boards/a5e/board.conf').read_text()
        self.assertIn('BOARD_AIC8800_FW_VARIANT="aic8800D80"', text)
        self.assertIn('BOARD_DTB_OVERRIDE="0"', text)

    def test_shared_then_optional_board_patches(self):
        text = (ROOT / 'lib/aic8800.sh').read_text()
        shared = text.index('${PROJECT_ROOT}/vendor/aic8800/')
        board = text.index('${BOARDS_DIR}/${BOARD}/aic8800/')
        self.assertLess(shared, board)

    def test_target_abi_and_sign_after_strip(self):
        text = (ROOT / 'lib/aic8800.sh').read_text()
        self.assertIn('include/config/kernel.release', text)
        self.assertIn('KERNELRELEASE="${krel}"', text)
        self.assertIn('modinfo -F vermagic', text)
        self.assertLess(text.index('strip --strip-debug'), text.index('scripts/sign-file'))
        self.assertIn('CONFIG_SDIO_BT=n', text)
        self.assertIn('certs/signing_key.x509', text)

    def test_cfg80211_regulatory_default(self):
        text = next((ROOT / 'vendor/aic8800').glob('0003-*.patch')).read_text()
        self.assertIn('+\tCOMMON_PARAM(custregd, false, false)', text)

    def test_firmware_and_autoload_are_board_assets(self):
        text = (ROOT / 'lib/aic8800.sh').read_text()
        self.assertIn('local inc="${BOARD_ASSETS_DIR}"', text)
        self.assertIn('BOARD_AIC8800_FW_VARIANT', text)
        self.assertIn("aic8800_bsp\\naic8800_fdrv\\n", text)
        self.assertNotIn('2>/dev/null || true', text)

    def test_kernel_and_firmware_patch_payloads_match(self):
        for kernel, firmware in [(178, '0076'), (179, '0077')]:
            k = next(KP.glob(f'{kernel}-*.patch')).read_text()
            u = next(UP.glob(f'{firmware}-*.patch')).read_text()
            u = u.replace('dts/upstream/src/arm64/allwinner/',
                          'arch/arm64/boot/dts/allwinner/')
            self.assertEqual(k, u)
            self.assertIn('0648ff3c4125d673c18b5f032dc7c28545c542b5', k)

    def test_ci_uses_capabilities_not_stale_board_allowlist(self):
        text = (ROOT / '.github/workflows/build.yml').read_text()
        self.assertNotIn('e20c|a5e)', text)
        self.assertIn('${BOARD_WIFI_AIC8800:-0}', text)
        self.assertIn('python3 tests/aic8800.py', text)


def check_dtb(path):
    nodes = read_fdt(path)
    def cells(node, prop):
        value = nodes[node][prop]
        assert len(value) % 4 == 0
        return list(struct.unpack('>' + 'I' * (len(value) // 4), value))
    handles = {cells(p, 'phandle')[0]: p for p in nodes if 'phandle' in nodes[p]}
    def ref(node, prop):
        values = cells(node, prop)
        return handles[values[0]], values[1:]
    mmc = '/soc/mmc@4021000'
    rpio = '/soc/pinctrl@7022000'
    assert nodes[mmc]['status'] == b'okay\0'
    assert cells(mmc, 'bus-width') == [4]
    assert cells(mmc, 'max-frequency') == [40000000]
    assert 'non-removable' in nodes[mmc]
    assert 'cap-sdio-irq' in nodes[mmc]
    assert ref(mmc, 'pinctrl-0') == ('/soc/pinctrl@2000000/mmc1-pins', [])
    supply, _ = ref(mmc, 'vmmc-supply')
    assert nodes[supply]['compatible'] == b'regulator-fixed\0'
    assert cells(supply, 'regulator-min-microvolt') == [3300000]
    assert cells(supply, 'regulator-max-microvolt') == [3300000]
    assert ref(supply, 'gpio') == (rpio, [0, 7, 0])
    assert 'enable-active-high' in nodes[supply]
    seq, _ = ref(mmc, 'mmc-pwrseq')
    assert nodes[seq]['compatible'] == b'mmc-pwrseq-simple\0'
    assert ref(seq, 'reset-gpios') == (rpio, [1, 1, 1])
    assert cells(seq, 'post-power-on-delay-ms') == [200]
    io, _ = ref(mmc, 'vqmmc-supply')
    assert io.endswith('/bldo1')
    assert cells(io, 'regulator-min-microvolt') == [1800000]
    assert cells(io, 'regulator-max-microvolt') == [1800000]
    assert 'regulator-always-on' in nodes[io]
    wifi = mmc + '/wifi@1'
    assert cells(wifi, 'reg') == [1]
    assert ref(wifi, 'interrupt-parent') == (rpio, [])
    assert cells(wifi, 'interrupts') == [1, 0, 8]
    assert nodes[wifi]['interrupt-names'] == b'host-wake\0'
    print(f'A5E_WIFI_COMPILED_CONTRACT_PASS {path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-dtb', type=Path)
    parser.add_argument('--uboot-dtb', type=Path)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(SourceContract))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.kernel_dtb or args.uboot_dtb:
        if not (args.kernel_dtb and args.uboot_dtb):
            parser.error('compiled audit requires both kernel and firmware DTBs')
        for path in (args.kernel_dtb, args.uboot_dtb):
            check_dtb(path)
