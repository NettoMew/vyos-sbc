# A5E 启动调查（2026-09-21～22）

## 范围与现象

### 当前状态：0545 SD / NVMe 系统、SPI-only 冷启动与重启实测通过

SPL/U-Boot、内核及全部匹配模块已重编，`.img.xz` 和 ISO 已生成并校验。
NVMe 安装完成了完整 4 GiB 读回校验；新版本已用 NVMe 的 EFI loader、内核、
squashfs 和 UUID 绑定的持久化分区进入 VyOS。NVMe 扩容至 57.4 GiB、64 MiB 写入及两次
直接读回均通过；之前串口失联期间系统实际持续运行了约 3.57 小时。新版 SD 与 NVMe
同时插入的介质隔离验证通过。SPI 已备份并写入，整片读回一致；用户实际拔掉 SD 后，
SPI→NVMe 自动冷启动和普通重启均通过，重复读写摘要一致。写 SPI 后插回 SD 的恢复启动、
正确介质挂载、双盘调试服务清理检查也已通过。
U-Boot 的 SD FAT 大文件写入失败另有记录，不能宣称其已修复。当前证据和安装方法见
[PCIe 状态](a5e-pcie.md) / [SD 与 NVMe 启动](a5e-nvme-boot.md)。
下文各时间点是历史记录，不覆盖本段的当前状态。

### 最新反馈：0145 集成版已启动，继续修复 PCIe

用户提供的新日志已进入 VyOS 登录，`sunxi-a5e-hwid` 为两口绑定固件 MAC，
并输出 `Configuration success`。这更新了下文早期“未进入用户态”的状态，
但不是新增 PCIe 二进制的验收结果。`lspci` 为空另有驱动和固件 DT 缺口，
见 [PCIe 调查与实现](a5e-pcie.md)。后续 COM3 只读检查确认 rsyslog 已自行启动，
实际配置校验通过；未改动该服务，也未判定最初失败的原因。

### 2026-09-22：源码集成与新镜像构建

已从用户参考镜像的 ext4 分区提取 `u-boot-config-target-1`、包元数据和
`/etc/armbian-release`，而非猜测当前 Armbian main。其 build commit 为
`0648ff3c4125d673c18b5f032dc7c28545c542b5`，U-Boot source commit 与本项目相同。
完整配置确认 **DRAM_CLK=936**，主线原配置为 1200；其余板级 DRAM 时序参数一致。

`boards/a5e/uboot/patches/always/` 现包含五项必需补丁：USB OS 交接、936 MHz、
CLDO3 供电、MMC 20 ms 稳定等待、A523 MMC 分频。后三项取自上述固定 Armbian commit，
保留原作者说明；不引入参考镜像二进制、不搬运与 SD 启动无关的 PCIe/SPI/NVMe 功能。
完整 SPL + TF-A BL31 + U-Boot 已从干净的隔离源码树编译成功，继续使用 GPT 的 128 KiB 偏移。
**本节是 0145 构建时的记录；现已收到该版启动成功反馈。新增 PCIe 版本仍需单独冷启动验收。**

网口改为单一命名责任：删除 A5E ifrename 服务和改名脚本；板级 udev 文件只屏蔽共享
Rockchip 规则。官方 `vyos-net-name-resolve.service` 的 ExecStartPre 运行
`sunxi-a5e-hwid.py`，此时 vyos-router 已解锁、挂载配置卷。脚本按平台地址、driver 和
DT `local-mac-address` 验证实际 MAC，只补现存 eth0/eth1 节点缺失的 hw-id；不覆盖用户
绑定、不重建删除的节点、不持久化随机地址，使用官方 ConfigTree 保留版本 footer，
原子写入并保留权限与首份 0600 备份。真正改名仍由官方 resolver 执行。

COM3 真机已验证两口的 DT MAC 与 sysfs 当前 MAC 一致、平台/驱动身份吻合。
在 `/tmp` 配置副本上使用设备里的真实 ConfigTree，已通过两口绑定、版本 footer 保留、
备份和幂等测试；**没有修改用户正在运行的 config.boot**。Linux 容器中 17 项安全回归、
27 项 build-cache、builder、xz 归档与 15 项 net-tune 测试通过；ShellCheck 按 CI 的
`-S warning` 级别通过。下方带时间的段落为调查历史，不代表新产物的当前构建状态。

