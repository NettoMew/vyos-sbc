#!/usr/bin/env python3
"""Opt-in GRUB/live-boot medium binding, including fail-closed selection."""
from pathlib import Path
import os
import shlex
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'overlay/data/live-build-config/includes.chroot/usr/lib/live/boot/9992-sbc-media.sh'
UUID = '11223344-5566-7788-99aa-bbccddeeff00'


class BootMedia(unittest.TestCase):
    def shell(self, cmdline, command, block=False):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory) / 'medium'
            if block:
                try:
                    os.mknod(device, stat.S_IFBLK | 0o600, os.makedev(1, 7))
                except (PermissionError, AttributeError):
                    self.skipTest('block-node fixture requires a privileged Linux test container')
            code = '''
cat() { if [ "$1" = /proc/cmdline ]; then printf '%s\\n' "$CMDLINE"; else command cat "$@"; fi; }
readlink() { [ "$1" = -f ] && [ "$2" = "/dev/disk/by-uuid/$EXPECTED_UUID" ] || return 1; printf '%s\\n' "$DEVICE"; }
check_dev() { printf 'LIVE:%s:%s:%s\\n' "$1" "$2" "$3"; }
probe_for_fs_label() { printf 'PERSIST:%s:%s\\n' "$1" "$2"; }
find_livefs() { echo UPSTREAM_LIVE; }
find_persistence_media() { echo UPSTREAM_PERSIST; }
'''
            code += '. ' + shlex.quote(str(SCRIPT)) + '\n' + command
            env = dict(os.environ, CMDLINE=cmdline, DEVICE=str(device), EXPECTED_UUID=UUID)
            result = subprocess.run(['sh', '-c', code], env=env, text=True, capture_output=True)
            return result, str(device)

    def test_no_parameter_preserves_upstream(self):
        result, _ = self.shell('boot=live', 'find_livefs 10; find_persistence_media persistence')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'UPSTREAM_LIVE\nUPSTREAM_PERSIST\n')

    def test_both_paths_use_same_device(self):
        result, device = self.shell('sbc-media-uuid=' + UUID,
                                   'find_livefs 10 && find_persistence_media persistence', True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f'LIVE:null:{device}:skip_uuid_check\nPERSIST:persistence:{device}\n')

    def test_missing_device_does_not_scan(self):
        for command in ('find_livefs 10', 'find_persistence_media persistence'):
            result, _ = self.shell('sbc-media-uuid=' + UUID, command)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')

    def test_malformed_empty_and_duplicate_rejected(self):
        for line in ('sbc-media-uuid=', 'sbc-media-uuid=../../sda',
                     'sbc-media-uuid=1234', f'sbc-media-uuid={UUID} sbc-media-uuid={UUID}'):
            result, _ = self.shell(line, 'find_livefs 10')
            self.assertEqual(result.returncode, 1, line)
            self.assertEqual(result.stdout, '')

    def test_timeout_respected(self):
        result, _ = self.shell('sbc-media-uuid=' + UUID,
                               'LIVE_MEDIA_TIMEOUT=20; find_livefs 10', True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')

    def test_board_opt_in_and_grub_uuid_probe(self):
        self.assertIn('BOARD_BIND_BOOT_MEDIA="1"', (ROOT/'boards/a5e/board.conf').read_text())
        hook = (ROOT/'overlay/data/live-build-config/hooks/live/94-sbc-grub-media.chroot').read_text()
        self.assertIn('probe --set=sbc_media_uuid --fs-uuid (${root})', hook)
        self.assertIn('sbc-media-uuid=${sbc_media_uuid}', hook)
        self.assertIn('sbc_pin_boot_media', hook)
        setup = (ROOT/'resources/grub-setup.py').read_text()
        self.assertIn("grub.GRUB_DIR_VYOS.lstrip('/')", setup)

    def test_installer_requires_explicit_identity_before_write(self):
        script = (ROOT/'scripts/install-a5e-nvme.sh').read_text()
        write = script.index('dd of="$device"')
        for guard in ('EXPECTED_SERIAL SHA256 --erase', 'NVMe serial mismatch',
                      'target or a descendant is mounted/in use', 'has active holders',
                      'image SHA256 mismatch', 'not an A5E firmware image'):
            self.assertLess(script.index(guard), write)
        self.assertIn('full 4 GiB image readback mismatch', script)

    def test_installer_replaces_cloned_disk_identities_and_loader(self):
        script = (ROOT/'scripts/install-a5e-nvme.sh').read_text()
        for command in ('sgdisk -e -G "$device"', 'tune2fs -U random "$p2"',
                        'mkfs.vfat -F32 -n EFI "$p1"', 'grub-install --target=arm64-efi',
                        '--pin-boot-media'):
            self.assertIn(command, script)
        self.assertLess(script.index('full 4 GiB image readback mismatch'),
                        script.index('sgdisk -e -G "$device"'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
