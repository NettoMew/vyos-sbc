# A5E：SD / NVMe 启动与恢复

[A5E 文档](README.md) · [文档中心](../../README.md)

## 启动链与验收边界

- SD：BROM → SD 上的 SPL/BL31/U-Boot → SD 的 EFI/GRUB → SD 系统。
- NVMe：BROM → SPI 上的 SPL/BL31/U-Boot → NVMe 的 EFI/GRUB → NVMe 系统。
  BROM 不直接读取 NVMe，只有把系统复制到 SSD 不构成无 SD 启动。
- 调试时可先保留 SD，仅让 SD 提供 SPL/U-Boot，显式加载 NVMe 的 EFI loader。
- SD 仍是恢复介质；不要为了选 NVMe 保存一个排除 SD 的永久 `boot_targets`。

0545 已完成 NVMe 4 GiB 安装读回校验、系统启动、扩容、文件写入/两次直接读回；
新版 SD 与 NVMe 同时插入的介质隔离通过。SPI 已备份、定长更新并全量读回比较。
用户实际拔掉 SD 后，SPI-only 自动冷启动和普通重启均通过；每次均核对无 SD 块设备、
NVMe 系统/持久化 UUID、内核/initrd/squashfs 摘要和文件直接读写。写 SPI 后插回 SD 的
恢复启动及正确介质挂载也已通过；两块盘的临时调试服务已清理。
最新真机状态以 [PCIe 验证记录](pcie.md) 为准，不把离线测试当成启动验收。

## 构建与产物

```sh
make a5e
```

当前默认只构建 A5E，整盘使用 `.img.xz`；xz 是外层归档，与内核 initramfs
的压缩格式是两件事。ISO 用于系统升级，**不会替换 SD/SPI 内的启动固件**。
0545 的内核和全部模块已重编；用户态复用未运行过的 0220 rootfs 基线，并重新生成
initramfs、squashfs、版本信息及介质绑定逻辑，不是一次完整的软件源重建。

## 安装到 NVMe（清空目标 SSD）

在已启动的 A5E VyOS 上先确认目标序列号、容量及挂载状态。不要猜 `/dev/nvme0n1`
就是目标，也不要给同名但不同序列号的盘执行写入：

```sh
lsblk -o NAME,SIZE,MODEL,SERIAL,FSTYPE,UUID,MOUNTPOINTS
cat /sys/block/nvme0n1/device/serial
```

将镜像放在 SD 上有足够空间的目录，**不要放入 1 GiB 机器的 `/tmp`（tmpfs）**。
把发布的 `install-a5e-nvme.sh`、`grub-setup.py` 放在同一个目录，或从源码仓库运行。
先验证随附 SHA256，再执行（以下是占位参数，必须替换为实际文件/序列号/摘要）：

```sh
sudo bash ./install-a5e-nvme.sh \
  /path/on/sd/vyos-<version>-radxa-cubie-a5e.img.xz \
  /dev/nvme0n1 '<exact-serial>' '<image-sha256>' --erase
```

安装器检查板型、整盘设备、序列号、容量、所有挂载/holder，完整解压验证 xz、
GPT/SPL 和镜像大小；写入后读回完整 4 GiB 做 SHA256 校验。随后生成独立 GPT GUID、
ext4 UUID，重建 FAT ESP 和官方 EFI GRUB。它不写 SPI，也不改 SD 启动固件。
首次启动由 growfs 服务扩展持久化分区。安装器失败时保留 SD 恢复环境，不自动重启。

## SD 与 NVMe 同时插入：只使用所选介质

不要将同一 raw image 原样复制两次后同时插入：UUID 相同会使 GRUB 和 live-boot
选盘不确定。上述安装器主动更换 SSD 身份；板级 `BOARD_BIND_BOOT_MEDIA=1` 还会：