交付版本 **2026.09.22-0145-a5e**：只构建 A5E，复用未改动的 6.18.50-vyos 内核 deb，
用官方流程重新生成有独立版本号的基础 ISO/initramfs，再注入板级修复生成整盘 xz 与升级 ISO。
组合固件 831,281 字节，SHA256
`1d9e6ec2550bcebc052a90f3a5028e77e5e00e9fa61ccaa3f5ddbeb98a3344a7`，
已核实与磁盘 131,072 字节处内容一致；SPL 校验和、主备 GPT CRC 均通过。
`tests/a5e-image.py <raw.img> <firmware.bin>` 提供只读布局验收。完整来源、项目源码、
编译配置、SHA256 清单随产物输出。**本轮应刷整盘 xz；升级 ISO 不更新 U-Boot。**

### 2026-09-22 01:08：物理地址闭环，确认 OHCI 遗留 DMA 写坏文件

反向对照恢复为不执行 `usb stop`，同样的原菜单 + `break=premount earlycon retain_initrd`
再次出现 udev 段错误。启动前读出的 OHCI HCCA 仍为 `0x7bf1f000` / `0x7bf2bc00`。
用 1336 字节、无 libc 的只读 ARM64 诊断程序 mmap `/usr/bin/udevadm`，读取其
`/proc/self/pagemap`（先触碰目标页，确认 present），得：

```text
pagemap=a10000000007bf1f
phys=000000007bf1f080
word=000000000000c97f
```

即 **udevadm 偏移 `0x12080` 的坏字节物理地址，恰好就是旧 OHCI HCCA + `0x80`**。
本次坏值 `7f c9 00 00`，正常值 `c0 b1 14 00`；压缩输入 SHA256 仍完全正确。
结合停止 USB 后原菜单正常启动、恢复 USB 后同地址再坏，可确认该复现中的破坏者是
**U-Boot 遗留的 OHCI DMA 帧号写回**，不是磁盘归档 xz/zst 格式问题。
这也提供了初始解压/BTF 异常的统一解释，但没有逐字节捕获最初那次 panic 的 DMA 写入，
且原始自编 SPL 无串口的更早故障仍需独立处理。

诊断源码/二进制在 `.omx/evidence/a5e-file-page.c` / `a5e-file-page`；串口传输后验证
SHA256 `02cbf4b03ba8ad8422536f89fdd161c8e16911d1e283eaca729b65ba4261e952` 才执行。
程序仅 open/mmap/read pagemap/write stdout，不操作物理内存、不写磁盘。

已加入 A5E 板级候选修复
`boards/a5e/uboot/patches/always/0001-usb-generic-quiesce-on-os-handoff.patch`：
为 generic EHCI/OHCI 增加 `DM_FLAG_OS_PREPARE`，使现有 remove 路径在交接时运行。
`lib/uboot.sh` 增加始终应用 `patches/always/*.patch`，不改变原 E52C 开核补丁的开关语义。
**尚未刷入带此补丁的新固件，不能把已验证的手动停止 USB 与源码补丁真机验收混为一谈。**

源码验证结果：固定 U-Boot commit `ece349ade2973e220f524ce59e59711cc919263f` 上
`git apply --check` 通过，使用 A5E defconfig 的 EHCI/OHCI 两个目标对象编译通过；
build-cache 27 项（含必需补丁、可选开核开关、缓存失效、失败不写 stamp）与 xz 归档回归通过。
Shell 语法、lib/uboot.sh ShellCheck 通过；动态调用 mock 的测试文件排除 SC2317 后通过。
记录 `.omx/evidence/test-logs/usb-handoff-tests.log`。只编译 A5E 相关目标对象，未重编内核/ISO，
未生成或刷写新的完整固件/镜像；原始源码缓存只读挂载，测试在一次性容器副本中运行。

