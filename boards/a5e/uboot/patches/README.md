# A5E boot firmware fixes

`always/*.patch` is board-scoped and applied in filename order to U-Boot
`ece349ade2973e220f524ce59e59711cc919263f` (v2026.07). It is independent of
the optional Rockchip core-unlock patches. The full directory participates
in the firmware cache key.

| Patch | Purpose / provenance |
| --- | --- |
| 0001 | Local EHCI/OHCI OS-handoff fix. Captured corruption physical address equals the old OHCI HCCA frame-number writeback address; `usb stop` A/B/A control confirms it. |
| 0010 | Match the bootable reference's actual `.config`: DRAM 936 MHz, not the upstream implicit 1200 MHz. Other DRAM parameters are unchanged. |
| 0020 | Armbian: explicitly configure/enable AXP717 CLDO3 SD power. |
| 0030 | Armbian: allow 20 ms for MMC power/clock stabilization. |
| 0040 | Armbian: A523 MMC divider handling and conservative SPL/eMMC clocks. |
| 0050 | Add the Linux PCIe/ComboPHY description to the firmware-passed DT. Match the kernel backport's compatible, interrupts, clocks and supply properties. No duplicate PL11 pinctrl claim. |
| 0060–0062 | Pinned Armbian PCIe clock, ComboPHY and host driver. Clock binding ID 180 already comes from 0050; PCI Makefile context rebased for v2026.07's AMD driver. |
| 0063–0064 | Pinned Armbian A523 SPI driver/SPL support. The already-upstream FIFO-reset polling is retained instead of duplicating it. |
| 0065 | Append NVMe to sunxi boot targets without removing SD recovery. |
| 0070 | Use the same Linux PCIe binding/supply in firmware, input-only WAKE#, preserve lane regulator ownership; propagate link/Identify failure; add PCI/NVMe OS-prepare removal and board SPI/NVMe configuration. |
| 0071 | Fence PCI DMA before failed-probe queue buffers are released; enable MTD, the SPI flash Kconfig parent. |
| 0072 | Explicitly enable the PB6/PB7 lane regulators on cold boot; fence DMA on command timeout before callers release payload buffers. |
| 0073 | Enable AXP717 CLDO1 at 1.8V in SPL and retain it in the Linux-passed DT; prefer NVMe after SD but before USB/network. Enable cache/regulator/PMIC diagnostic commands. |
| 0074 | Require enabled LTSSM and live PCIe data-link-active status; do not trust stale APP_LINK bits after OS handoff. |
| 0075 | Own the slot 3.3V supply, power-cycle under asserted PERST#, and release power before handing off to Linux. Paired with kernel 177; SD/NVMe runtime, I/O and SD-removed SPI cold/warm boot verified. |

Patches 0020–0040 are vendored unmodified with their original authorship
and sign-offs, from **0648ff3c4125d673c18b5f032dc7c28545c542b5**:
<https://github.com/armbian/build/tree/0648ff3c4125d673c18b5f032dc7c28545c542b5/patch/u-boot/v2026.07-sunxi64>.
This is the build commit recorded in `/etc/armbian-release` inside the user's
bootable `Armbian_community_26.11.0-trunk.52` image, not a floating `main` selection.
Its firmware metadata records the same U-Boot commit as this project.

No downloaded firmware blob is used by the release build. SPL/U-Boot and TF-A
are compiled from pinned source. The image stays GPT with firmware at 128 KiB;
writing a second copy at 8 KiB would corrupt GPT and is not a fix.

The USB DMA failure is physically diagnosed. Aligning the SD/DRAM baseline is
evidence-based, but does not retroactively prove which difference caused the
original no-SPL-output report. A newly built full firmware still needs its own
hardware boot verification; see `docs/a5e-bringup.md`.

## Current acceptance

0075 is installed in the SD firmware area and automatically identifies/reads
the NVMe without manual GPIO commands. Its explicit NVMe EFI handoff booted the
0545 kernel/rootfs to VyOS login; the installer also passed a full 4 GiB write
and readback hash check. Both disks now boot 0545 with independent medium UUIDs.
NVMe growth, serial/SSH access and a 64 MiB fsync write/two direct reads passed.
Persistent journal proves the first NVMe boot continued for 3.57 hours during
the earlier serial outage; its precise transport cause remains undetermined.
SPI was proven entirely blank byte-for-byte and an equivalent full backup was
saved off-board with provenance. Firmware update and full 16 MiB comparison
passed. Actual SD-removed automatic cold boot and normal reboot both reached
0545 VyOS with matching NVMe medium/persistence UUIDs and no mmc block device;
artifact hashes and repeated direct I/O passed on both boots. Temporary
validation services have been removed. Post-flash SD re-insertion boot and
correct SD medium/persistence selection also passed, with NVMe left unmounted.
Known limitation: a 16 MiB U-Boot SD FAT write failed. The ESP was backed up,
repaired under Linux, and then boot-tested. Do not use that firmware FAT-write
path for backups; no fix for the large-write issue is claimed.
See `docs/a5e-pcie.md` and `docs/a5e-nvme-boot.md` for current evidence.

## Historical diagnostic milestones

0220 firmware is now hardware-verified to boot VyOS and enumerate the NVMe PCI
endpoint. Its NVMe Identify command fails; it did not initialize PCIe in U-Boot.
The new boot stack through 0073 boots from SD and has successfully identified
the 57.6 GiB NVMe and read its first eight sectors in U-Boot. Linux still fails
Identify (0x4001); this is not a completed NVMe installation. A slot power cycle
also preceded that successful firmware test, so repeat cold-boot testing remains
necessary. Patch 0074 is compiled but not yet installed on the board.
The subsequent owned-power/reset prototype booted the reference Armbian kernel
with a working NVMe namespace and read-only I/O. Patch 0075 and kernel 177 are
compiled candidates for making that sequence automatic, not yet a verified
SD/SPI/NVMe release.
SPI NOR is now automatically identified as a 16 MiB w25q128fw with 0073's CLDO1
correction (AXP717 0x91 bit 0, 0x9b=0x0d). Readback works; no SPI write or
SPI-only boot is yet verified.
