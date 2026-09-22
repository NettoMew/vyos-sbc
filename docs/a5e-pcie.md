# A5E PCIe / M.2 支持

## 当前验证版：2026.09.22-0545-a5e-nvme

已编译 U-Boot 补丁至 0075、内核补丁至 177，以及匹配的全部
`6.18.50-vyos` 模块、initramfs、整盘 xz 和升级 ISO。以下是真机证据：

- 0075 自动执行插槽电源/PERST# 时序，无需手动操作 GPIO；U-Boot 能识别并读盘。
- Linux 只读 64 MiB 两次 SHA256 一致；旧 SD 系统配新固件也已识别 NVMe。
- 经用户允许清盘后，FORESEE E2M2 64GB 完成整盘写入，完整 4 GiB 读回 SHA256 一致。
- 安装器重新分配 GPT GUID、ext4 UUID，并重建 EFI/GRUB，避免与 SD 克隆身份冲突。
- SD 提供 SPL/U-Boot，显式执行 NVMe 上的 EFI loader 后，新内核、initrd、squashfs
  均从 NVMe 启动，持久化分区也按 UUID 绑定 NVMe，达到 `Configuration success` 和登录。

09-22 10:54 补充实测：

- 先前串口失联期间，NVMe 上的 journal 证明系统继续运行约 3.57 小时；未发现 NVMe
  I/O timeout、Oops 或 panic。不能将那次串口无响应判为内核死机；串口失联根因仍未确定。
- 新版 NVMe 再次启动，串口登录和独立网络 SSH 均正常；growfs 已将 p2 扩至 57.4 GiB。
  64 MiB 随机文件 fsync 写入、两次 O_DIRECT 读回 SHA256 一致，测试文件随后删除。
- 同一 0545 版本同时装在 SD/NVMe，两种选择均验证实际内核、squashfs 和持久化盘
  使用对应 UUID；新版 SD 启动通过，原 0220 救援版本和 SD 配置保留。
- SPI 原始 16 MiB 与独立全 FF 缓冲区逐字节一致，已在电脑保存等价完整备份及取证说明。
  仅更新 906137 字节固件；整片 16 MiB 读回比较通过，未修改的尾部仍全 FF。

- 用户实际拔掉 SD 后冷启动，串口明确显示 `Trying to boot from sunxi SPI`、`MMC: no card present`，
  自动加载 NVMe EFI，再进入 0545 VyOS。Linux 中无 mmcblk0，系统/写层均来自 NVMe。
- 无 SD 普通 `systemctl reboot` 再次完成相同启动链；两次启动均通过内核/initrd/squashfs
  SHA256、SSH、64 MiB 写入/两次直接读回验证。冷/热启动 boot ID 不同，非重复读取旧日志。
- 所有 journal 文件（包括启动时被标记为 unclean 的轮转文件）执行 `journalctl --verify` 均通过；
  rsyslog active，未发现 NVMe I/O error/timeout、ext4 error、Oops/panic。
- 临时调试网络服务已从 SD 和 NVMe 的持久化写层移除，NVMe 已正常关机；正式镜像不含该服务。

- 写 SPI 后用户插回 SD：自动启动 0545、串口登录和 rsyslog 正常；命令行与持久化挂载均为
  SD UUID，NVMe 正常识别但未挂载。再次只读检查两盘调试文件均已删除，端口 2222 未监听。

**SD 启动、SPI→NVMe 无 SD 冷启动/普通重启，以及插回 SD 恢复均已通过。**
这些是本机 FORESEE E2M2 的有限实测，不代表所有 SSD 兼容性或长期压力测试完成。
另发现 U-Boot 向 SD FAT 写 16 MiB 备份时失败；已先备份整个 ESP，再在 Linux 修复 FAT，
新 SD 系统随后启动通过。该 U-Boot FAT 大文件写入问题尚未修复，不用于 SPI 备份传输。

安装方式、介质隔离和 SPI 验证步骤见 [SD / NVMe 启动](a5e-nvme-boot.md)。
下面保留调查时间线；早期的“尚未编译/写盘”等描述只对应当时状态。

## 09-22 真机进展：参考内核已读盘，新时序待集成验收