反向坏启动取证后，再次重启并仅执行 `usb stop; run bootcmd`，原自动菜单第二次达到
`vyos login:`（仍有相同 hw-id 配置错误）。最终停在登录提示符，释放 COM3；未保存启动环境。
所以下次重启仍需在 U-Boot 手动执行这条临时命令，不能将当前 SD 当作已持久修复的镜像。

### 2026-09-22 01:04：USB 停止对照指向 U-Boot OHCI DMA 残留

在原菜单加 `retain_initrd` 后再次复现：`/sys/firmware/initrd` 的完整 SHA256
与离线源文件一致，但解包后的 udevadm 同一位置变为 `ee c4 00`（上一次为 `3c fc 00`）。
因此这次压缩输入至少在检查时仍正确，损坏集中于解包输出/运行期。
`retain_initrd` 的保留与 sysfs 实现已对照 [Linux 源码](https://github.com/torvalds/linux/blob/v6.18/init/initramfs.c)。

该形状符合 OHCI HCCA 的写回位置：32 个 32-bit 表项之后，偏移 `0x80` 是 16-bit
`frame_no` 和每帧归零的 16-bit padding，见 [U-Boot ohci.h](https://github.com/u-boot/u-boot/blob/v2026.07/drivers/usb/host/ohci.h)。
这目前是**有实物对照支持的推断**，尚未完成坏文件页的物理地址与 HCCA 地址对应。

U-Boot 只读寄存器实测：
- OHCI `0x04101400`：control=`0x8f`（运行中），HCCA=`0x7bf1f000`。
- OHCI `0x04200400`：control=`0x8f`，HCCA=`0x7bf2bc00`。
- 两个 HCCA 的 `+0x80` 内存字分别为 `0x0000b2db` / `0x0000b2d1`。

然后在 U-Boot 仅先执行 `usb stop`，仍走相同 bootcmd / EFI boot manager / GRUB 菜单，
保持 `break=premount earlycon retain_initrd`：initrd、udevadm、BTF 哈希全部恢复正常，
udev 成功启动。下一次重启又执行 `usb stop; run bootcmd`，**不加任何诊断参数、不进 GRUB 命令行**，
原自动菜单也越过原故障，启动 systemd 并达到 VyOS target（网口 hw-id 错误依旧，尚非整机验收通过）。

固定的 U-Boot 源码中，`ohci-generic.c` 和 `ehci-generic.c` 均只有
`DM_FLAG_ALLOC_PRIV_DMA`，没有 `DM_FLAG_ACTIVE_DMA` / `DM_FLAG_OS_PREPARE`。
[EFI ExitBootServices](https://github.com/u-boot/u-boot/blob/v2026.07/lib/efi_loader/efi_boottime.c)
调用 `dm_remove_devices_active()`，而该路径按 active/OS-prepare 标志筛选驱动；这是需要修复的交接缺口。
还需确认参考 Armbian 实际补丁集并验证最小源码修复，不能把手动 `usb stop` 写成永久修复完成。

### 2026-09-22 00:55：抓到解包后文件的 3 字节损坏

用户重启后已重新接管 COM3，日志 `.omx/evidence/a5e-serial-20260922-003555.log`。
原 bootcmd / EFI boot manager 路径的 GRUB 变量确认为 ttyS0 / 115200；版本目录没有
`dtb` / `vmlinuz-dtb` 覆盖文件。原先无输出不能简单解释成串口速率错误。

- 手动 GRUB 与增加 GRUB `debug=linux` 的原菜单均可进入 `rdinit=/bin/sh`。
- 去掉 GRUB debug、原菜单仅加 `panic=10` 时，越过 initrd/BTF 初始化，随后多个
  initramfs 命令 `Segmentation fault`，最终找不到 live medium。此故障在网口配置前。
- 用原菜单加 `break=premount earlycon`（不带 `panic=`）保留出错现场。
  注意本 initramfs 的 `panic=` 会让 break 点自动重启，而不是进入交互 shell。
- 故障现场只读、禁止 journal replay 挂载 SD 分区，initrd 与 vmlinuz 的 SHA256
  仍匹配下面的离线基准；本次运行中的 BTF 也匹配。BusyBox、blkid、libc 和动态加载器均匹配。
- **内存根文件系统 `/usr/bin/udevadm` 的 SHA256 稳定不匹配**：
  正常 `af4165eaea19c0814f26f4e064d05b40e78613107fc45c77b64cfe0dc5324d73`；
  故障 `d0151546f0d9a9871bd732c81f846b76097a4da2c4ef86e082af0c30f2409230`。
- 逐段缩小并从串口取回 4 KiB 页，页 SHA256 校验通过，差异仅在文件偏移
  `0x12080..0x12082`：`c0 b1 14` 变为 `3c fc 00`。把这页替换进离线原文件后，
  重构出的完整文件 SHA256 与板上故障文件一致，排除了仅串口显示错误的解释。
  首次 base64 传输确有串口错误，已丢弃；使用第二次、哈希验证通过的数据。
- 先备份故障文件到 RAM `/tmp/udevadm.bad`，**仅在 initramfs RAM 文件中恢复这 3 字节**，
  整文件 SHA256 恢复原值，`udevadm --version` 从段错误恢复为正常输出 `252`。
  未修改 SD 上的 initrd、内核或引导配置。这是局部因果验证，不是正式修复。

已确认：至少这次 udevadm 崩溃由启动后可见的文件内容损坏引起，且 SD 源文件校验正常。
尚未确认：损坏发生在加载、解压还是后续运行阶段；不能直接判定 DDR、GRUB、EFI 或驱动。
证据：`.omx/evidence/udevadm-reference.bin`、`udevadm-bad-page18.bin`、
`udevadm-corruption-diff.json`。只构建 A5E / xz 默认的约束不变；未启动全量构建。

### 最新真机进展：COM3 直启已登录，另有网口配置问题

用户授权接管 COM3 / 115200 / 8N1 / 无流控；串口日志保存在
`.omx/evidence/a5e-serial-20260921-234018.log` 与 `...-234247.log`。

- 用户实测 initrd 读入 `0x48000000` 后 CRC `88666398`，等待后复查仍相同；
  vmlinuz CRC `950676de`。接管后再次验证，并用 U-Boot `unzip` 解到 `0x42000000`：
  大小 `0x1fae200`，CRC `2b626254`，与离线原始 Image 一致。
- 从 `${fdtcontroladdr}` 复制控制 DTB 到 `0x4fa00000`，没有编辑原控制 DTB；
  保持原 VyOS 启动参数，仅加 `panic=10` 便于故障后恢复。
- `booti 42000000 48000000:1d1c5d4 4fa00000` 绕过 EFI/GRUB；U-Boot 实际将
  initrd 搬到 `0x462e3000..0x47fff5d3`，DTB 搬到 `0x49fed000`。
- 本次没有 initrd 解压失败或 BTF panic，8 核上线，`Run /init as init process`，
  随后出现 `Welcome to VyOS 2026.09.17-1715-sbc (rolling)` 并启动 systemd。
  已用默认账户登录；运行约 5 分钟无 panic。配置/网口验收未通过，不能写成全部可用。
- 登录后 `/sys/kernel/btf/vmlinux` 的 SHA256 为
  `9cebb1370b96d2a47e4af3926c940030edf2effc8871f5d985d938f9f0b91097`，
  与离线从同一 Image 提取的 BTF 完全一致。
- 结论仅是**直接 booti 的本次运行通过原故障点**；差异包括 EFI/GRUB 和内存布局，
  不能据此直接宣布 GRUB 是根因或彻底排除 DDR/缓存问题。PL11 冲突仍存在但未阻止进入用户态。
- 未刷写固件、未 `saveenv`、未修改磁盘启动配置；正常用户态启动会写持久分区，
  首次启动的 growfs 服务也已运行，不能将整个过程称为磁盘只读。

第二次直启把 Image 放到 `0x64200000`（根据原 panic 的物理 `swapper_pg_dir=0x65c6c000`
减去相对 Image 的符号偏移 `0x1a6c000`，推得的原 EFI 内核物理起点），CRC 仍匹配。
initrd 在 `0x70000000` 校验匹配；临时 `bootm_size=0x38000000` 后，`booti` 将其搬至
`0x762e3000..0x77fff5d3`，DTB 至 `0x762d0000`。再次越过原故障点，运行 `/init` 和 systemd。
这增加 EFI 路径相关问题的嫌疑，但不是完整内存压力测试或已确认软件根因。

进一步对照（串口 `...-234906.log`、`...-235740.log`）：

1. 同一 Image/initrd，经 `bootefi 42000000:1fae200 48000000:1d1c5d4 4fa00000`
   直接 EFI 启动，参数增加 `rdinit=/bin/sh`，成功进入 initramfs shell；原解压/BTF 错误均未出现。
   EFI 本身不是必然失败。该命令的 initrd 参数已用实际固件 `help bootefi` 核实。
2. 从 ESP 手动加载原 GRUB（`2.06-13+deb12u2`），GRUB `hashsum --hash sha256`
   对 initrd/vmlinuz 校验与离线一致；`--uncompress` 对内核得
   `8b0f58e232e3d7677d3cb432f396c3a219e977ede7660698bb128f6c6767df5e`，与原始 Image 一致。
3. 随后 GRUB 手动 `linux` / `initrd` / `boot`，同样增加 `panic=10 rdinit=/bin/sh`，
   **也成功进入 initramfs shell**。GRUB debug 输出内核加载缓冲区 `0x6a0b4000`，
   initrd `0x68397000..0x6a0b35d3`；不等同于 EFI stub 最终内核地址。

因此“GRUB 必然损坏文件/EFI 必然失败”均不成立，**根因仍未确认**。
下一步复测原自动 bootcmd 路径及完全断电启动，区分执行时序、内存分配、冷/热启动和间歇性问题。
GRUB 还报 `efi_uga.mod` 缺失、`serial port com0 isn't found`；它实际使用 EFI 控制台仍可操作，
不能仅凭这些非致命错误解释原 panic。GRUB 固件串口长命令不能全速粘贴（RX FIFO 会丢尾部），
已把诊断串口工具改成逐字符间隔 5ms，并用完整回显/启动参数确认命令。

2026-09-22 00:00 再次重启后，执行原 `run bootcmd`（`run distro_bootcmd`），可见
`Scanning mmc 0:1` 后经 **EFI boot manager** (`Booting: Label: mmc 0 Device path: ...`)
进入 GRUB。默认倒计时结束仅显示 `Booting 2026.09.17-1715-sbc`，后续串口无输出，
Ctrl-C 也没有可见响应；这不同于手动 `load ... BOOTAA64.EFI; bootefi ...` 的入口。
暂不能区分卡住与默认控制台配置变化，尚需复位并检查实际 GRUB 变量、禁用 boot manager
的 RAM 内对照以及断电复现；**未修改磁盘引导配置/固件**。

#### 网口配置错误的独立证据

`sunxi-a5e-ifrename.service` 确实先按驱动把 e2/e3 改为 eth0/eth1，脚本不是没运行。
之后 `vyos-router` 在配置挂载完成后启动官方 `vyos-net-name-resolve.service`：

- `/run/vyos-net-name-resolve.json`: `configured={}`，`pending_unresolved=[eth0, eth1]`。
- 两个配置节点都无 `hw-id`，又有两个未绑定设备，官方实现为避免错绑**不猜配对**，
  留空两个 pending 节点，将真实设备重新命名为 eth2/eth3。
- MAC：gmac0/dwmac-sun8i `02:10:0c:7b:dc:2d`；gmac1/dwmac-sun55i `12:10:0c:7b:dc:2d`。
  这些值属于本板，不能硬编码进通用镜像。
- 最后出现 `Configuration error`；两个设备当时均 `NO-CARRIER`，未验证网络收发。

后续应在配置挂载后、官方命名服务前，按本板确定的设备身份初始化**缺失的** hw-id，
尊重已有用户绑定；不要只重复 rename，也不要禁用官方命名服务掩盖问题。尚未实现此修复。

#### 已验证的临时低地址直启步骤

仅限本次 1 GiB A5E 固件/文件版本，在 U-Boot 提示符操作，各步报错立即停止。
这是 RAM 内测试，不是永久启动配置；启动用户态后仍会正常写持久分区。

```text
load mmc 0:2 48000000 /boot/2026.09.17-1715-sbc/vmlinuz
unzip 48000000 42000000 4000000
crc32 42000000 1fae200
load mmc 0:2 48000000 /boot/2026.09.17-1715-sbc/initrd.img
crc32 48000000 1d1c5d4
fdt move ${fdtcontroladdr} 4fa00000 10000
setenv bootargs boot=live rootdelay=5 noautologin net.ifnames=0 biosdevname=0 vyos-union=/boot/2026.09.17-1715-sbc console=ttyS0,115200 panic=10
booti 42000000 48000000:1d1c5d4 4fa00000
```

Image CRC 应为 `2b626254`，initrd CRC 应为 `88666398`。
命令参考：[unzip 实现](https://github.com/u-boot/u-boot/blob/v2026.07/cmd/unzip.c)、
[booti 文档](https://docs.u-boot.org/en/latest/usage/cmd/booti.html)。

### 先前 EFI/GRUB 路径：已越过 U-Boot，但未进入 VyOS 用户态

用户提供了带 Armbian 固件标记的完整启动日志：SPL 检出 **1 GiB DRAM**，BL31/EFI 进入
`6.18.50-vyos`；**8 核上线**，两个 dwmac 控制器开始 probe。但这不是系统启动成功：

1. `Initramfs unpacking failed: ZSTD-compressed data is corrupt`。
2. 随后 `btf_find_by_name_kind+0x90/0x148` 在 `bpf_dummy_struct_ops_init` 路径发生 Oops，
   `Attempted to kill init! exitcode=0x0000000b` 导致 panic。
3. `regulator-pcie-vcc3v3` 对 PL11 的重复占用另需排查，但发生在 initrd 损坏之后，不应直接拿它解释首故障。

同一 GPT + 128 KiB 布局已走到内核，因此不能再把它列为这次停机的首要嫌疑。
参考固件有助于推进启动，但尚未达到真机可用验收，也尚未复现成最小源码补丁。

### 启动文件离线复核

从实际 `armbian-uboot-test.img.xz` 解压出的磁盘经**只读 loop + debugfs**提取：

| 文件 | 字节数 | CRC32（供 U-Boot 对照） | SHA256 |
|---|---:|---|---|
| `/boot/2026.09.17-1715-sbc/initrd.img` | 30524884 (`1d1c5d4`) | `88666398` | `87fd3be7f57eca555c509ae5709631b6d316e5fec5bbfbf1c26b39dd298f32ff` |
| `/boot/2026.09.17-1715-sbc/vmlinuz` | 12569326 (`bfcaee`) | `950676de` | `db7141930fdf7901bc41c6134bc71a5b5fa870ac5928d54aa5700c72ee95809e` |

- initrd 与板级 squashfs 中的原件相同，ZSTD 完整解压为 53,331,456 字节 CPIO，1223 个条目，包含 `/init`。
- vmlinuz 与 squashfs 及原始 linux-image deb 相同；gzip 完整解压为 33,219,072 字节 ARM64 Image。
- 从 Image 的 `__start_BTF..__stop_BTF` 提取 5,447,644 字节 BTF，类型表边界、122,893 个类型及
  类型/成员/参数名称偏移检查均通过。这不是 BTF 运行时语义的全面验证。
- 对照实物内核反汇编，故障指令是从类型指针读取 kind 字节。日志类型 ID `0xd035`（53301）
  对应文件中的正常指针应为 `ffff8000816f91c8`，当时却从指针表读出 `ffff8000967a2128`。
  结合更早的 initrd 解压损坏，优先调查装载后内存数据被破坏；**DDR 不稳定、装载/缓存问题或软件写越界
  尚未区分，不能直接宣布硬件坏了，也不要通过关闭 BTF 掩盖问题**。

### 已执行的 U-Boot 只读文件校验（保留复现步骤）

若能停在 U-Boot 命令行，以下命令仅读 SD 文件到空闲低位 RAM 并计算 CRC，不写 SD/eMMC。
适用于本日志的 1 GiB A5E，在启动内核之前操作；若 `load` 失败或长度不符，不继续猜设备号，先收集 `mmc list`。

```text
load mmc 0:2 48000000 /boot/2026.09.17-1715-sbc/initrd.img
crc32 48000000 ${filesize}
```

期望读取 30524884 字节，CRC `88666398`。等几秒不重新 load，再执行一次同一 CRC 命令。
然后验证内核压缩文件：

```text
load mmc 0:2 48000000 /boot/2026.09.17-1715-sbc/vmlinuz
crc32 48000000 ${filesize}
```

期望读取 12569326 字节，CRC `950676de`。这些命令只写易失 RAM，不执行 `saveenv` / `mmc write`。
另需完全断电冷启动复现，记录是否每次同一报错/地址；CRC 正常也不能排除后续 EFI/GRUB 或运行期内存损坏。

---

- 用户报告 Armbian 能启动，`2026.09.17-1715-sbc` 的 VyOS A5E 镜像没有 SPL/U-Boot 输出。
- **当前只打包 A5E**，不自动编译其他板或 `make all`。裸 `make` 和 CI 默认设备为 A5E。
- 整盘归档改为 `.img.xz`（`XZ_LEVEL=6`）；Docker 镜像缓存仍用 zstd，二者无关。
- 暂未确认刷写介质、是否先解压、串口设置和是否真正完全没有字节。不能把猜测写成已修复。

## 本地取证

已检查用户指定的解压镜像：
`Armbian_community_26.11.0-trunk.52_Radxa-cubie-a5e_trixie_current_6.18.52_minimal.img`。
其启动区与 Downloads 中同名 `.img.xz` 的解压内容一致。

| 项目 | VyOS 旧 A5E 镜像 | 用户的 Armbian 镜像 |
|---|---|---|
| 分区表 | GPT，ESP 从 16 MiB 开始 | MBR，首分区从 4 MiB 开始 |
| SPL 起点 | 128 KiB（sector 256） | 8 KiB（sector 16） |
| 启动头 | eGON.BT0，校验和正确 | eGON.BT0，校验和正确 |
| SPL 长度 | 49,152 字节 | 49,152 字节 |
| U-Boot | 2026.07-gece349ade297 | 2026.07_armbian，源码标记 Sece3，补丁标记 P2ee6 |
| 固件完整长度（SPL + FIT） | 831,281 字节 | 914,465 字节 |
| BL31 字符串 | v2.13.0(debug):e019f64 | v2.13.0(debug):armbian |
| SPL 中 CLDO3 提示字符串 | 无 | 有 `PMIC: enabling CLDO3` |

旧镜像内 128 KiB 处的固件与构建机 `work/uboot/a5e/u-boot-sunxi-with-spl.bin`
逐字节一致。固件 SHA256：
`d659bd2c7748f966951bce7a8594e9f12369e0b15bd60815b9b5d56426fa758a`。

从参考镜像按 eGON 长度和 FIT totalsize 提取的完整固件 SHA256：
`e5d92097fcd549232acc90173a8300bace48d896880f1a95b0f4025ec1a65f68`。

这些结果排除了“发布镜像漏写 U-Boot / 启动头校验和算错”。它们**不能**证明卡上写入正确，
也不能证明 BootROM 已经执行 SPL、DDR 能训练成功，或串口设置正确。

## 与上游实现的关系

- [U-Boot sunxi 文档](https://docs.u-boot.org/en/latest/board/allwinner/sunxi.html)
  说明较新的 sunxi SoC 可从 128 KiB 启动，以避开 GPT。不能仅因与 Armbian 的 8 KiB 不同就判错，
  更不能在现有 GPT 的 8 KiB 直接加写一份固件（会覆盖 GPT 表项）。
- [Armbian sunxi64 写盘实现](https://github.com/armbian/build/blob/main/config/sources/families/include/sunxi64_common.inc)
  使用 8 KiB。两份镜像的布局不同是可实测的对照变量，不是已确认根因。
- [Armbian A5E defconfig 补丁](https://github.com/armbian/build/blob/main/patch/u-boot/v2026.07-sunxi64/board_radxa-cubie-a5e/edit-radxa-cubie-a5e-defconfig.patch)
  将 DRAM 频率设为 936 MHz，而我们的未修改主线 Kconfig 默认为 1200 MHz。
- Armbian 还维护 [CLDO3 供电补丁](https://github.com/armbian/build/blob/main/patch/u-boot/v2026.07-sunxi64/sunxi-board-cldo3-fix.patch)
  和 [A523 MMC 时钟补丁](https://github.com/armbian/build/blob/main/patch/u-boot/v2026.07-sunxi64/mmc-sunxi-a523-emmc-fix.patch)。
  用户提供的二进制确有 CLDO3 提示；不能把当前 main 的所有补丁自动认定为该镜像的实际补丁集。
- 当前 Armbian main 还有 DRAM 参数回退补丁，但参考镜像中没找到其回退提示字符串，故不声称它已包含该补丁。

DRAM/读卡问题一般有更早的 SPL 串口信息，仍需用户确认实际停在哪一行。
当前没有充分证据直接给内核/TF-A打补丁，未改变默认固件或写盘偏移。

## xz 基线对照

旧 A5E 镜像仅重新压缩为 `.img.xz`，没有重新编译内核、ISO 或其他板。
转换前后完整 4 GiB 原始磁盘 SHA256 均为：
`fdc91c068b5578991a7ce5c6206688d3cd07045d0799e8ba9adcc85954649883`。

因此这份 xz 是**刷写格式对照**，不是启动修复版。烧录后若仍无输出，继续查固件/BootROM，
而不是重复全量编译 VyOS。

后续应逐个改变变量：先确认同一张卡、正确 `.img` 内容和 115200 8N1 无流控；
必要时只替换参考镜像的 SPL+BL31+U-Boot，保留 VyOS 分区和系统不变，作为明确标记的测试镜像。
参考固件不能据此直接成为正式发行依赖；对照成功后应回到固定源码和最小补丁集复现。

## 已生成的固件对照测试版

`vyos-2026.09.17-1715-sbc-radxa-cubie-a5e-armbian-uboot-test.img.xz`
只将 128 KiB 处的 914,465 字节替换为从用户参考镜像提取的固件（含控制 DTB）。
替换前后，对**该区间以外的全部磁盘字节**重新计算 SHA256，结果一致：
`011f4386808546e5506ed0ee459ea964f090dc61d3c936ab528c6abc93a75310`。
所以 GPT、ESP、VyOS 内核及根文件系统均未改变；旁边的 `.provenance.json` 记录来源和修改范围。

这是本地诊断产物，**最新真机结果是已进入内核但 panic（见文首），不是正式固件依赖，也没有改动默认 U-Boot 构建配方**。

- 原版 xz 有输出：优先核实之前的解压/刷写流程；不代表固件所有功能正确。
- 原版无输出、参考固件版有输出：将问题缩小到 SPL/BL31/U-Boot/控制 DTB 差异，继续按日志定位。
- 两版均无输出、Armbian 原镜像仍能启动：继续查介质读回和 BootROM 布局兼容性，不能直接认定 DDR 问题。
- 有 SPL、停在 DRAM / MMC / BL31：保留完整串口日志，再选对应最小补丁；不要为此重编整个 VyOS 内核。

## 本次验证

- Shell 语法和改动脚本的 ShellCheck 通过。
- 原生 Linux 容器中通过：image-archive（真实 xz 往返、校验、保留/删除 raw、失败不覆盖成品）、
  build-cache（26 项）、builder、kernel-features、r8125-source、net-tune（15 项）测试。
- `make -n` 只输出 `scripts/build.sh a5e`；A5E dry-run 显示 `.img.xz`。
- builder mock 中修正了上一会话遗留的旧 image-ID / rtl8125 信任目录断言，匹配已有的
  RootFS-layer 缓存身份 / TF-A 目录；增加 `XZ_LEVEL` Docker 环境透传断言。
- 本次没有重编任何其他板，也未启动新的内核/ISO 全量构建。
