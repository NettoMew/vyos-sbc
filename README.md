# vyos-sbc

为 Rockchip / Allwinner 小主机构建 VyOS 路由系统。

提供可直接烧录的整盘镜像与原生升级 ISO，补齐板级启动、驱动和固件适配，保留 VyOS 的配置、升级与回退机制。

## 支持设备

| 设备 | SoC | 网络 | 验证状态 |
| :-- | :-- | :-- | :-- |
| Radxa E20C | RK3528 | 双千兆 | 真机验证 |
| MangoPi M28K | RK3528 | 双千兆 · Wi-Fi 6 | 真机验证 |
| NanoPi R5S | RK3568 | 千兆 + 双 2.5G | 真机验证 |
| Radxa E52C | RK3582 | 双 2.5G | 真机验证（开核 8 核） |
| Radxa Cubie A5E | Allwinner A527 | 双千兆 · Wi-Fi 6 | SD / SPI→NVMe 启动、AIC8800 驱动验证 |

支持状态记录已完成的真机测试，不代表每个新镜像都已通过完整验收。具体范围见设备文档与发布记录。

## 使用与文档

- **使用镜像**：[安装与首次启动](docs/usage/installation.md) · [升级与回退](docs/usage/upgrade.md)
- **设备说明**：[Cubie A5E](docs/boards/a5e/README.md) · [E52C 网络调优](docs/boards/e52c/network-performance.md)
- **构建与开发**：[构建指南](docs/build/README.md) · [项目架构](docs/development/architecture.md) · [设备适配](docs/development/porting.md)
- **完整索引**：[文档中心](docs/README.md) · [发布记录](docs/releases/README.md)

当前默认构建 **A5E**，整盘格式为 **`.img.xz`**。系统升级 ISO 不会更新 SD / SPI 中的启动固件；A5E 的无 SD 启动需配套 SPI 固件。

## 许可

构建脚本与设备适配以 **MIT** 发布。VyOS、Linux、U-Boot 及其他组件遵循各自许可。
