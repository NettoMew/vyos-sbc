# A5E AIC8800 Wi-Fi bring-up

## 当前状态（2026-09-22）

目标是驱动为 **STA 客户端和 AP 热点两种模式**提供正常接口。用户已明确：
关联网络和配置热点交给 VyOS，本轮不做网络业务配置。**SD 正常启动及新固件的
SPI→NVMe 无 SD 冷启动、软件重启，均已通过本轮驱动验收**。

真机结果（0545 系统更新为本轮固件及签名驱动）：

- SDIO 枚举 `C8A1:0082` / `C8A1:0182`，D80 U02 固件下载成功，创建 `phy0/wlan0`。
- 实际 SDIO 为 40 MHz、4-bit、1.8 V；厂商日志的 150 MHz 是能力描述而非实际时钟。
- 模块通过强制签名验证；默认 `custregd=N`，没有放松监管域限制。
- 声明 managed/AP，接口关闭时 AP→managed 类型切换成功；正式驱动三轮被动扫描
  在 SD 下分别发现 6/7/8 个 BSS，NVMe 冷启动和重启各为 5/6/7；没有关联周围网络、
  没有保存邻居 SSID。
- 重启后重复加载成功，接口名称和 MAC 稳定；未发现 AIC 固件超时或内核 Oops。
- SD 引导区和 SPI 已更新到 0077 固件并读回比对，NVMe 持久层也已安装驱动资产。
  无 SD 冷启动确认 NVMe 介质 UUID、持久层、模块/固件校验和；软件重启串口完整记录
  `Trying to boot from sunxi SPI` → NVMe EFI → Linux，两个不同 boot ID 均完成相同检查。
  两次 NVMe 检查均无 SD 块设备、无失败 systemd 服务，接口名称与 MAC 保持一致。

新候选镜像 `2026.09.22-1150-a5e-wifi` 包含上述组件，已完成离线完整性检查。
它复用已验证的 0545 内核 Image/initrd 和用户空间，重编 AIC 模块、配对 DTB 与
U-Boot，再生成 squashfs、IMG.XZ 和 ISO；**不是全量重编内核，也尚未整镜像重刷验收**。

原系统只有 `mmc0`，`/sys/bus/sdio/devices` 为空；实际交接给 Linux 的
`/soc/mmc@4021000` 为 `disabled`，镜像也没有 AIC8800 模块和固件。
因此只安装一个驱动不能解决问题。

## 实现

- 内核补丁 `178/179`、U-Boot 补丁 `0076/0077` 配对启用 SDIO：4-bit、40 MHz，
  PL7 控制 Wi-Fi 3.3 V，PM1 为低有效复位，复位释放后等待 200 ms，PM0 为
  host-wake；BLDO1 保持 1.8 V IO 供电。
- 保持 `BOARD_DTB_OVERRIDE=0`：默认使用固件 DT，保留 SID 派生的以太网 MAC。
  **仅更新备用内核 DTB 或 ISO 不会更新旧固件的 SDIO 描述。** SD 引导区及
  SPI 中固件的更新、回退和读回校验需分别处理，不能自动覆盖已验证固件。
- `BOARD_WIFI_AIC8800=1` 启用已有板级资产流程，A5E 只选 `aic8800D80` 固件。
  共享 SDIO 兼容补丁位于 `vendor/aic8800/`，m28k 也使用同一份；不重复维护，
  不应用未参与构建的 USB／PCIe transport 补丁。
- 模块针对目标 `kernel.release` 和 `Module.symvers` 编译，核验 vermagic，
  去除调试段后再用同一内核密钥签名。保持 `MODULE_SIG_FORCE`。
- 驱动与固件只进入该板的 assets／squashfs，不污染共享基础 ISO。
  `modules-load.d` 早期加载 BSP 和 Wi-Fi 模块。
- `custregd` 默认改为 `false`，使用 cfg80211 监管规则，不替用户选择国家，
  不绕过签名 regulatory database，不解锁非标准信道。蓝牙不在本轮范围。
- 外置模块需要宿主侧内核树；默认构建模式为 `cross`，不兼容的完整
  `container` 构建计划会提前拒绝。默认板仍是 A5E，格式仍是 `.img.xz`。

接线依据保留了原作者署名的
[Armbian Wi-Fi 补丁](https://github.com/armbian/build/blob/0648ff3c4125d673c18b5f032dc7c28545c542b5/patch/kernel/archive/sunxi-6.18/patches.backports/22-Enable-wifi-on-Radxa-Cubie-A5E.patch)
和 [IO 供电补丁](https://github.com/armbian/build/blob/0648ff3c4125d673c18b5f032dc7c28545c542b5/patch/kernel/archive/sunxi-6.18/patches.backports/34-fix-wifi-regulator-cubie-a5e.patch)。
无线实测应按 [Radxa 天线说明](https://docs.radxa.com/en/cubie/a5e/hardware-use/ante)
接好天线。

## 验收门槛

1. 内核和固件 DT 的 Wi-Fi、PCIe 合约均通过，两个模块签名及 ABI 匹配。
2. 真机出现 SDIO 设备、固件下载成功、无线接口创建，重启可重复，无固件超时／Oops。
3. cfg80211/nl80211 能查询无线设备，声明 managed（STA）和 AP 模式；不创建用户网络。
4. 无线接口操作和被动扫描正常，核查监管域及可用频段，不强设国家或解除信道限制。
5. 重启重复枚举、固件加载、接口创建；检查接口名称、MAC 和内核日志。
6. 在 SD 与 SPI→NVMe 两条路径重复驱动验收，并清理调试服务；新整镜像重刷验证
   单独记录，不能以组件测试替代。

驱动验收不等于实际 STA 关联、AP 客户端收发、同一射频 AP+STA 并发、DFS、全部
频段／带宽或长期性能保证；业务配置由 VyOS 负责。未通过上述真机步骤前，不应
宣称全部启动路径均验收完成，也不能承诺任何场景都没有问题。

源码和配套 DT 检查：

```sh
python3 tests/aic8800.py
python3 tests/aic8800.py --kernel-dtb <kernel.dtb> --uboot-dtb <u-boot.dtb>
```
