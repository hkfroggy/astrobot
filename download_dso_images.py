#!/usr/bin/env python3
"""
Download all DSO catalog images from CDS HiPS2FITS and save them locally.

Run once:  python download_dso_images.py
           python download_dso_images.py --force   # re-download even if file exists

Images saved to: assets/dso/<name>.jpg
"""
import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from widgets.deep_sky import (
    _CATALOG, _IMG_W, _IMG_H, _FOV_SCALE,
    _ra_to_deg, _dec_to_deg,
    _HIPS_BASE, _HIPS_BASE2,
    _HIPS_SURVEY_PRIMARY, _HIPS_SURVEY_FALLBACK,
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
        ra_str     = entry[3]
        dec_str    = entry[4]
        fov_cat    = entry[7]
        out_file   = _OUT_DIR / f"{_safe(name)}.jpg"

        if out_file.exists() and not force:
            print(f"[{i:2d}/{total}] {name:<14s} skip (exists)")
            skipped += 1
            continue

        ra  = _ra_to_deg(ra_str)
        dec = _dec_to_deg(dec_str)
        fov = fov_cat * _FOV_SCALE

        saved = False
        for base in (_HIPS_BASE, _HIPS_BASE2):
            for survey in (_HIPS_SURVEY_PRIMARY, _HIPS_SURVEY_FALLBACK):
                try:
                    r = requests.get(base, params={
                        "hips":       survey,
                        "width":      _IMG_W,
                        "height":     _IMG_H,
                        "fov":        fov,
                        "ra":         f"{ra:.5f}",
                        "dec":        f"{dec:.5f}",
                        "projection": "TAN",
                        "format":     "jpg",
                    }, timeout=30)
                    r.raise_for_status()
                    if len(r.content) > 500:
                        out_file.write_bytes(r.content)
                        print(f"[{i:2d}/{total}] {name:<14s} OK  "
                              f"({len(r.content)//1024} KB)  [{survey}]")
                        ok += 1
                        saved = True
                        break
                except Exception as e:
                    host = base.split("/")[2]
                    print(f"[{i:2d}/{total}] {name:<14s} FAIL {host} {survey}: {e}")
            if saved:
                break

        if not saved:
            print(f"[{i:2d}/{total}] {name:<14s} *** ALL SOURCES FAILED ***")
            failed += 1

    print(f"\n{'─'*50}")
    print(f"Done — {ok} downloaded, {skipped} skipped, {failed} failed")
    print(f"Images in: {_OUT_DIR}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    download_all(force=force)
