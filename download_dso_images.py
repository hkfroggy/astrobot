#!/usr/bin/env python3
"""
Download all DSO catalog images from the configured online providers.

Run once:  python download_dso_images.py
           python download_dso_images.py --force   # re-download even if file exists

Images saved to: assets/dso/<name>.jpg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from widgets.deep_sky import (
    _CATALOG, _fetch_online_image,
)

_OUT_DIR = Path(__file__).parent / "assets" / "dso"


def _safe(name: str) -> str:
    return name.replace(" ", "_").replace("/", "_")


def download_all(force=False):
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = len(_CATALOG)
    ok = skipped = failed = 0

    for i, entry in enumerate(_CATALOG, 1):
        name       = entry[0]
        out_file   = _OUT_DIR / f"{_safe(name)}.jpg"

        if out_file.exists() and not force:
            print(f"[{i:2d}/{total}] {name:<14s} skip (exists)")
            skipped += 1
            continue

        obj = {
            "name": name, "ra": entry[3], "dec": entry[4], "fov": entry[7]
        }
        result = _fetch_online_image(obj)
        if result is None:
            print(f"[{i:2d}/{total}] {name:<14s} *** ALL SOURCES FAILED ***")
            failed += 1
            continue

        raw, source = result
        out_file.write_bytes(raw)
        print(f"[{i:2d}/{total}] {name:<14s} OK  "
              f"({len(raw)//1024} KB)  [{source}]")
        ok += 1

    print(f"\n{'─'*50}")
    print(f"Done — {ok} downloaded, {skipped} skipped, {failed} failed")
    print(f"Images in: {_OUT_DIR}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    download_all(force=force)
