"""Make a capture: download every Word file of `sources.json`, check its sha256, convert it.

Each file is fetched from its URL (the Cámara de Diputados' LeyesBiblio, or a mirror given with
`--base-url`), one request at a time with a pause between them, and written at its published path
inside the capture folder. A file whose sha256 differs from the pinned one stops the capture
unless `--accept-unpinned` is given: a new hash means the Cámara regenerated the text (usually after
a new decree), which this package has to learn first.

Each Word file is then converted with LibreOffice (`soffice --headless --convert-to html`, a
throwaway profile), the HTML landing beside it. The downloads are data: nothing in them is executed
by this package, and LibreOffice runs headless with a fresh profile (macros disabled by default).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from tigie_nico_mx import __version__
from tigie_nico_mx.sources import SOURCES, Source, sha256_file

DEFAULT_BASE_URL = "https://www.diputados.gob.mx/LeyesBiblio/"
MAC_SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
USER_AGENT = f"tigie-nico-mx/{__version__} (open-data build; python-urllib)"


class CaptureError(Exception):
    pass


def find_soffice(explicit: str | None = None) -> str:
    """`--soffice`, else $SOFFICE, else `soffice` or `libreoffice` on PATH, else the macOS app."""
    for candidate in (
        explicit,
        os.environ.get("SOFFICE"),
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        MAC_SOFFICE if Path(MAC_SOFFICE).is_file() else None,
    ):
        if candidate:
            return candidate
    raise CaptureError(
        "LibreOffice not found: install it (apt install libreoffice-writer, or "
        "brew install --cask libreoffice) or set SOFFICE to its soffice binary"
    )


def source_url(source: Source, base_url: str) -> str:
    if base_url == DEFAULT_BASE_URL or not source.url.startswith(DEFAULT_BASE_URL):
        return source.url
    return base_url.rstrip("/") + "/" + source.url.removeprefix(DEFAULT_BASE_URL)


def download(url: str, target: Path, timeout: float = 300.0) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        with partial.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    partial.replace(target)


def convert(soffice: str, docs: list[Path]) -> None:
    """Convert Word files to HTML beside them, one LibreOffice run per folder."""
    by_folder: dict[Path, list[Path]] = {}
    for doc in docs:
        by_folder.setdefault(doc.parent, []).append(doc)
    with tempfile.TemporaryDirectory(prefix="tigie-lo-") as profile:
        for folder, files in by_folder.items():
            command = [
                soffice,
                f"-env:UserInstallation={Path(profile).as_uri()}",
                "--headless",
                "--convert-to",
                "html:HTML (StarWriter)",
                "--outdir",
                str(folder),
                *[str(f) for f in files],
            ]
            subprocess.run(command, check=True, capture_output=True, timeout=3600)  # noqa: S603
    for doc in docs:
        html = doc.with_suffix(".html")
        if not html.is_file():
            raise CaptureError(f"conversion failed: {doc}")


def capture(
    root: Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    soffice: str | None = None,
    delay: float = 1.0,
    accept_unpinned: bool = False,
    log: bool = True,
) -> list[dict[str, object]]:
    """Download, verify and convert every source into `root` (which must be new or empty)."""
    if root.exists() and any(root.iterdir()):
        raise CaptureError(f"refusing: {root} is not empty")
    binary = find_soffice(soffice)
    root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    docs: list[Path] = []
    for i, source in enumerate(SOURCES.values()):
        if i and delay:
            time.sleep(delay)
        url = source_url(source, base_url)
        target = root / source.path
        download(url, target)
        actual = sha256_file(target)
        pinned = actual == source.sha256
        rows.append({"key": source.key, "file": source.path, "sha256": actual, "pinned": pinned})
        if log:
            mark = "ok" if pinned else "DIFFERS"
            sys.stderr.write(f"{mark:7} {actual}  {source.path}\n")
        docs.append(target)
    unpinned = [str(r["file"]) for r in rows if not r["pinned"]]
    if unpinned and not accept_unpinned:
        raise CaptureError(
            "these files differ from their pinned sha256 (a newer Cámara text?): "
            + ", ".join(unpinned)
        )
    if log:
        sys.stderr.write(f"converting {len(docs)} files with LibreOffice ({binary})\n")
    convert(binary, docs)
    return rows
