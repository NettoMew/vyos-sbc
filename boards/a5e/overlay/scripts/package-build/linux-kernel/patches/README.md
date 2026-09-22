# A5E kernel backports

PCIe support is based on the **actual Armbian reference image's build commit**
`0648ff3c4125d673c18b5f032dc7c28545c542b5`, not floating `main`:
<https://github.com/armbian/build/tree/0648ff3c4125d673c18b5f032dc7c28545c542b5/patch/kernel/archive/sunxi-6.18/patches.armbian>.

- `170`: unchanged `drv-clk-sunxi-ng-fix-clock-handling-for-ccu-sun55i-a523.patch`.
- `171`: `drv-phy-allwinner-add-pcie-usb3-driver.patch`, with only Kconfig/Makefile
  insertion contexts rebased to vanilla 6.18.50 (no unrelated AC200 dependency).
  The driver C source is unchanged.
- `172`: unchanged `drv-pci-sunxi-enable-pcie-support.patch`.
- `173`: PCIe-only adaptation of the SoC/board DT patches. Omit unrelated IOMMU,
  vendor `usbc1`, SPI and display changes. Do not duplicate the PL11 GPIO claim
  using a pinctrl group. PB6/PB7 select/enable the board's PCIe lane switch.
- `174`: keep supplier probe errors (including `-EPROBE_DEFER`) rather than
  proceeding with an unpowered slot; WAKE# is an endpoint-driven **input**.
- `175`: retain CLDO1 at 1.8 V for the SPI NOR boot supply, matching firmware DT.
- `176`: require enabled LTSSM and live DL-active status after firmware handoff;
  report the negotiated speed rather than the target speed. Signed replacement
  host-module testing restored enumeration, but did not fix NVMe Identify.
- `177`: assert raw PERST# before owned slot power/REFCLK, release reset only
  after stabilization, and quiesce the host after PCI children at shutdown.
  Remove boot/always-on from the slot supply in both kernel and firmware DTs.
  The resulting 0545 kernel has booted from both SD and NVMe with independent
  medium UUIDs; NVMe growth, serial/SSH and direct I/O tests passed. Actual
  SD-removed SPI-only cold/warm boot also passed (see `docs/boards/a5e/pcie.md`).

The driver code retains original authorship/licensing. These are downstream
backports, not a claim that vanilla Linux 6.18 supports A523 PCIe.

`CONFIG_PCIE_SUN55I_RC=y`, `CONFIG_AW_INNO_COMBOPHY=y`, PCI/MSI/NVMe are enabled
in `74-allwinner-sun55i.config`. The corresponding PCIe DT description is also
applied to U-Boot (`0050`), because A5E uses the EFI firmware DT, **not** a kernel
DT override. Keep both descriptions synchronized and validate both compiled DTBs.

The published 0220 firmware leaves PCIe initialization to Linux. The subsequent
NVMe boot work adds firmware PCIe/NVMe support and DMA-safe OS handoff; 176 is
needed because the host's APP_LINK bits can remain set after LTSSM is disabled.
SD remains the recovery boot medium. U-Boot still fixes up SID-derived MAC
addresses, and the prior USB OS-handoff fix remains in place.

A5E shares the SuperSpeed lane between PCIe and USB3. This configuration selects
PCIe; USB2 is unaffected. NVMe-only/SPI cold/warm boot is hardware-verified;
simultaneous USB3 + PCIe is not supported.
See <https://docs.radxa.com/en/cubie/a5e/hardware-use/usb>.
