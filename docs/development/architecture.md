# 项目架构

[文档中心](../README.md) · [设备适配](porting.md) · [构建指南](../build/README.md)

## 共享基础与板级资产

项目通过 overlay、配置片段和补丁扩展上游构建，不维护独立的 vyos-build fork。公共内核与基础 ISO 在输入一致时复用；设备差异在板级声明、固件和资产中维护。

| 阶段 | 产物与职责 |
| :-- | :-- |
| 内核 | 上游内核、SoC 配置片段与板级补丁 → 签名内核包 |
| 基础 ISO | 官方 arm64 组装流程 → 不含板级外置资产的基础系统 |
| 板级资产 | 对应内核 ABI 的外置模块、固件和板级文件 |
| U-Boot | 主线源码与板级补丁；Rockchip 配合 rkbin，A5E 编译 TF-A BL31 |
| 整盘镜像 | 注入该板资产、生成 squashfs、分区及启动结构 |
| 板级 ISO | 使用该板 squashfs 生成可由 VyOS 原生升级的系统镜像 |

AIC8800、r8125、OLED 等专属资产不写入共享基础 ISO，避免无对应硬件的其他板型加载错误模块。

## 编排与配置

[`scripts/build.sh`](../../scripts/build.sh) 是阶段入口，配置顺序为 `build.conf` → `board.conf` → 派生环境。`Makefile` 只提供设备与常用阶段快捷入口。

板级行为优先使用能力声明，不在通用构建引擎中扩展机型名称白名单。昂贵构建阶段的缓存需覆盖其真实输入：源码引用、补丁、配置、工具链和相关资产。

## 启动与升级

通常启动链为 BootROM → SPL / U-Boot → GRUB（EFI）→ 内核与 initrd。A5E 的 SD 与 SPI / NVMe 链路见[设备启动文档](../boards/a5e/boot.md)。

镜像引导结构复用 VyOS 的 GRUB 生成机制。系统升级保留原生多版本和回退能力，但不把启动固件更新混入 ISO 升级；见[升级边界](../usage/upgrade.md)。

## 目录约定

```text
build.conf       构建参数与上游版本
Makefile         常用入口
scripts/         阶段编排、容器入口与安装工具
lib/             构建引擎
families/        SoC 家族声明
boards/          每板配置、补丁和资产
overlay/         共享的 vyos-build 定制
vendor/          固定来源的外置驱动包与共享补丁
resources/       镜像组装辅助工具
docker/          构建工具容器
tests/           回归与产物检查
docs/            使用、构建、开发、设备及发布文档
work/            中间产物（不入库）
out/             镜像与校验文件（不入库）
```
