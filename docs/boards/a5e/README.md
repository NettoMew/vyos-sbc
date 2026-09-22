# Radxa Cubie A5E

[文档中心](../../README.md) · [安装镜像](../../usage/installation.md)

Allwinner A527，双千兆以太网，AIC8800D80 SDIO Wi-Fi。当前默认构建目标为 `a5e`，串口参数为 115200 / 8N1 / 无流控。

## 验证状态

- SD 系统启动、NVMe 系统与读写、无 SD 的 SPI→NVMe 冷启动和重启已实测。
- AIC8800 签名模块、固件、`wlan0`、AP/managed 接口类型切换与被动扫描已在 SD 和 NVMe 启动下验证。
- STA/AP 业务配置由 VyOS 负责；未把接口类型切换当作实际关联、AP 客户端收发或长期性能验证。
- `2026.09.22-1150-a5e-wifi` 已完成打包及离线检查，真机使用 0545 系统更新相同组件；**1150 整镜像尚未重刷验收**。

## 使用与排障

| 文档 | 内容 |
| :-- | :-- |
| [SD / NVMe 启动与恢复](boot.md) | 启动链、安装器、UUID 隔离、SPI 备份与恢复 |
| [PCIe / M.2](pcie.md) | 控制器、PHY、时序与 NVMe 验证记录 |
| [AIC8800 Wi-Fi](wifi.md) | SDIO 供电、签名模块、固件及验收范围 |
| [启动调查](bringup.md) | U-Boot、USB DMA、initramfs 与早期启动故障取证 |

无 SD 启动需要配套 SPI 固件；ISO 升级不会更新 SPI。保留 SD 救援卡，不将同一镜像以重复 UUID 同时部署到 SD 与 NVMe。

构建来源及已知限制见 [0545 SD/NVMe 记录](../../releases/2026.09.22-0545-a5e-nvme.md)和 [1150 Wi-Fi 记录](../../releases/2026.09.22-1150-a5e-wifi.md)。
