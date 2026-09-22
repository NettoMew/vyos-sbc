# 历史构建记录

[文档中心](../README.md) · [构建指南](README.md) · [维护与验收](maintenance.md)

以下保留当时的环境、产物与故障记录；历史版本、格式和资源参数不代表当前默认值。

## 2026-09-15 候选构建记录

候选版本 `2026.09.15-22dfa159-rockchip` 已在 amd64 宿主的 Docker 环境完成四板构建,各产出整盘 `.img.zst` 和升级 `.iso`。Linux 6.18.50 源码签名通过 Greg Kroah-Hartman 公钥验证;内核包架构为 ARM64。E52C/R5S 模块版本为 `9.018.00-NAPI-RSS`,M28K 的 AIC8800 与 OLED 同时完成编译。

验证通过:

- 25 项缓存/源码回归、builder 与官方驱动输入回归,Bash 语法及变更脚本 ShellCheck。
- 8 个镜像的 SHA256、Zstandard 解压校验与 ISO 内部文件摘要。
- 四板整盘 GPT 主/备头及分区表 CRC,U-Boot 保留区与对应编译产物字节一致。
- FAT/ext4 只读检查,ARM64 EFI PE 头,内核/initrd/DTB/GRUB 文件布局。
- 整盘与同板 ISO 内的 squashfs 字节一致;外置模块 vermagic、ARM64 架构及 CMS 签名与本次内核公钥匹配。
- 成品传回维护工作站后再次核对 SHA256,全部一致。

产物附有构建清单、基础系统 SBOM 与离线校验日志。基础 SBOM 不包含后注入的板级资产,这些资产另列于构建记录。镜像仍是待真机验收候选,尚未验证冷启动、WAN 稳定性和升级回退,不得据此宣布断链问题已经解决。

## DAE 内核能力验收

2026-09-15 候选镜像的交叉编译容器缺少 pahole。虽然上游片段请求
`CONFIG_DEBUG_INFO_BTF=y`,Kconfig 因依赖不满足取消该项,构建仍继续并生成了无 BTF
的内核。此外原配置未启用 `CONFIG_BPF_STREAM_PARSER`。这两项均不满足 DAE 基线;
旧版离线打包验证不能视为 DAE 可用性证明。

修复顺序:先用回归测试锁定缺项拒绝行为,再补构建依赖与声明式配置,最后检查真实
构建输出。`73-dae.config` 是 DAE 能力契约:在 dae 上游 BPF/TC/BTF 基线之外,覆盖
Mayami 实际使用的 cgroup BPF、网络命名空间、veth、IPv4/IPv6 与策略路由。
Kprobe 相关项保留为上游兼容基线,不声称 Mayami 当前使用 kprobe 做进程追踪。

交叉编译必须先找到 pahole,合并后的配置必须满足能力契约;两种构建模式在接受
内核包前均检查最终配置、vmlinux 的非空 `.BTF` 段、包内配置及内核 Image 一致性。
片段中 `=m` 表示允许模块或内建,`=y` 必须内建。缺项停止发布,不能以 perf 打包
失败的容忍分支跳过这些检查。pahole 仅安装在构建容器,不安装到宿主机或路由器。

镜像验收还需检查 TC/veth 模块与 r8125 同版本、同签名密钥;启动后须读取
`/sys/kernel/btf/vmlinux` 并实际加载 DAE。离线检查和虚拟机测试不能替代 E52C
真机网口、PPPoE 与长期稳定性验证。


### 2026-09-16 E52C 修复成品与现场反馈

`2026.09.16-dae-btf1` 已完成 E52C 重编、实际内核 DEB 的隔离 ARM64 QEMU 启动和 DAE
初始化验收，成品传回维护工作站并核对摘要。内核 release 仍为 `6.18.50-vyos`。
后续现场确认 BTF 存在、Mayami 可运行，systemd 的缓存权限与重复实例问题另行排除。
这不等于已完成 WAN 断链根因分析、PPPoE 长期稳定性和性能验收，也不代表其他三板本轮重编。

