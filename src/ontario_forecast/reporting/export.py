"""Shared export helpers for the final deliverables (03 scenarios, 04 impact).
Charts go to config.CHARTS_DIR, tables to config.TABLES_DIR."""

from __future__ import annotations

import csv
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages

from ontario_forecast import config


def export_figures(pages: list[tuple[str, object]], out_dir: Path, *, suffix: str, pdf_name: str) -> None:
    """Each figure -> <key><suffix>.png (200 dpi) + .svg, and all of them -> one PDF.

    Output is byte-for-byte reproducible: no timestamps, and fixed SVG element IDs
    (svg.hashsalt), so rerunning with unchanged results leaves git clean.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    with PdfPages(out_dir / pdf_name, metadata={"CreationDate": None, "ModDate": None}) as pdf:
        for key, fig in pages:
            fig.savefig(out_dir / f"{key}{suffix}.png", dpi=200)
            fig.savefig(out_dir / f"{key}{suffix}.svg", metadata={"Date": None})
            pdf.savefig(fig)
    print(f"Exported {len(pages)} chart(s) + {pdf_name} to {out_dir.relative_to(config.ROOT)}/")


def write_csv(rows: list[dict], path: Path) -> None:
    """Write dict rows (the charts' table view). Skips silently-empty files: warns instead."""
    if not rows:
        print(f"  ! nothing to write for {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  -> {path.relative_to(config.ROOT)} ({len(rows)} rows)")
