# 文档中心

[返回项目首页](../README.md)

按使用、构建、开发、设备和发布记录分类。构建成功、组件验证与整镜像真机验收是不同结论，请以各文档的验证范围为准。

## 使用

- [安装与首次启动](usage/installation.md)：镜像类型、校验、SD 烧录与登录。
- [升级与回退](usage/upgrade.md)：VyOS 原生升级、配置迁移和固件边界。

## 构建

- [构建指南](build/README.md)：环境、默认目标、构建模式、产物与 CI。
- [维护与验收](build/maintenance.md)：输入版本、缓存、容器隔离与发布检查。
- [历史构建记录](build/history.md)：候选产物、构建故障与资源对照；不是当前默认参数清单。

## 开发

- [项目架构](development/architecture.md)：构建阶段、板级资产与目录约定。
- [设备适配](development/porting.md)：新增设备、补丁组织与回归入口。
- [DAE 内核契约与 BTF 复盘](development/dae-kernel.md)。

## 设备

- **[Radxa Cubie A5E](boards/a5e/README.md)**：[SD / NVMe 启动](boards/a5e/boot.md) · [PCIe](boards/a5e/pcie.md) · [Wi-Fi](boards/a5e/wifi.md) · [启动调查](boards/a5e/bringup.md)。
- **Radxa E52C**：[网络调优与 VyOS 配置边界](boards/e52c/network-performance.md)。
- 其他设备的声明、补丁与专属资产位于 [`boards/`](../boards/)。

## 发布

[发布记录](releases/README.md)列出构建来源、产物与验证边界。历史记录按当时的状态保留，不把旧版本测试结果自动算作新版本验收。
