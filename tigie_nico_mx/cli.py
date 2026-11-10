"""`python3 -m tigie_nico_mx <command>`

capture <dir> [--base-url URL] [--soffice PATH] [--delay SECONDS] [--accept-unpinned]
    Download every Word file of `sources.json` into a new folder, check each sha256 against the
    pinned one, and convert each file to HTML with LibreOffice. Needs network and LibreOffice.

verify <capture>
    Print every source with its sha256 and whether it matches the pin; exit 1 on any difference.

build <capture> [--out dist] [--as-of YYYY-MM-DD] [--format csv,sqlite,json] [--accept-unpinned]
    Parse the capture and write the edition into `--out`: `csv/*.csv`, `tigie-nico-mx-csv.zip`,
    `tigie.sqlite`, `tigie.json`, `resumen.json` and `SHA256SUMS`. Prints the counts. Exits 1 when
    a source is missing or a hash differs (unless `--accept-unpinned`).

Environment: TIGIE_BASE_URL (the Cámara's LeyesBiblio by default), SOFFICE (LibreOffice's
`soffice`; found on PATH or in /Applications by default), TIGIE_OUT (`dist` by default).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from tigie_nico_mx import __version__
from tigie_nico_mx.build import build
from tigie_nico_mx.capture import DEFAULT_BASE_URL, CaptureError, capture
from tigie_nico_mx.export import FORMATS, export
from tigie_nico_mx.sources import CONSOLIDATED_ON, Capture


def _print(data: Any) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m tigie_nico_mx",
        description="TIGIE 2022 with its NICOs and dated duties, from the Cámara de Diputados' "
        "copies of the DOF.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="download, verify and convert the sources")
    cap.add_argument("dir", type=Path, help="a new or empty folder")
    cap.add_argument(
        "--base-url",
        default=os.environ.get("TIGIE_BASE_URL", DEFAULT_BASE_URL),
        help=f"where LeyesBiblio lives (default {DEFAULT_BASE_URL}, or $TIGIE_BASE_URL)",
    )
    cap.add_argument("--soffice", default=None, help="LibreOffice's soffice (default: $SOFFICE)")
    cap.add_argument("--delay", type=float, default=1.0, help="seconds between downloads")
    cap.add_argument("--accept-unpinned", action="store_true", help="keep files that differ")

    ver = sub.add_parser("verify", help="check a capture's files against the pinned sha256")
    ver.add_argument("capture", type=Path)

    bld = sub.add_parser("build", help="build the edition from a capture")
    bld.add_argument("capture", type=Path)
    bld.add_argument(
        "--out",
        type=Path,
        default=Path(os.environ.get("TIGIE_OUT", "dist")),
        help="output folder (default dist, or $TIGIE_OUT)",
    )
    bld.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=CONSOLIDATED_ON,
        help=f"date of the computed cuotas (default {CONSOLIDATED_ON}, the consolidation date)",
    )
    bld.add_argument(
        "--format",
        default=",".join(FORMATS),
        help=f"comma-separated subset of {','.join(FORMATS)}",
    )
    bld.add_argument("--accept-unpinned", action="store_true", help="build from changed files")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "capture":
        try:
            rows = capture(
                args.dir,
                base_url=args.base_url,
                soffice=args.soffice,
                delay=args.delay,
                accept_unpinned=args.accept_unpinned,
            )
        except CaptureError as exc:
            sys.stderr.write(f"tigie_nico_mx: {exc}\n")
            return 1
        _print({"capture": str(args.dir), "files": len(rows), "sources": rows})
        return 0
    root: Path = args.capture
    if not root.is_dir():
        sys.stderr.write(f"tigie_nico_mx: not a directory: {root}\n")
        return 2
    if args.command == "verify":
        rows = Capture(root).verify()
        _print(rows)
        return 0 if all(r["pinned"] and r["html"] for r in rows) else 1
    formats = tuple(f.strip() for f in args.format.split(",") if f.strip())
    unknown = set(formats) - set(FORMATS)
    if unknown:
        sys.stderr.write(f"tigie_nico_mx: unknown format(s): {', '.join(sorted(unknown))}\n")
        return 2
    try:
        edition = build(Capture(root), as_of=args.as_of)
    except FileNotFoundError as exc:
        _print({"errores": [str(exc)]})
        return 1
    unpinned = [str(r["file"]) for r in edition.sources if not r["pinned"]]
    if unpinned and not args.accept_unpinned:
        edition.errors.append(
            "these Word files are missing or differ from their pinned sha256: "
            + ", ".join(unpinned)
        )
        _print({"errores": edition.errors})
        return 1
    written = export(edition, args.out, formats)
    _print(
        {
            "salida": str(args.out),
            "archivos": [p.relative_to(args.out).as_posix() for p in written],
            "conteos": edition.counts(),
            "advertencias": len(edition.warnings),
        }
    )
    return 0
