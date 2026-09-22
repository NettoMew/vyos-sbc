# 设备适配

[文档中心](../README.md) · [项目架构](architecture.md) · [维护与验收](../build/maintenance.md)

## 新增设备

先选用已有 SoC 家族，再按目录约定添加声明与专属文件：

| 路径 | 内容 |
| :-- | :-- |
| `boards/<设备>/board.conf` | 家族、串口、U-Boot、DTB 与板级能力开关 |
| `boards/<设备>/uboot/` | U-Boot 定制与补丁 |
| `boards/<设备>/overlay/` | 内核补丁、配置或设备树 |
| `boards/<设备>/rootfs/` | 网口命名、服务等板级根文件系统补充 |
| `families/<家族>.conf` | 新家族的固件来源、文件名和写入偏移 |
| `Makefile` | 在设备列表中注册入口 |

可参考 [`boards/a5e/`](../../boards/a5e/) 和 [`boards/m28k/`](../../boards/m28k/)，不要把已有板的 GPIO、供电和写盘偏移直接套到新硬件。

## 补丁与模块

- 板级必需 U-Boot 修复放在 `uboot/patches/always/`，按文件名排序应用；可选开核补丁保留能力开关约束。
- 可复用的外置驱动兼容补丁放在 `vendor/`，板级差异单独声明，避免复制多份共享补丁。
- 外置模块使用目标内核的 `kernel.release`、`Module.symvers` 和签名密钥；先处理调试段，再签名。
- 驱动、固件和 autoload 文件进入该板的资产目录，最终由镜像阶段注入，不污染共享基础 ISO。
- 修改启动设备树时同时检查内核 DT 与固件交接 DT；只更新未被使用的备用 DTB 不算修复。

## 回归与验收

首先用 `make <设备>-dry` 检查阶段和缓存计划。在 Linux 构建环境中运行 Shell 回归及相关 Python 检查：

```bash
for test in tests/*.sh; do bash "$test" || exit; done
python3 tests/a5e-hwid.py
python3 tests/a5e-pcie.py
python3 tests/aic8800.py
sudo python3 tests/boot-media.py
python3 tests/net-tune.py
```

语法、ShellCheck 与编译后 DTB 检查的具体入口见 [CI 工作流](../../.github/workflows/build.yml)。内核 BPF/BTF 变更还需满足 [DAE 内核契约](dae-kernel.md)。

分别记录源码回归、实际产物检查、组件真机测试和完整镜像启动，不能互相替代。网络业务由 VyOS 配置管理；驱动修复不应顺便覆盖用户的路由、offload 或无线配置。

设备文档放在 `docs/boards/<设备>/`，发布结果放在 `docs/releases/`，同时更新[文档索引](../README.md)。
