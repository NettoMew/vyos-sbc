#!/usr/bin/env bash
# Install an A5E disk image to an explicitly selected, unmounted NVMe.
# SD rescue is left untouched. SPI firmware installation is a separate step.
set -euo pipefail

die() { printf 'E: %s\n' "$*" >&2; exit 1; }
[[ $# == 5 && $5 == --erase ]] || die "usage: $0 IMAGE.img.xz /dev/nvmeNnN EXPECTED_SERIAL SHA256 --erase"
image=$(readlink -f -- "$1")
device=$2 serial=$3 expected=$4
[[ $EUID == 0 ]] || die 'run as root'
[[ $device =~ ^/dev/nvme[0-9]+n[0-9]+$ && -b $device ]] || die 'target must be a whole NVMe namespace'
[[ $expected =~ ^[0-9a-f]{64}$ && -f $image ]] || die 'image and explicit SHA256 required'
[[ $(tr -d '\0' < /proc/device-tree/model) == 'Radxa Cubie A5E' ]] || die 'this installer is A5E-only'
for tool in python3 sha256sum lsblk sgdisk partprobe udevadm mkfs.vfat e2fsck tune2fs mount umount losetup chroot; do
    command -v "$tool" >/dev/null || die "missing tool: $tool"
done
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
helper=$script_dir/../resources/grub-setup.py
[[ -f $helper ]] || helper=$script_dir/grub-setup.py
[[ -f $helper ]] || die 'grub-setup.py must accompany the installer'

check_target() {
    local found
    found=$(lsblk -dn -o SERIAL "$device" | xargs)
    [[ -n $serial && $found == "$serial" ]] || die "NVMe serial mismatch: $found"
    [[ $(lsblk -dn -o TYPE "$device") == disk ]] || die 'not a whole disk'
    [[ $(lsblk -bdn -o SIZE "$device") -ge 4294967296 ]] || die 'target smaller than image'
    if lsblk -nr -o MOUNTPOINTS "$device" | grep -q '[^[:space:]]'; then
        die 'target or a descendant is mounted/in use (including the running system)'
    fi
    while read -r name; do
        [[ -z $(find "/sys/class/block/$name/holders" -mindepth 1 -maxdepth 1 -print -quit) ]] || die "$name has active holders"
    done < <(lsblk -nr -o KNAME "$device")
}
check_target
printf '%s  %s\n' "$expected" "$image" | sha256sum --check --status || die 'image SHA256 mismatch'
# Before erasing anything, verify the exact image geometry and A5E SPL header.
raw_hash=$(python3 - "$image" <<'PY'
import hashlib,lzma,struct,sys,zlib
p=sys.argv[1]
with lzma.open(p,'rb') as f:
    data=f.read(2*1024**2)
    total=len(data)
    digest=hashlib.sha256(data)
    while chunk:=f.read(1024**2):
        total+=len(chunk)
        digest.update(chunk)
assert total==4*1024**3,'expected a 4 GiB A5E image'
assert data[512:520]==b'EFI PART' and data[131076:131084]==b'eGON.BT0'
h=bytearray(data[512:1024]);size,crc=struct.unpack_from('<II',h,12)
assert 92<=size<=512
struct.pack_into('<I',h,16,0);assert zlib.crc32(h[:size])==crc
lba,count,entry_size,crc=struct.unpack_from('<QIII',h,72)
entries=data[lba*512:lba*512+count*entry_size]
assert zlib.crc32(entries)==crc
assert struct.unpack_from('<Q',entries,32)[0]==32768
assert struct.unpack_from('<Q',entries,entry_size+32)[0]==557056
spl=data[131072:];crc,size=struct.unpack_from('<II',spl,12)
assert 32<=size<=len(spl) and size%4==0
words=list(struct.unpack(f'<{size//4}I',spl[:size]));words[3]=0x5f0a6c39
assert sum(words)&0xffffffff==crc
assert b'Radxa Cubie A5E\0' in spl,'not an A5E firmware image'
print('A5E image SHA256, size, GPT and SPL preflight passed',file=sys.stderr)
print(digest.hexdigest())
PY
)
check_target
printf 'ERASING %s, serial %s; SD and SPI are NOT targets.\n' "$device" "$serial"
python3 -c 'import lzma,shutil,sys; f=lzma.open(sys.argv[1],"rb"); shutil.copyfileobj(f,sys.stdout.buffer,1024**2)' "$image" | dd of="$device" bs=4M iflag=fullblock conv=fsync status=progress
readback=$(dd if="$device" bs=4M count=1024 iflag=fullblock status=none | sha256sum | cut -d' ' -f1)
[[ $readback == "$raw_hash" ]] || die 'full 4 GiB image readback mismatch; SD rescue remains untouched'
echo 'Full image write/readback SHA256 passed; assigning independent disk identities.'
sgdisk -e -G "$device"
partprobe "$device"
udevadm settle --timeout=30
p1=${device}p1 p2=${device}p2
[[ -b $p1 && -b $p2 ]] || die 'partition nodes did not appear'
# Never leave a cloned ext4 UUID or an EFI loader searching for the SD UUID.
set +e
e2fsck -f -p "$p2"
rc=$?
set -e
[[ $rc -le 1 ]] || die "filesystem check failed: $rc"
tune2fs -U random "$p2"
mkfs.vfat -F32 -n EFI "$p1"

tmp=$(mktemp -d /tmp/a5e-nvme-install.XXXXXX)
disk=$tmp/disk rootfs=$tmp/rootfs
mkdir "$disk" "$rootfs"
cleanup() {
    local path
    for path in tmp sys proc dev mnt/boot/efi mnt; do
        mountpoint -q "$rootfs/$path" && umount "$rootfs/$path" || true
    done
    mountpoint -q "$rootfs" && umount "$rootfs" || true
    mountpoint -q "$disk" && umount "$disk" || true
    # No recursive deletion: preserve evidence if a mount could not be removed.
    rmdir "$rootfs" "$disk" "$tmp" 2>/dev/null || true
}
trap cleanup EXIT
mount "$p2" "$disk"
mapfile -t squash < <(find "$disk/boot" -mindepth 2 -maxdepth 2 -type f -name '*.squashfs')
[[ ${#squash[@]} == 1 ]] || die 'expected exactly one installed image'
mount -t squashfs -o ro,loop "${squash[0]}" "$rootfs"
[[ -f $rootfs/usr/lib/live/boot/9992-sbc-media.sh ]] || die 'image lacks strict boot-medium binding'
version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$rootfs/usr/share/vyos/version.json")
[[ ${squash[0]} == "$disk/boot/$version/$version.squashfs" ]] || die 'version/layout mismatch'
mount --bind "$disk" "$rootfs/mnt"
mount "$p1" "$rootfs/mnt/boot/efi"
mount --bind /dev "$rootfs/dev"
mount -t proc proc "$rootfs/proc"
mount -t sysfs sysfs "$rootfs/sys"
mount -t tmpfs tmpfs "$rootfs/tmp"
cp "$helper" "$rootfs/tmp/grub-setup.py"
path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
chroot "$rootfs" env PATH="$path" grub-install --target=arm64-efi --no-nvram --removable --boot-directory=/mnt/boot --efi-directory=/mnt/boot/efi
chroot "$rootfs" env PATH="$path" python3 /tmp/grub-setup.py --root-dir /mnt --version "$version" --console-type ttyS --console-num 0 --console-speed 115200 --pin-boot-media
grep -q 'sbc-media-uuid=' "$disk/boot/grub/grub.cfg.d/vyos-versions/"*.cfg
sync
cleanup
trap - EXIT
sgdisk -v "$device"
e2fsck -f -n "$p2"
lsblk -o NAME,SIZE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS "$device"
echo 'NVMe installation complete. First boot grows persistence; SPI-only boot still needs firmware provisioning and hardware verification.'
