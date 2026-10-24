"""Read PE import tables without adding anything to the locked Python runtime."""
import argparse
import json
import mmap
import re
import struct
from pathlib import Path


def imports(path):
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        if data[:2] != b"MZ":
            return []
        header = struct.unpack_from("<I", data, 0x3c)[0]
        if data[header:header + 4] != b"PE\0\0":
            return []
        sections = struct.unpack_from("<H", data, header + 6)[0]
        optional_size = struct.unpack_from("<H", data, header + 20)[0]
        optional = header + 24
        magic = struct.unpack_from("<H", data, optional)[0]
        directories = optional + (112 if magic == 0x20b else 96)
        import_rva = struct.unpack_from("<I", data, directories + 8)[0]
        table = optional + optional_size

        def offset(rva):
            for section in range(sections):
                entry = table + section * 40
                virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", data, entry + 8)
                if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
                    return raw_offset + rva - virtual_address
            return rva

        if not import_rva:
            return []
        cursor = offset(import_rva)
        result = []
        while data[cursor:cursor + 20] != b"\0" * 20:
            name_rva = struct.unpack_from("<I", data, cursor + 12)[0]
            name_offset = offset(name_rva)
            end = data.find(b"\0", name_offset)
            result.append(data[name_offset:end].decode("ascii").lower())
            cursor += 20
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    matched = {}
    scanned = 0
    for path in args.stage.rglob("*"):
        if path.suffix.lower() not in (".dll", ".pyd", ".exe") or path.parent.name == "prerequisites":
            continue
        scanned += 1
        native = [name for name in imports(path) if re.match(r"(msvcp|vcruntime|concrt|vcomp|ucrtbase|api-ms-win-crt)", name)]
        if native:
            matched[str(path.relative_to(args.stage))] = native
    args.report.write_text(json.dumps({"native_files_scanned": scanned, "crt_imports": sorted({name for names in matched.values() for name in names}),
        "files": matched, "strategy": "Official CPython app-local vcruntime DLLs; official Microsoft VC++ x64 redistributable prerequisite; Windows UCRT",
        "vc_standalone_included": (args.stage / "prerequisites/VC_redist.x64.exe").is_file()}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