能力分组、修复提交、压缩 Image 校验、产物摘要和证据边界见 [DAE 内核契约与复盘](../development/dae-kernel.md)。

## 2026-09-17 远程构建观察：lb build 对容器资源上限敏感

在 amd64 宿主（80 核 / 125 GiB）用 `scripts/docker-build.sh` 构建时，把 `JOBS=32 BUILD_CPUS=32 BUILD_MEMORY=64g`
传给容器,ISO 阶段在 `lb bootstrap_archives` 的 `apt-get update` 稳定失败:
`Could not read from .../packages.vyos.net_..._InRelease - getline (12: Cannot allocate memory)`,
随后 `provides only weak security information` 并中止。同一 builder 镜像直接 `docker run` 跑
`apt-get update`（无限制 / 64g / 32g）均正常;改回脚本默认的 `16 / 16 / 32g` 后 ISO 阶段顺利通过。
根因未定位（怀疑 qemu-user 下 apt 的 gpgv 拆分读取与 cgroup 上限的交互）,在查明前请保持默认资源上限,
不要为了提速把 `BUILD_MEMORY`/`BUILD_CPUS` 翻倍。此外 `git archive` 在 Windows（`core.autocrlf=true`）
上导出会把脚本转成 CRLF,向 Linux 构建机投放源码树时要加 `-c core.autocrlf=false`。

## 2026-09-17 缓存指纹修正：host 镜像身份改用 RootFS 层摘要

`scripts/docker-build.sh` 每次调用都会 `docker build` 一次 host 工具镜像。层全部命中缓存时 BuildKit
仍会给出一个新的镜像 ID（config 不同、RootFS 完全相同）。此前把这个 ID 作为 `BUILD_HOST_IMAGE_ID`
喂进内核/U-Boot 缓存指纹,结果是**每一次**调用都判定"内核输入已变"→ 重编内核 deb → deb 比 ISO 新
→ 再重建 base ISO,五板顺序构建就要重复五遍 1.5 小时。现改为 RootFS 层摘要列表的 sha256
（`rootfs:<sha256>`）:层相同即工具链相同;Dockerfile/apt 真变了层才变。远程构建当场用 `restamp.sh`
按新身份重写了已有产物的缓存戳,避免多重编一轮。

## 2026-09-17 原生 arm64 构建机（Apple Silicon + colima）实测

在 M4 Mac mini（10 核 / 16 GiB）上用 Homebrew 装 `colima` + `docker` CLI,起原生 arm64 Ubuntu 24.04 VM:
`colima start --cpu 8 --memory 10 --disk 50 --vm-type vz --arch aarch64 --mount-type virtiofs`,
仓库放在 VM 数据盘 `/mnt/lima-colima/`（根盘只有 19 GiB）,在 VM 内直接跑
`JOBS=8 BUILD_CPUS=8 BUILD_MEMORY=7g BUILDER_MEMORY=6g scripts/docker-build.sh <板>`（无 qemu,
`deps` 阶段自动跳过 binfmt 检查）。同一棵树、同一 VyOS 提交的实测:

| 阶段 | x86 + qemu（v2in0,80 核） | M4 原生（VM 8 核） |
| --- | --- | --- |
| host/builder 镜像 | 缓存 | 首次约 5 分钟 |
| 内核交叉编（cross） | ~15 分钟 | ~15 分钟 |
| base ISO（lb build） | ~1.5 小时 | **4 分钟** |
| 每板 U-Boot + 整盘 img + 每板 ISO | ~10 分钟 | ~1.5 分钟 |
| a5e 全链从零 | ~2 小时 | **28 分钟** |

结论:仿真只该作兜底,日常构建用原生 arm64（本机 VM 或 GitHub arm64 runner）。
