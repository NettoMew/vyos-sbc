#!/usr/bin/env bash
# lib/env.sh — 在 build.conf 与 boards/<board>/board.conf 之后 source，
# 派生全部路径/全局量。board 可为空（只跑板无关阶段时）。

# --- 路径 ----------------------------------------------------------------------
WORK_DIR="${WORK_DIR:-${PROJECT_ROOT}/work}"
OUT_DIR="${OUT_DIR:-${PROJECT_ROOT}/out}"
STATE_DIR="${WORK_DIR}/state"
MNT_DIR="${WORK_DIR}/mnt"

VYOS_BUILD_TREE="${WORK_DIR}/vyos-build"
UBOOT_SRC="${WORK_DIR}/src/u-boot"
RKBIN_SRC="${WORK_DIR}/src/rkbin"
TFA_SRC="${WORK_DIR}/src/arm-trusted-firmware"   # Allwinner 板的 BL31 源（families/sunxi.conf）
ISO_KEEP_DIR="${WORK_DIR}/iso"

OVERLAY_DIR="${PROJECT_ROOT}/overlay"
BOARDS_DIR="${PROJECT_ROOT}/boards"
FAMILIES_DIR="${PROJECT_ROOT}/families"
RESOURCES_DIR="${PROJECT_ROOT}/resources"

# 构建 flavor 名 = overlay/data/build-flavors/sbc.toml
FLAVOR="${FLAVOR:-sbc}"

# --- vyos-build 克隆来源自动探测 -------------------------------------------------
if [[ -z "${VYOS_BUILD_REPO}" ]]; then
  local_sibling="$(cd "${PROJECT_ROOT}/../.." 2>/dev/null && pwd)/vyos-build"
  if [[ -d "${local_sibling}/.git" ]]; then
    VYOS_BUILD_REPO="${local_sibling}"
  else
    VYOS_BUILD_REPO="https://github.com/vyos/vyos-build"
  fi
  unset local_sibling
fi

# --- 板级派生（BOARD 为空则跳过）-------------------------------------------------
if [[ -n "${BOARD:-}" ]]; then
  : "${BOARD_SOC:?board.conf 必须设置 BOARD_SOC}"
  : "${BOARD_UBOOT_DEFCONFIG:?board.conf 必须设置 BOARD_UBOOT_DEFCONFIG}"
  : "${BOARD_IMAGE_PREFIX:?board.conf 必须设置 BOARD_IMAGE_PREFIX}"
  BOARD_SERIAL_CONSOLE="${BOARD_SERIAL_CONSOLE:-ttyS0}"
  BOARD_SERIAL_BAUD="${BOARD_SERIAL_BAUD:-1500000}"

  # ttyS0 → CONSOLE_TYPE=ttyS CONSOLE_NUM=0（VyOS grub 变量按此拆分）
  CONSOLE_TYPE="${BOARD_SERIAL_CONSOLE%%[0-9]*}"
  CONSOLE_NUM="${BOARD_SERIAL_CONSOLE#"${CONSOLE_TYPE}"}"

  UBOOT_OUT_DIR="${WORK_DIR}/uboot/${BOARD}"

  # 板级资产暂存（C2）：aic8800/r8125/oled 阶段把"该板专属"的内核模块/固件/二进制/
  # modules-load.d 产到这里（镜像 rootfs 目录结构），image 阶段 host 侧解包 base
  # squashfs 后只注入本板这一份 → 每板镜像只带自己的资产，base ISO 保持板无关。
  BOARD_ASSETS_DIR="${WORK_DIR}/board-assets/${BOARD}"

  # 每板 ISO 中转（imgiso 阶段）：image 阶段把"注入本板资产后的 squashfs"（+ DTB
  # override 板的内核 DTB）落到这里，imgiso 阶段拿它换进 base ISO 的 live/，remaster
  # 成可被 VyOS `add system image` 原地升级的每板 ISO。
  BOARD_ISO_DIR="${WORK_DIR}/board-iso/${BOARD}"

  # SoC 家族 = families/<BOARD_FAMILY>.conf（声明式，与 boards/ 同构）：它给出启动固件的
  # 来源与产物（UBOOT_ARTIFACT / UBOOT_IMAGE_OFFSET_KIB / KERNEL_DTB_FAMILY_GLOB）并实现
  # family_* 钩子（取源、缓存输入、选 blob 或现编 BL31、按 SoC 派生）。引擎对家族零 if：
  # 加一个 SoC 家族 = 加一个文件，加一块板 = 写 board.conf 指向家族。契约见 families/rockchip.conf。
  : "${BOARD_FAMILY:?board.conf 必须设置 BOARD_FAMILY（families/ 下的家族名，如 rockchip、sunxi）}"
  FAMILY_CONF="${FAMILIES_DIR}/${BOARD_FAMILY}.conf"
  [[ -f "${FAMILY_CONF}" ]] || fatal "未知家族 BOARD_FAMILY=${BOARD_FAMILY}（缺 ${FAMILY_CONF}）"
  # shellcheck source=/dev/null
  source "${FAMILY_CONF}"
  family_soc_config "${BOARD_SOC}"
fi

# --- 运行时解析（fetch 后才有值）--------------------------------------------------
resolved_kernel_version() {
  # 内核版本以 work 树里的 defaults.toml 为准（与官方包生态严格一致）
  [[ -f "${VYOS_BUILD_TREE}/data/defaults.toml" ]] || { echo "<unresolved>"; return; }
  awk -F'"' '/^kernel_version/ {print $2; exit}' "${VYOS_BUILD_TREE}/data/defaults.toml"
}

kernel_deb_glob() {
  local kv; kv="$(resolved_kernel_version)"
  echo "${VYOS_BUILD_TREE}/packages/linux-image-${kv}-vyos_*_arm64.deb"
}

iso_state_file() { echo "${STATE_DIR}/iso-path"; }

current_iso() {
  # 最近一次成功构建并归档的 ISO；不存在（含 state 记录的路径已失效，如 work/ 被搬过）返回空。
  # 必须以 0 退出：调用方 `iso="$(current_iso)"` 在 set -e 下，非零会让整个构建静默退出。
  local f; f="$(iso_state_file)"
  [[ -f "${f}" ]] || return 0
  local p; p="$(cat "${f}")"
  [[ -f "${p}" ]] && echo "${p}"
  return 0
}
