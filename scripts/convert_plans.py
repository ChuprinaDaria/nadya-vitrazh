"""Convert pavilion plan PDFs to PNG images for the dashboard.

Usage:
    python scripts/convert_plans.py [path/to/plans/dir]

Default: looks in materials/матеріали павільйону/плани/
Output: vitrazh/dashboard/static/plans/
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import fitz  # PyMuPDF


NAME_MAP = {
    "план камер з розмірами.pdf": "plan_cameras.png",
    "план павільйону з розмірами та площею.pdf": "plan_pavilion.png",
    "чистий план камер.pdf": "plan_cameras_clean.png",
    "чистий план павільйону.pdf": "plan_pavilion_clean.png",
}

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_PLANS_DIR = PROJECT_ROOT / "materials" / "матеріали павільйону" / "плани"
OUTPUT_DIR = PROJECT_ROOT / "vitrazh" / "dashboard" / "static" / "plans"


def convert(plans_dir: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for pdf_name, png_name in NAME_MAP.items():
        path = plans_dir / pdf_name
        if not path.exists():
            print(f"  skip: {pdf_name} (not found)")
            continue

        doc = fitz.open(str(path))
        page = doc[0]
        mat = fitz.Matrix(2, 2)  # 2x zoom for quality
        pix = page.get_pixmap(matrix=mat)
        out = OUTPUT_DIR / png_name
        pix.save(str(out))
        print(f"  {png_name}: {pix.width}x{pix.height}")
        doc.close()


if __name__ == "__main__":
    plans_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PLANS_DIR
    print(f"Converting plans from: {plans_dir}")
    convert(plans_dir)
    print(f"Output: {OUTPUT_DIR}")