05:18 对照已出现 `/dev/nvme0n1`（120831998 个 512-byte 扇区），型号 E2M2 64GB、
固件 10100080；前八扇区只读测试成功。使用的是参考 Armbian 内核/initrd 加当前
0073 固件，不是完整原版 Armbian。先拉低 PERST#、关闭插槽供电，再由内核接管
供电的实验成功；只改 reset GPIO 极性不是充分解释（原极性配合手动供电也成功）。

内核 177 与 U-Boot 0075 因此把插槽电源改为 host 所有，保持 PERST# 至电源和
REFCLK 稳定，并在交接/关机时先复位、后撤电。两者已编译，18 个固件补丁与实际
源码逐文件一致，11 项源码测试和双份编译 DT 契约通过。**新版二进制尚待上板，
尚未完成正常重启、SPI-only 或 NVMe 安装验收；未写入 SPI/NVMe。**

以下为此前诊断过程，不能把早期失败或一次实验成功当作当前发布版本的最终结论。

用户已刷入 `2026.09.22-0220-a5e-pcie`。新日志以及 COM3 复测确认：
ComboPHY/RC 正常 probe，PCIe Gen2 ×1，`01:00.0 [1217:8760]` 是 FORESEE/O2 Micro
NVMe 控制器。但 `Identify Controller failed (16385)`，尚无 `/dev/nvme0n1`。
这不能写成“NVMe 已修复”，也不能把 PCIe 枚举等同于磁盘读写成功。

私有 trace instance 捕获到 CNS=1 的 Identify 命令和约 66 微秒后的完成，状态
`0x4001`（Invalid Opcode + DNR），不是单纯等待中断超时。运行时禁用 ASPM、降至
Gen1，均复现同样状态。PCI bus reset 后一次重探测改为超时，故不反复用总线复位
掩盖问题。用户尚未在 Armbian 上测试这块盘，未建立 SSD/参考系统的正常对照。

后续 COM3 实测的新 U-Boot（补丁至 0073）已能 Identify 这块 57.6 GiB NVMe，
并成功读取前八个扇区。SPI 的 CLDO1 1.8V 电源修正后，也能自动识别 16 MiB
w25q128fw。尚未写入 SPI 或 NVMe；Linux Identify 仍失败，不能声称完整 NVMe 启动完成。

另已实证固件交接问题：LTSSM 已关闭，APP_LINK 却保留 `0x17`，旧内核误判链路仍在。
启用 LTSSM 后，实际 Link Status 的 DL-active 恢复，PCI 端点随即重新枚举。
内核 176 / U-Boot 0074 改为检查 LTSSM 和实际 DL-active；内核修正已通过签名的临时
替代 host 模块上板验证。该修正解决端点消失，**不解决目前的 NVMe Identify 失败**。
0074 固件已编译，尚未上板；完整新版内核和镜像尚待构建。

04:55 使用用户参考镜像中原版 `6.18.52-current-sunxi64` Image、initrd 和 A5E DTB
进行一次性 initramfs 对照（仍由当前 0073 SPL/U-Boot 引导，不是原版固件全栈对照）：
PCIe Gen2 枚举正常，但同样 `Identify Controller failed (16385)`，没有 NVMe 块设备。
随后两次 U-Boot 重探测也复现 `0x4001`，此前成功读盘尚不能稳定复现。
下一步需真正断电冷启动作对照；不据此断言 SSD 损坏或宣布 NVMe 已修复。

以下“实现/限制”描述的是已发布的 0220 版本；新启动固件验收另见后续记录。

## 0145 版为什么 `lspci` 为空

用户新日志已进入 VyOS、`Configuration success`，并确认 eth0/eth1 的固件 MAC 绑定。
PCIe 是独立缺口：发布内核虽有 `CONFIG_PCI=y` / `CONFIG_BLK_DEV_NVME=y`，却没有
A523/A527 专用 PCIe RC 与 ComboPHY 驱动；传给 Linux 的 U-Boot DT 也没有 PCIe 节点。
因此不能仅靠 `modprobe nvme`，也不能只改 `/boot/.../dtbs` 里未被使用的备用 DTB。