1. GRUB 从实际选中的 root filesystem 探测 UUID，传递 `sbc-media-uuid=`。
2. initramfs 只在该 UUID 的分区查找 squashfs 与持久化目录。
3. 缺失、非法或重复参数不降级到另一块磁盘；无该参数的其他板型保持原行为。

在保留 SD 的 U-Boot 提示符中，可以明确选择 NVMe（不是 `saveenv`）：

```text
pci enum
nvme scan
if load nvme 0:1 ${kernel_addr_r} /EFI/BOOT/BOOTAA64.EFI; then bootefi ${kernel_addr_r} ${fdtcontroladdr}; fi
```

注意：只设置 `boot_targets=nvme0` 再 `run bootcmd`，仍可能由 EFI boot manager
选中已有的 `mmc0` 启动项。必须用内核命令行和实际挂载验证，不能只看扫描过 NVMe。

进入系统后记录：

```sh
uname -a
cat /proc/cmdline
lsblk -o NAME,SIZE,FSTYPE,UUID,MOUNTPOINTS
findmnt -t ext4,overlay,squashfs
sudo journalctl -b -u sbc-growfs --no-pager
sudo dmesg | grep -Ei 'nvme|pcie|timeout|corrupt|oops|panic'
```

预期 NVMe 的 UUID 同时对应命令行、live medium 和持久化 ext4；SD 不应被当作该版本
的写层。还需实际验证普通重启、冷启动、读写和一段时间运行稳定性。

## SPI：先完整备份，再定长更新，最后拔 SD 冷启动

SPI 固件与 SD 固件为同一个 `u-boot-sunxi-with-spl.bin`，但写入偏移不同：
**SD 为 128 KiB；SPI 为 0**。不要把整盘 `.img` 写入 SPI，也不要把 SD 固件写到
8 KiB 破坏 GPT。参考 [Radxa SPI 安装说明](https://docs.radxa.com/en/cubie/a5e/getting-started/install-system/nvme-system/burn-spi)。

写入前应确认 `sf probe` 识别正确型号/容量，完整读取 16 MiB SPI，并可靠保存到另一台
电脑计算 SHA256。备份未落到另一台电脑前不执行擦写。
固件必须核对该版本随附 SHA256；仅更新其实际字节数，随后 SPI 读回并逐字节比较。
不要用整片擦除替代定长更新。

**本机不要使用 U-Boot `fatwrite mmc` 传输大文件备份**：16 MiB 写入实测失败并损坏
ESP 的 FAT 元数据，之后已先备份整个 ESP，再用 Linux fsck 修复，SD 启动验证通过。
该 U-Boot 写入问题尚未修复。本次原 SPI 全空，采用完整 `sf read` 后与独立生成的
16 MiB 全 FF 缓冲区逐字节比较；所有字节一致后在电脑重建等价备份并记录方法。
这不是仅凭 CRC 猜测内容，也不是 SPI 原始数据的网络下载。非空 SPI 不适用此方法，
必须另行完成可靠的完整备份传输。

只有满足以下条件后，才可把 SPI/NVMe 启动标为通过：

1. 新系统已在 NVMe 完成运行与重启测试。
2. SPI 全量备份已保存到板外，固件写入后的读回比较通过。
3. 正常关机、断电、移除 SD、上电；捕获 SPL 从 SPI 加载和 Linux 从 NVMe 挂载的日志。
4. 无 SD 状态下再做普通重启，确认电源与 PERST# 交接可重复。
5. 插回 SD 能恢复启动；不能以修改 SPI 为代价丢掉 SD 恢复通路。

本机 SPI 定长更新、整片比较、无 SD 冷/热启动、NVMe 读写及插回 SD 恢复均已通过。
正常使用时 SD 优先，拔 SD 后自动走 SPI→NVMe；不需要每次手动输入 U-Boot 命令。
这是这块板及 FORESEE E2M2 64GB 的实测，不等于所有 SSD 或长时间压力测试认证。
