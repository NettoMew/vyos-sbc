#!/usr/bin/env python3
"""Read-only A5E raw-image audit: GPT integrity, SPL checksum and firmware bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib


def audit(image, firmware):
    size = image.stat().st_size
    assert size % 512 == 0, "unaligned image size"
    data = firmware.read_bytes()
    assert data[4:12] == b"eGON.BT0", "missing sunxi SPL boot header"
    checksum, length = struct.unpack_from("<II", data, 12)
    assert 32 <= length <= len(data) and length % 4 == 0, "invalid SPL length"
    words = list(struct.unpack(f"<{length // 4}I", data[:length]))
    words[3] = 0x5F0A6C39
    assert sum(words) & 0xFFFFFFFF == checksum, "bad SPL checksum"
    # FIT is placed after the SPL, padded to a sector boundary.
    fits = [offset for offset in range(length, len(data) - 8, 512)
            if data[offset:offset + 4] == b"\xd0\x0d\xfe\xed"]
    assert fits, "missing U-Boot/BL31 FIT"
    fit = fits[0]
    fit_size = struct.unpack_from(">I", data, fit + 4)[0]
    assert fit_size >= 40 and fit + fit_size <= len(data), "truncated FIT"
    with image.open("rb") as stream:
        mbr = stream.read(512)
        assert mbr[510:512] == b"\x55\xaa" and mbr[450] == 0xEE, "missing protective MBR"

        def header(lba):
            stream.seek(lba * 512)
            h = bytearray(stream.read(512))
            assert h[:8] == b"EFI PART", "missing GPT header"
            hsize, expected = struct.unpack_from("<II", h, 12)
            assert 92 <= hsize <= 512
            struct.pack_into("<I", h, 16, 0)
            assert zlib.crc32(h[:hsize]) == expected, "bad GPT header CRC"
            current, other = struct.unpack_from("<QQ", h, 24)
            assert current == lba
            entries_lba, count, entry_size, entries_crc = struct.unpack_from("<QIII", h, 72)
            assert count <= 4096 and 128 <= entry_size <= 4096
            stream.seek(entries_lba * 512)
            entries = stream.read(count * entry_size)
            assert zlib.crc32(entries) == entries_crc, "bad GPT entries CRC"
            return other, entries, entry_size

        backup_lba, entries, entry_size = header(1)
        assert backup_lba == size // 512 - 1
        primary_lba, backup_entries, backup_size = header(backup_lba)
        assert primary_lba == 1 and backup_entries == entries and backup_size == entry_size
        partitions = []
        for offset in range(0, len(entries), entry_size):
            entry = entries[offset:offset + entry_size]
            if entry[:16] == bytes(16):
                continue
            start, end = struct.unpack_from("<QQ", entry, 32)
            name = entry[56:128].decode("utf-16-le").rstrip("\0")
            partitions.append({"name": name, "start": start * 512, "end": (end + 1) * 512})
        assert len(partitions) == 2
        assert partitions[0]["start"] == 16 * 1024**2
        assert partitions[1]["start"] == 272 * 1024**2
        offset = 128 * 1024
        assert offset + len(data) <= partitions[0]["start"], "firmware overlaps ESP"
        stream.seek(offset)
        assert stream.read(len(data)) == data, "written firmware differs from build artifact"
    return {"image_bytes": size, "firmware_offset": offset, "firmware_bytes": len(data),
            "firmware_sha256": hashlib.sha256(data).hexdigest(),
            "spl_bytes": length, "fit_offset": fit, "fit_bytes": fit_size,
            "partitions": partitions, "result": "PASS"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("firmware", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.image, args.firmware), indent=2))
