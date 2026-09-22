# 维护与验收

[文档中心](../README.md) · [构建指南](README.md) · [历史记录](history.md)

## 版本策略

VyOS 固定到明确提交,内核沿用该提交的 `data/defaults.toml`,Debian 基础发行版与用户态软件源跟随 VyOS。U-Boot 使用稳定发布版本,rkbin 与 AIC8800 使用明确提交。更新引用后必须重新验证板级补丁,不以版本号较大代替兼容性证据。

固定 Git 提交不等于字节级可复现:滚动 APT 软件源与容器基础镜像仍会变化。发布时应记录实际容器 ID、软件包版本、固件文件校验值和最终镜像 SHA256,不能只记录日期版本串。

2026-09-15 维护基线:

| 组件 | 引用 | 说明 |
| --- | --- | --- |
| VyOS | `22dfa15927f2bd01336ab2c0154800f061b0f2e8` | rolling,Debian bookworm,配套 Linux 6.18.50 |
| U-Boot | `ece349ade2973e220f524ce59e59711cc919263f` | v2026.07 稳定版 |
| rkbin | `3e288fe814e059dd06833495f845cab04ac20a5c` | DDR/BL31 文件还需按板记录摘要 |
| TF-A（A523） | `e019f64d91ff7c2dfbbfe7f76a14f240761b9edc` | jernejsk 分支 a523-v4（上游 TF-A 尚无 sun55i_a523）;仅 Cubie A5E 的 BL31 |
| AIC8800 | `516e3b087763d80c44f5e3b6d2dd63e0d925c91d` | 固定源码构建；不自动应用其 Debian 包补丁 |
| r8125 | `9.018.00` | 仓库保留官网下载原始包,解包前核对固定 SHA256 |

Realtek 官网下载需要验证码。维护者提供的 9.018.00 原始包保存在 `vendor/r8125/`,默认构建无需再次访问下载站。包内版本已核对,本次计算的 SHA256 为 `66291cb5d4d3b359cfa0c9ca902028d9ce0f76065887cb64b4052dce4a676ff8`;该摘要用于锁定输入和检查传输,不等于 Realtek 发布的签名或独立来源认证。来源与许可见该目录说明。

需要替换输入时,必须同时提供 `R8125_SOURCE_URL` 与 `R8125_SOURCE_SHA256`;`file://` 文件须位于挂入容器的项目/work 路径内。摘要错误、损坏缓存或错误布局均中止构建,不会回退到旧版或镜像仓库。

9.018.00 将模块参数 `eee_giga_lite` 改为 `enable_giga_lite`。项目没有持久化旧参数;自行添加过 modprobe 参数的设备需要检查并迁移。编译时继续关闭 ASPM、EEE、Giga Lite 的默认启用,保持 RSS 与多 TX 队列;另外显式维持此前关闭的 DASH 与 page reuse,避免版本升级同时引入尚未验证的新路径。这些选择不构成 WAN 断链根因判断或修复保证。

## 清理范围与回归

U-Boot 板级必需修复放在 `boards/<board>/uboot/patches/always/*.patch`，按文件名顺序始终应用；
既有 `patches/*.patch` 保持 `BOARD_UNLOCK_CORES` 门控。两类都进入输入指纹且不作为源码覆盖复制。
A5E USB 交接补丁的硬件证据、验证边界及已知限制见 [A5E bring-up](../boards/a5e/bringup.md)。

此次维护先为源码切换、缓存失效和构建失败路径增加回归测试,再修正实现。范围限于版本获取及构建可信性,不改变路由策略、网卡调优和板级开核默认值。

- 相同提交允许复用已投放 overlay 的工作树;新提交必须检出正确源码。
- 构建失败不得用上次遗留的内核包满足成功条件。
- 内核、基础 ISO、U-Boot 和 builder 缓存必须对应其构建输入。
- 源码包在解包、编译之前校验;下载失败或校验不符不得回退到其他版本。

Overlay 路径清单从首次执行新版 `overlay` 阶段开始建立。它不能猜测旧工作目录中未登记文件的来源;迁移历史构建目录时宜使用新的 `WORK_DIR`,不要期待首次登记自动清理所有旧定制。

回归脚本位于 `tests/`,使用临时目录和模拟命令,不需要启动真实镜像构建。Shell 脚本使用 Bash,在 Linux 构建容器中执行测试与 ShellCheck。

## 容器隔离边界

`docker/Dockerfile.host` 提供原生架构的交叉工具链及镜像组装工具,避免在构建宿主机安装整套开发依赖。ARM64 基础系统在独立的 VyOS builder 容器中生成;amd64 宿主需要注册带 `F` 标志的 ARM64 binfmt 解释器。

```bash
# 默认 cross、16 并行、16 CPU、32 GiB 内存;参数也约束内层运行容器。
scripts/docker-build.sh e52c

# 单独检查版本和阶段;真正不启动 Docker 的静态预览用 scripts/build.sh --dry-run。
scripts/docker-build.sh e52c --dry-run
```

`JOBS`、`BUILD_CPUS`、`BUILD_MEMORY` 可覆盖默认资源上限;内层 `BUILDER_CPUS`、`BUILDER_MEMORY` 默认继承。各运行容器分别受限,不是整个构建树共享总配额。Docker daemon 的镜像构建不继承 `docker run` 限额。打包压缩线程同样遵循 `JOBS`。

镜像组装需要 loop 设备、挂载与 chroot,因此使用特权容器;Docker socket 也具有宿主 root 权限。此方案隔离软件依赖,不是运行不可信代码的安全沙箱。只使用受信源码,不挂载额外业务目录,不发布容器端口。

源码、日志和产物放在专用目录,不得对共享宿主执行 `docker system prune`、清理其他项目容器或覆盖全局 Docker 配置。构建结束仅移除本次容器;保留产物和日志,缓存按项目单独管理。官方 Docker 安装脚本会添加软件源并安装、启动系统服务,属于宿主机的持久变更。

## 发布验收

1. 生成目标板整盘 `.img.xz` 与升级 `.iso`，校验压缩流及 ISO 内的 `sha256sum.txt`。
   当前只调试 A5E，不自动构建其他板；旧版本产物 `.img.zst` 的历史记录保留。
2. 检查内核版本、目标架构、模块 vermagic 与签名、板级 DTB 和 GRUB EFI 文件。
3. E52C/R5S 检查 r8125 与网口命名；M28K 检查 AIC8800、固件和 OLED；E20C 检查板级外设。A5E 还需配套检查 SD/SPI 固件、NVMe 介质选择及 AIC8800。
4. 真机分别验证冷启动、网络转发、PPPoE、链路稳定性、升级与回退。M28K 还需验证无线 AP,不能以模块加载成功代替。

离线产物检查与真机验收分别记录。没有真机结果的镜像只能作为待验证候选,不能宣称解决 WAN 断链。
