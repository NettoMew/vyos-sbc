# 安装与首次启动

[文档中心](../README.md) · [升级与回退](upgrade.md)

## 选择镜像

为设备选择对应板型的产物，不要混用不同型号的启动固件。镜像来自本地构建或手动触发的 CI，源码仓库不提交镜像二进制；获取方式见[构建指南](../build/README.md)。

| 文件 | 用途 |
| :-- | :-- |
| `vyos-<版本>-<设备>.img.xz` | 压缩整盘镜像，包含分区、系统和该板 SD 启动固件 |
| `vyos-<版本>-<设备>.iso` | 已运行设备的 VyOS 原生系统升级 |
| `.sha256` / `SHA256SUMS-*.txt` | 核对下载或传输后的文件完整性 |

查看该版本的[发布记录](../releases/README.md)，区分待验证候选和已完成的真机测试。

## 烧录 SD 卡

1. 备份卡上数据，核对目标设备容量、型号及镜像 SHA256。
2. 用 Etcher 打开 `.img.xz` 烧录，或先解压为 `.img`。
3. 烧录完成后安全弹出，将 SD 插入板子再上电。

Linux 命令行示例（**会覆盖整块目标盘**；`/dev/sdX` 必须替换为核实后的 SD 整盘设备，不是分区）：

```bash
set -euo pipefail
lsblk -o NAME,SIZE,MODEL,SERIAL,MOUNTPOINTS
cd out
sha256sum -c 'vyos-<版本>-radxa-cubie-a5e.img.xz.sha256'
xz -t 'vyos-<版本>-radxa-cubie-a5e.img.xz'
xz -dc 'vyos-<版本>-radxa-cubie-a5e.img.xz' | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress
```

校验失败时停止操作，不要继续写盘；目标盘上已挂载的分区须先卸载。

## 首次登录

镜像默认通过 DHCP 获取地址并开启 SSH。把网口接到有 DHCP 的网络，待系统启动后连接：

```bash
ssh vyos@<设备地址>
```

默认账户为 `vyos / vyos`，首次登录后请立即修改密码。没有可用网络时，使用对应设备文档中的串口参数；A5E 为 115200、8N1、无流控。

网络和无线业务配置由 VyOS 管理。驱动可见不等于已经配置 STA 或 AP，构建脚本不会替用户选择无线网络。

## A5E 的 NVMe 启动

A5E 无 SD 启动采用 **SPI 固件 → NVMe 系统**；只把镜像写到 SSD 不够。安装器会清空目标 SSD，须核对序列号并先备份。

请按 [A5E SD / NVMe 启动与恢复](../boards/a5e/boot.md)操作，保留 SD 救援卡。不要将相同整盘镜像原样复制到 SD 和 NVMe 后同时使用，重复 UUID 会影响介质选择。
