#!/usr/bin/env bash
# lib/uboot.sh — 主线 U-Boot 交叉编译（宿主机，aarch64-linux-gnu-）。
#
# 启动固件（BL31 / DDR blob / SCP）由家族文件 families/<BOARD_FAMILY>.conf 负责：
# 它声明产物名与写盘偏移，并实现 family_firmware_inputs（缓存输入）与
# family_firmware_prepare（选 blob 或现编，填 FIRMWARE_MAKE_ARGS）。本文件对家族零 if。
#
# 板级 U-Boot 源注入 = 文件投放：boards/<board>/uboot/ 镜像 U-Boot 源码树结构，
# 构建前 rsync 进去（e20c 纯主线无此目录；m28k 的 DTS/defconfig 走这里）。

# 源版本、家族声明、板级覆盖、开核开关及实际固件输入共同决定缓存。
uboot_inputs_digest() {
  {
    git -C "${UBOOT_SRC}" rev-parse HEAD || return
    printf '%s\0' "${BOARD_FAMILY}" "${BUILD_HOST_IMAGE_ID:-native}"
    aarch64-linux-gnu-gcc --version || return
    aarch64-linux-gnu-ld --version || return
    printf '%s\0' "${BOARD}" "${BOARD_UBOOT_DEFCONFIG}" "${BOARD_UNLOCK_CORES:-0}"
    family_firmware_inputs || return
    build_input_files "${LIB_DIR}/uboot.sh" "${FAMILY_CONF}" "${BOARDS_DIR}/${BOARD}/uboot"
  } | sha256sum | cut -d' ' -f1
}

stage_uboot() {
  section "U-Boot（${BOARD}：${BOARD_UBOOT_DEFCONFIG}）"

  local artifact="${UBOOT_OUT_DIR}/${UBOOT_ARTIFACT}"
  local stamp="${UBOOT_OUT_DIR}/inputs.sha256" digest
  digest="$(uboot_inputs_digest)" || return
  if [[ "${REBUILD_UBOOT:-0}" != "1" && -s "${artifact}" && -f "${stamp}" && "$(cat "${stamp}")" == "${digest}" ]]; then
    log "U-Boot 输入未变，跳过（REBUILD_UBOOT=1 强制重编）：${artifact}"
    return 0
  fi
  run rm -f "${stamp}" "${UBOOT_SRC}/${UBOOT_ARTIFACT}" || return

  # 固件：家族决定（rkbin 选 blob / TF-A 现编 …），结果是 U-Boot make 变量。
  FIRMWARE_MAKE_ARGS=()
  family_firmware_prepare || return

  # 源码树复位 + 当前板的源注入（保证板间互不渗漏）。boards/<b>/uboot/ 是镜像 U-Boot 源
  # 树结构的“文件覆盖”（m28k 的 DTS/defconfig 走这里），但其下 patches/ 子目录是“补丁库”
  # 非源覆盖 —— rsync 排除它，避免把补丁文件复制进 U-Boot 树（补丁由下方 git apply 应用）。
  run git -C "${UBOOT_SRC}" checkout -- . || return
  run git -C "${UBOOT_SRC}" clean -fdq || return
  if [[ -d "${BOARDS_DIR}/${BOARD}/uboot" ]]; then
    log "注入板级 U-Boot 源：boards/${BOARD}/uboot/（排除 patches/）"
    run rsync -a --no-owner --no-group --exclude='patches/' "${BOARDS_DIR}/${BOARD}/uboot/" "${UBOOT_SRC}/" || return
  fi

  # 必需修复独立于可选开核：patches/always/*.patch 始终应用，且包含在输入指纹中。
  # 不把 A5E 的 USB DMA 交接修复挂在 BOARD_UNLOCK_CORES 上，也不改变 E52C 开关语义。
  local pdir="${BOARDS_DIR}/${BOARD}/uboot/patches" p
  for p in "${pdir}/always/"*.patch; do
    [[ -f "${p}" ]] || continue
    log "U-Boot 必需修复：git apply $(basename "${p}")"
    run git -C "${UBOOT_SRC}" apply "${p}" || return
  done

  # RK3582 开核（feature-flag 门控，与 lib/r8125.sh 的 BOARD_R8125 同构）：默认开。
  # 砍核全发生在 U-Boot ft_system_setup()（读 OTP 后套市场分级策略）；补丁把三段分级
  # 策略 #if 0 掉，放出 efuse 实测为好的核 + GPU，保留 OTP 对单颗真坏核的屏蔽。真 RK3588S2
  # 上 cpu-code≠0x3582 → 空操作。boards/<b>/uboot/patches/*.patch 按 ls 序 git apply
  # （与 vyos-build 内核 patches/*.patch glob 同构；e20c/m28k 无此目录则跳过）。
  if [[ "${BOARD_UNLOCK_CORES:-0}" == "1" ]]; then
    [[ -d "${pdir}" ]] || fatal "BOARD_UNLOCK_CORES=1 但缺补丁目录：${pdir}"
    for p in "${pdir}/"*.patch; do
      [[ -f "${p}" ]] || continue
      log "开核：git apply $(basename "${p}")"
      run git -C "${UBOOT_SRC}" apply "${p}" || return
    done
  fi

  run make -C "${UBOOT_SRC}" mrproper || return
  run make -C "${UBOOT_SRC}" "${BOARD_UBOOT_DEFCONFIG}" || return
  run make -C "${UBOOT_SRC}" -j"${JOBS}" CROSS_COMPILE=aarch64-linux-gnu- \
    "${FIRMWARE_MAKE_ARGS[@]}" || return

  [[ -f "${UBOOT_SRC}/${UBOOT_ARTIFACT}" ]] || [[ "${DRY_RUN:-0}" == "1" ]] \
    || fatal "U-Boot 构建结束但缺 ${UBOOT_ARTIFACT}"
  run install -Dm644 "${UBOOT_SRC}/${UBOOT_ARTIFACT}" "${artifact}" || return
  [[ "${DRY_RUN:-0}" == "1" ]] || printf '%s\n' "${digest}" > "${stamp}"
  log "U-Boot 产物：${artifact}"
}