09-22 02:51 通过 COM3 只读取证：`/proc/cmdline` 确认运行 0145 版，实际 firmware DT
没有 `pcie@4800000` / `phy@4f00000`，平台驱动列表无 sunxi PCIe/ComboPHY，`lspci` 为空。
用户确认接有 NVMe，但该盘型号及 Armbian 下枚举情况尚未提供；不能据此判定盘的好坏。

两口板载网卡走 SoC 内置 GMAC，不挂在 PCI 总线上。`NO-CARRIER` 是物理链路状态，
不等同于 PCIe 没驱动。rsyslog 的 journal 显示首次失败后已自动成功启动；只读检查时
为 `active`，使用实际 `/run/rsyslog/rsyslog.conf` 的 `-N1` 校验通过。本轮未修改日志服务，
也没有据此认定早期启动失败的原因。

## 实现

- 基于参考 Armbian 镜像的固定 build commit
  `0648ff3c4125d673c18b5f032dc7c28545c542b5`，引入内核补丁 170–174。
- 170：USB3/PCIe 共用参考时钟；171：INNO ComboPHY；172：sun55i PCIe RC。
- 173：仅移植 PCIe 相关 SoC/板级 DT，不夹带 IOMMU、SPI、显示或 vendor usbc1。
- 174：供应者尚未就绪时正确 deferred probe；WAKE# 配置为输入，不与端点争驱动。
- U-Boot 0050 使用相同的 **Linux binding**（compatible、MSI/INTx、中断映射、
  电源域、clock/reset、`pcie3v3-supply`），继续走 firmware DT，保留 SID MAC fixup。
- U-Boot **不**开启 PCI/NVMe 初始化，Linux 独占 PCIe 初始化；SD 启动链不变。
- PL11 只由插槽电源 regulator 申请，不叠加另一份 pinctrl 申请；PB6/PB7 选择 PCIe 通路。

原补丁来源和移植差异见
`boards/a5e/overlay/scripts/package-build/linux-kernel/patches/README.md`。

## 限制

PCIe 与 USB3 共用高速通道，本版选择 PCIe，USB2 保留；不是同时开启 PCIe + USB3。
见 [Radxa USB 说明](https://docs.radxa.com/en/cubie/a5e/hardware-use/usb)。
此改动使 Linux 可驱动 M.2 PCIe 设备，不等于支持无 SD 的 SPI/NVMe 引导。

新固件 DT 和新内核必须配套：本轮用完整 `.img.xz`，单独 `add system image` 不更新 U-Boot。
刷卡会清除目标卡，先备份配置。不要格式化 NVMe，也不要对 NVMe 做写入测试来验证枚举。

## 验证

`tests/a5e-pcie.py` 检查源码配置、双份 DT 一致性、Linux compatible 和 probe 修复；
给出 `--kernel-config`、`--kernel-dtb`、`--uboot-config`、`--uboot-dtb` 时还会检查真实
编译产物的属性及引用，防止“备用内核 DT 正确、实际 firmware DT 缺失”的回归。
CI 会从最终内核 deb 中取出 config/DTB，与真实 U-Boot DTB 一起验证。

本轮已生成 `2026.09.22-0220-a5e-pcie` 的整盘 `.img.xz`、ISO 和独立 SPL/BL31/U-Boot。
内核已干净重编，发布镜像通过 GPT/SPL/xz/ISO 内容校验和上述实际 DTB 契约检查。
0220 已上板验证 PCIe 端点枚举和 VyOS 启动；NVMe 块设备验收仍未通过。

真机验收必须在接好 PCIe 设备后冷启动，并记录：

```sh
show version
sudo dmesg | grep -Ei 'pci|combphy|phy@|nvme|defer|regulator'
lspci -nnk
lsblk -o NAME,SIZE,TYPE,MODEL
sudo cat /sys/kernel/debug/devices_deferred
```

若还要诊断独立的日志服务故障：

```sh
sudo systemctl status rsyslog --no-pager -l
sudo journalctl -b -u rsyslog --no-pager -n 80
systemctl show rsyslog -p ExecStart --no-pager
sudo rsyslogd -N1 -f /run/rsyslog/rsyslog.conf
```

源码和离线编译测试不代替实机 PCIe link-up、端点枚举与只读访问验收。
