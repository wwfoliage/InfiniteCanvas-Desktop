from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ICON_SIZES = (16, 32, 48, 64, 128, 256)


def make_icon(source: Path, destination: Path) -> None:
    image = Image.open(source).convert("RGBA")
    side = max(image.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(image, ((side - image.width) // 2, (side - image.height) // 2))
    destination.parent.mkdir(parents=True, exist_ok=True)
    square.save(destination, format="ICO", sizes=[(size, size) for size in ICON_SIZES])


def make_version_info(version: str, destination: Path) -> None:
    parts = [int(part) for part in version.split(".")]
    if len(parts) != 3:
        raise ValueError("VERSION must contain three numeric components")
    version_tuple = (*parts, 0)
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple!r},
    prodvers={version_tuple!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('080404B0', [
        StringStruct('CompanyName', 'wwfoliage'),
        StringStruct('FileDescription', 'InfiniteCanvas Desktop'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'InfiniteCanvas'),
        StringStruct('LegalCopyright', 'See bundled LICENSE'),
        StringStruct('OriginalFilename', 'InfiniteCanvas.exe'),
        StringStruct('ProductName', 'InfiniteCanvas Desktop'),
        StringStruct('ProductVersion', '{version}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""
    destination.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    version = (root / "VERSION").read_text(encoding="utf-8-sig").strip()
    make_icon(root / "static" / "images" / "logo.png", root / "build" / "windows" / "InfiniteCanvas.ico")
    make_version_info(version, root / "build" / "windows" / "version_info.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
