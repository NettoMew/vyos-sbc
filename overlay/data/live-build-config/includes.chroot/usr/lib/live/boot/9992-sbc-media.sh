#!/bin/sh
# Opt-in for SBC disks installed side by side (e.g. SD + NVMe). GRUB supplies
# the UUID of the filesystem from which it actually loaded this menu entry.
# Without the parameter, upstream live-boot and VyOS behavior is unchanged.
# Do not scan another disk when the requested medium is absent: identical
# version names must not select another disk's squashfs or writable overlay.
SBC_MEDIA_UUID=
SBC_MEDIA_PIN=
for _sbc_arg in $(cat /proc/cmdline)
do
    case "${_sbc_arg}" in
        sbc-media-uuid=*)
            if [ "${SBC_MEDIA_PIN}" = yes ]; then
                SBC_MEDIA_UUID=invalid
                break
            fi
            SBC_MEDIA_PIN=yes
            SBC_MEDIA_UUID=${_sbc_arg#*=}
            ;;
    esac
done
unset _sbc_arg

if [ "${SBC_MEDIA_PIN}" = yes ]; then
    sbc_boot_media ()
    {
        # Only ext4-style UUIDs; never interpret arbitrary command-line paths.
        printf '%s\n' "${SBC_MEDIA_UUID}" | grep -Eq \
            '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' || return 1
        local device
        device=$(readlink -f "/dev/disk/by-uuid/${SBC_MEDIA_UUID}") || return 1
        [ -b "${device}" ] || return 1
        printf '%s\n' "${device}"
    }

    find_livefs ()
    {
        local device
        if [ -n "${LIVE_MEDIA_TIMEOUT}" ] && [ "${1}" -lt "${LIVE_MEDIA_TIMEOUT}" ]; then
            return 1
        fi
        device=$(sbc_boot_media) || return 1
        check_dev null "${device}" skip_uuid_check
    }

    find_persistence_media ()
    {
        local device
        device=$(sbc_boot_media) || return 1
        # The SBC image has one ext4 partition labelled persistence. Keep the
        # normal label check, but only on the same device as the live medium.
        probe_for_fs_label "${1}" "${device}"
    }
fi
