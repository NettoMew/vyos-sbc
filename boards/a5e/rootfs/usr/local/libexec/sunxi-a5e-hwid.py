#!/usr/bin/env python3
"""Bind missing A5E port hw-ids before VyOS's official name resolver.

Never rename devices, overwrite user bindings, create deleted interface nodes,
or persist random MACs. ConfigTree preserves VyOS version metadata. Exact
DT/platform identities, not current names/probe order, define WAN and LAN.
"""
import fcntl
import logging
import os
from pathlib import Path
import re
import stat
import tempfile

PORTS = {
    "eth0": ("4500000.ethernet", "dwmac-sun8i"),
    "eth1": ("4510000.ethernet", "dwmac-sun55i"),
}
LOG = logging.getLogger("sunxi-a5e-hwid")
CONFIG = Path("/opt/vyatta/etc/config/config.boot")


def valid_mac(value):
    return bool(re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", value)
                and value != "00:00:00:00:00:00"
                and not (int(value[:2], 16) & 1))


def discover_ports(net=Path("/sys/class/net")):
    """Accept SID-derived locally administered MACs only when DT agrees."""
    found = {name: [] for name in PORTS}
    for interface in sorted(net.iterdir()):
        if (interface / "master").exists():
            continue
        try:
            device = (interface / "device").resolve(strict=True)
            driver = (device / "driver").resolve(strict=True).name
            roles = [name for name, identity in PORTS.items()
                     if identity == (device.name, driver)]
            if not roles:
                continue
            address = (interface / "address").read_text().strip().lower()
            firmware = []
            for prop in ("mac-address", "local-mac-address"):
                try:
                    raw = (device / "of_node" / prop).read_bytes()
                except FileNotFoundError:
                    continue
                if len(raw) == 6:
                    firmware.append(":".join(f"{b:02x}" for b in raw))
            if not valid_mac(address) or address not in firmware:
                LOG.warning("skip %s: live MAC is not a verified firmware MAC", interface.name)
                continue
            found[roles[0]].append(address)
        except (OSError, RuntimeError):
            continue
    result = {}
    for name, addresses in found.items():
        if len(addresses) == 1:
            result[name] = addresses[0]
        elif addresses:
            LOG.warning("skip %s: ambiguous hardware identity", name)
    return {name: mac for name, mac in result.items()
            if list(result.values()).count(mac) == 1}


def bind_missing(config, ports):
    """Preserve existing bindings, including swapped ports or renamed nodes."""
    claimed = set()
    for kind in ("ethernet", "wireless"):
        base = ["interfaces", kind]
        if config.exists(base):
            for name in config.list_nodes(base):
                leaf = base + [name, "hw-id"]
                if config.exists(leaf):
                    claimed.add(config.return_value(leaf).lower())
    added = {}
    for name, mac in sorted(ports.items()):
        node = ["interfaces", "ethernet", name]
        if not config.exists(node) or config.exists(node + ["hw-id"]):
            continue
        if mac in claimed:
            LOG.warning("skip %s: firmware MAC is already bound in user config", name)
            continue
        config.set(node + ["hw-id"], value=mac)
        claimed.add(mac)
        added[name] = mac
    return added


def atomic_replace(path, original, replacement, before):
    """Keep owner/mode, create a private first-change backup, then rename."""
    backup = path.with_name(path.name + ".pre-a5e-hwid")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.a5e-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchown(stream.fileno(), before.st_uid, before.st_gid)
            os.fchmod(stream.fileno(), stat.S_IMODE(before.st_mode))
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        now = path.stat()
        if ((now.st_dev, now.st_ino, now.st_mtime_ns) !=
                (before.st_dev, before.st_ino, before.st_mtime_ns)
                or path.read_bytes() != original):
            raise RuntimeError("config.boot changed during bootstrap; refusing to overwrite")
        try:
            backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(backup_fd, "wb") as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def bootstrap(path, ports, tree_type):
    # Follow a user-selected config symlink rather than replacing the link.
    path = path.resolve(strict=True)
    before = path.stat()
    original = path.read_bytes()
    config = tree_type(original.decode())
    added = bind_missing(config, ports)
    if added:
        atomic_replace(path, original, config.to_string().encode(), before)
        for name, mac in added.items():
            LOG.info("bound missing %s hw-id to firmware %s", name, mac)
    return added


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    compatible = Path("/sys/firmware/devicetree/base/compatible")
    if not compatible.exists() or b"radxa,cubie-a5e" not in compatible.read_bytes().split(b"\0"):
        return
    if not CONFIG.exists():
        return
    from vyos.configtree import ConfigTree

    with open("/run/lock/sunxi-a5e-hwid.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        bootstrap(CONFIG, discover_ports(), ConfigTree)


if __name__ == "__main__":
    main()
