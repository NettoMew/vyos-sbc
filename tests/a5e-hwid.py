#!/usr/bin/env python3
"""A5E firmware MAC/config safety regressions (stdlib, Linux, no hardware)."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

# Import the real overlay module without dropping host-version bytecode into
# a directory later copied verbatim into the target root filesystem.
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "hwid", ROOT / "boards/a5e/rootfs/usr/local/libexec/sunxi-a5e-hwid.py")
hwid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hwid)
WAN, LAN = "02:10:0c:7b:dc:2d", "12:10:0c:7b:dc:2d"


class Tree:
    """Minimal ConfigTree API double; real VyOS integration tested separately."""
    def __init__(self, text):
        self.data = json.loads(text)

    def value(self, path):
        node = self.data
        for key in path:
            node = node[key]
        return node

    def exists(self, path):
        try:
            self.value(path)
            return True
        except KeyError:
            return False

    def list_nodes(self, path):
        return list(self.value(path))

    def return_value(self, path):
        return self.value(path)

    def set(self, path, value):
        self.value(path[:-1])[path[-1]] = value

    def to_string(self):
        return json.dumps(self.data)


def config(ethernet=None, wireless=None):
    return Tree(json.dumps({"interfaces": {
        "ethernet": ethernet if ethernet is not None else {"eth0": {}, "eth1": {}},
        "wireless": wireless or {}}}))


class Discovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.net = self.root / "net"
        self.net.mkdir()

    def port(self, name, role, mac, firmware=True, driver=None):
        device_name, expected_driver = hwid.PORTS[role]
        device = self.root / "devices" / device_name
        device.mkdir(parents=True, exist_ok=True)
        drv = self.root / "drivers" / (driver or expected_driver)
        drv.mkdir(parents=True, exist_ok=True)
        if not (device / "driver").exists():
            (device / "driver").symlink_to(drv)
        interface = self.net / name
        interface.mkdir()
        (interface / "device").symlink_to(device)
        (interface / "address").write_text(mac + "\n")
        (device / "of_node").mkdir(exist_ok=True)
        if firmware:
            (device / "of_node/local-mac-address").write_bytes(bytes.fromhex(mac.replace(":", "")))
        return interface

    def test_probe_names_do_not_define_roles(self):
        self.port("eth3", "eth0", WAN)
        self.port("eth2", "eth1", LAN)
        self.assertEqual(hwid.discover_ports(self.net), {"eth0": WAN, "eth1": LAN})

    def test_no_dt_mac_rejected(self):
        self.port("eth2", "eth0", WAN, firmware=False)
        self.assertEqual(hwid.discover_ports(self.net), {})

    def test_wrong_driver_rejected(self):
        self.port("eth2", "eth0", WAN, driver="unrelated")
        self.assertEqual(hwid.discover_ports(self.net), {})

    def test_random_or_user_changed_mac_rejected(self):
        port = self.port("eth2", "eth0", WAN)
        (port / "address").write_text(LAN)
        self.assertEqual(hwid.discover_ports(self.net), {})

    def test_multicast_zero_and_malformed_mac_rejected(self):
        for mac in ("01:00:00:00:00:01", "00:00:00:00:00:00", "garbage", "ff:ff:ff:ff:ff:ff"):
            self.assertFalse(hwid.valid_mac(mac))
        self.assertTrue(hwid.valid_mac(WAN))

    def test_duplicate_port_or_mac_rejected(self):
        self.port("eth2", "eth0", WAN)
        self.port("eth4", "eth0", WAN)
        self.assertEqual(hwid.discover_ports(self.net), {})

    def test_same_mac_on_two_roles_rejected(self):
        self.port("eth2", "eth0", WAN)
        self.port("eth3", "eth1", WAN)
        self.assertEqual(hwid.discover_ports(self.net), {})

    def test_enslaved_port_rejected(self):
        port = self.port("eth2", "eth0", WAN)
        (port / "master").symlink_to(self.root)
        self.assertEqual(hwid.discover_ports(self.net), {})


class Bindings(unittest.TestCase):
    def test_missing_bindings_added(self):
        tree = config()
        self.assertEqual(hwid.bind_missing(tree, {"eth0": WAN, "eth1": LAN}), {"eth0": WAN, "eth1": LAN})
        self.assertEqual(hwid.bind_missing(tree, {"eth0": WAN, "eth1": LAN}), {})

    def test_deleted_interface_not_created(self):
        tree = config({"eth1": {}})
        self.assertEqual(hwid.bind_missing(tree, {"eth0": WAN, "eth1": LAN}), {"eth1": LAN})

    def test_swapped_user_bindings_preserved(self):
        tree = config({"eth0": {"hw-id": LAN}, "eth1": {"hw-id": WAN}})
        before = tree.to_string()
        self.assertEqual(hwid.bind_missing(tree, {"eth0": WAN, "eth1": LAN}), {})
        self.assertEqual(tree.to_string(), before)

    def test_renamed_or_wireless_binding_not_stolen(self):
        tree = config({"eth0": {}, "eth9": {"hw-id": WAN.upper()}}, {"wlan0": {"hw-id": LAN}})
        self.assertEqual(hwid.bind_missing(tree, {"eth0": WAN, "eth1": LAN}), {})


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "config.boot"
        self.original = config().to_string().encode()
        self.path.write_bytes(self.original)
        self.path.chmod(0o640)

    def test_atomic_backup_permissions_and_idempotence(self):
        before = self.path.stat()
        hwid.bootstrap(self.path, {"eth0": WAN, "eth1": LAN}, Tree)
        after = self.path.stat()
        self.assertEqual((after.st_uid, after.st_gid, after.st_mode), (before.st_uid, before.st_gid, before.st_mode))
        backup = self.path.with_name("config.boot.pre-a5e-hwid")
        self.assertEqual(backup.read_bytes(), self.original)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        current = self.path.read_bytes()
        self.assertEqual(hwid.bootstrap(self.path, {"eth0": WAN}, Tree), {})
        self.assertEqual(self.path.read_bytes(), current)
        self.assertEqual(self.path.stat().st_mtime_ns, after.st_mtime_ns)

    def test_existing_backup_untouched(self):
        backup = self.path.with_name("config.boot.pre-a5e-hwid")
        backup.write_bytes(b"older backup")
        hwid.bootstrap(self.path, {"eth0": WAN}, Tree)
        self.assertEqual(backup.read_bytes(), b"older backup")

    def test_symlink_preserved(self):
        link = self.path.with_name("selected-config")
        link.symlink_to(self.path)
        hwid.bootstrap(link, {"eth0": WAN}, Tree)
        self.assertTrue(link.is_symlink())
        self.assertIn(WAN, self.path.read_text())

    def test_concurrent_write_refused(self):
        before = self.path.stat()
        self.path.write_bytes(b"user changed")
        with self.assertRaises(RuntimeError):
            hwid.atomic_replace(self.path, self.original, b"replacement", before)
        self.assertEqual(self.path.read_bytes(), b"user changed")
        self.assertEqual(list(self.path.parent.glob(".config.boot.a5e-*")), [])

    def test_parse_error_no_changes(self):
        self.path.write_bytes(b"invalid config")
        with self.assertRaises(ValueError):
            hwid.bootstrap(self.path, {"eth0": WAN}, Tree)
        self.assertEqual(self.path.read_bytes(), b"invalid config")


if __name__ == "__main__":
    unittest.main(verbosity=2)
