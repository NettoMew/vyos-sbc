# 构建指南

[文档中心](../README.md) · [维护与验收](maintenance.md) · [历史记录](history.md)

## 开始构建

以下命令均在仓库根目录的 Linux 构建环境中执行：

```bash
make a5e-dry    # 静态预览：不构建、不联网、不 sudo
make a5e        # 完整构建 A5E
```

当前调试目标为 A5E，裸 `make` 也只构建 A5E。其他设备仍可显式指定；`make all` 会构建全部设备，不用于当前单板调试。

完整流程为：依赖与源码 → overlay → builder → 内核 → 共享基础 ISO → 板级资产 → U-Boot → 整盘镜像 → 板级升级 ISO。

## 构建环境

需要 Linux、Docker、交叉工具链及镜像组装工具。也可在 Linux VM 中构建；原生 arm64 可避免用户态仿真开销，amd64 上的 arm64 builder 需要可用的 binfmt 支持。

使用仓库提供的 host 工具容器，可避免在宿主机安装整套编译依赖：

```bash
scripts/docker-build.sh a5e
```

该入口仍会构建 host 工具镜像，即使传入 `--dry-run` 也会启动 Docker。真正只看计划请用 `make a5e-dry`。

镜像组装涉及 loop、挂载和 chroot，工具容器需要特权及 Docker socket；这是依赖隔离，**不是不可信代码的安全沙箱**。资源限制、共享宿主保护要求见[容器隔离边界](maintenance.md#容器隔离边界)。

Arch / CachyOS 的依赖参考：`docker`、`qemu-user-static`、`aarch64-linux-gnu-gcc`、`squashfs-tools`、`parted`、`dosfstools`、`e2fsprogs`、`xz`、`zstd`、`rsync`、`swig`、`python-pyelftools`、`debhelper`。依赖检查阶段会列出缺项；完整工具清单见 [`Dockerfile.host`](../../docker/Dockerfile.host)。

## 配置与内核模式

默认值位于 [`build.conf`](../../build.conf)，板级能力位于 [`boards/<设备>/board.conf`](../../boards/)。支持的参数可通过环境变量覆盖。

| 模式 | 用途 |
| :-- | :-- |
| `cross`（默认） | 宿主工具链编译，保留准备好的内核树，供外置模块匹配 ABI 和签名 |
| `container` | 官方 arm64 容器内核流程，不提供外置模块所需的宿主侧构建树 |

A5E、M28K、R5S、E52C 的外置驱动需要 `cross`；E20C 可选择 `container`。不兼容的完整构建计划会提前拒绝。

例如重建 A5E 内核：

```bash
KERNEL_BUILD_MODE=cross REBUILD_KERNEL=1 make a5e
```

`WORK_DIR` / `OUT_DIR` 可指定中间件和产物目录；`JOBS`、`BUILD_CPUS`、`BUILD_MEMORY` 等参数用于容器资源控制。先保留经过验证的默认值，不要把提高并行数视为必然提速。

## 产物与缓存

`out/` 存放每板 `.img.xz`、`.iso` 及相应校验文件。`.img.xz` 用于整盘烧录，`.iso` 用于系统升级；参见[安装](../usage/installation.md)和[升级](../usage/upgrade.md)。

内核、基础 ISO、U-Boot 和 builder 使用输入指纹复用缓存。定制变化应触发相关产物重建，不通过删除其他项目缓存来“修复”构建。`make distclean` 会删除 `work/` 和 `out/`，使用前必须备份需要保留的镜像及日志。

固定源码提交不代表滚动软件源可字节级复现；发布需记录实际输入与产物摘要，详见[维护与验收](maintenance.md)。

## GitHub Actions

[`build-image`](../../.github/workflows/build.yml) 仅手动触发，使用原生 arm64 运行器。在 Actions 中选择设备和内核模式即可构建，默认 A5E / cross；不会因普通 push 自动构建全部设备。

流程缓存源码、内核与构建容器，并上传镜像产物。CI 构建和离线回归通过不等于真机验收通过。
