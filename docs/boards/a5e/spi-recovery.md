# A5E SPI 备份与恢复包

[A5E 文档](README.md) · [SD / NVMe 启动](boot.md)

下载：[2026-09-22 SPI 恢复包](https://github.com/NettoMew/vyos-sbc/releases/tag/a5e-spi-recovery-2026.09.22)。
二进制保存在 Release 附件，不进入 Git 历史。此发布仅用于备份与启动固件恢复，
标为预发布，**不是整盘系统镜像，也不是厂商出厂固件**。

## 包含什么

`a5e-spi-recovery-20260922.tar.xz` 解压后包含：

| 目录 / 文件 | 用途 |
| :-- | :-- |
| `backups/a5e-spi-before-20260922-1015.bin` | 最初的 16 MiB SPI 状态，全部为 `FF`；**不可启动，不能当作修复固件刷入** |
| `backups/a5e-spi-before-wifi-20260922.bin` | Wi-Fi 更新前的 16 MiB SPI 状态：0545 / 0075 固件，其余全部为 `FF` |
| `firmware/u-boot-2026.09.22-0545-a5e-nvme-radxa-cubie-a5e.bin` | 906,137 字节；SD/NVMe 启动固件，旧版回退用，不含后续 Wi-Fi DT 修正 |
| `firmware/u-boot-2026.09.22-1150-a5e-wifi-radxa-cubie-a5e.bin` | 906,729 字节；包含 0076/0077 Wi-Fi DT 与供电修正的启动固件 |
| `firmware/*.config` | 对应两版 U-Boot 构建配置，不是设备运行配置 |
| `manifest.json`、`SHA256SUMS`、`README.md` | 文件摘要、来源及验证范围、使用说明 |

两份完整备份都是**等价重建文件**：先读取实际 SPI，在板上将全部 16,777,216 字节
与独立准备的预期内容逐字节比较，一致后在电脑保存相同内容。原始备份与全 `FF`
比较；更新前备份与已知 0075 固件加 `FF` 尾部比较。不是 SPI 原始字节的串口/网络下载，
也不是仅凭 CRC 推测。它们不包含已保存的 U-Boot 环境或额外用户数据。

本包不含 SD 首部、ESP 文件系统备份、串口原始日志、设备序列号、用户配置或私钥。
这些本机诊断材料不作为通用恢复文件公开；原件仍保留在本地。

## 下载校验

下载 Release 的四个附件（压缩包、`README.md`、`manifest.json`、`SHA256SUMS`），
放在同一个空目录中，先校验下载内容，再解包校验内部文件：

```sh
sha256sum -c SHA256SUMS
tar -xJf a5e-spi-recovery-20260922.tar.xz
cd a5e-spi-recovery-20260922
sha256sum -c SHA256SUMS
```

Windows 可用 `Get-FileHash -Algorithm SHA256 <文件>` 对照摘要，再用支持 xz/tar 的工具解包。
不要把本归档交给 Etcher；Etcher 使用的是系统 `.img.xz`，本包不是磁盘镜像。

## 恢复原则

1. **仅限 Radxa Cubie A5E。** 先用已验证的 SD 救援卡启动，保持稳定供电和串口连接。
   本次验证的 SPI 是 `w25q128fw`、16 MiB；不同板型、芯片或容量不可直接套用。
2. 在任何写操作前，对目标机器的**当前 SPI**另做完整板外备份并校验。
   本包只记录这一块测试板的历史，不能替代另一块板的专属备份。
3. 通常恢复 `firmware/` 中匹配系统的短固件，而不是覆盖整片 SPI。
   SPI 固件偏移为 **0**，SD 固件偏移为 **128 KiB**；不要混用，也不要把整盘 `.img` 写入 SPI。
4. 先 `sf probe` 核对芯片，再确认加载的固件长度、摘要和 RAM 地址。
   `sf update` 按擦除块工作，最后一个块中超出文件长度的部分也可能被擦除；
   必须先检查该范围并保留原数据，不能把“定长更新”误解成任意尾部数据都安全。
   具体语义见 [U-Boot 的 sf 命令说明](https://docs.u-boot.org/en/latest/usage/cmd/sf.html)。
5. 写后读回整个 SPI，逐字节核对新固件及预期保留区域；核验失败不要重启。
   本机两版固件之后的区域均为 `FF`；其他机器不可作此假设。
6. 更新 SPI 不会更新 SD 固件或 SSD 系统。恢复后分别验证 SD 启动，以及拔 SD 后
   SPI→NVMe 的冷启动、普通重启、实际挂载介质和读写。

不要执行整片擦除来“修复”NVMe 启动：恢复全空状态会移除 SPI 启动固件。
本机 U-Boot 的大文件 `fatwrite mmc` 曾损坏 ESP，**不要用它导出 SPI 备份**。
完整安装与验收流程见 [SD / NVMe 启动与恢复](boot.md)。

## 验证范围与源码

两版启动固件均已做 SPI 全量读回比较、SD 启动和无 SD 的 NVMe 冷/热启动验证。
1150 的 Wi-Fi 驱动组件在更新后的 0545 系统上验收；**1150 整镜像尚未重刷验收**。
旧版回退会撤销后续 Wi-Fi DT 支持，不能据此判断 Wi-Fi 模块损坏。

`manifest.json` 固定上游 U-Boot / TF-A commit，并列出配套仓库提交及补丁摘要。
这是既有固件的归档，没有重新编译或把旧固件冒充为当前主线的新构建。
更多背景见 [0545 发布记录](../../releases/2026.09.22-0545-a5e-nvme.md)、
[1150 发布记录](../../releases/2026.09.22-1150-a5e-wifi.md)及[构建指南](../../build/README.md)。
