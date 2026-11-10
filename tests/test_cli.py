"""The command line and the capture step (a fake LibreOffice, files served from disk)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import textwrap
import unittest
import unittest.mock
from pathlib import Path

from tests import TARIFF
from tigie_nico_mx import cli
from tigie_nico_mx.capture import DEFAULT_BASE_URL, CaptureError, capture, source_url
from tigie_nico_mx.sources import SOURCES


def run(args: list[str]) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(args)
    return code, out.getvalue()


FAKE_SOFFICE = textwrap.dedent(
    """\
    #!{python}
    import sys
    from pathlib import Path
    args = sys.argv[1:]
    out = Path(args[args.index("--outdir") + 1])
    for name in args[args.index("--outdir") + 2:]:
        (out / (Path(name).stem + ".html")).write_text("<html><body><p>x</p></body></html>")
    """
)


class CliTest(unittest.TestCase):
    def test_build_refuses_unpinned_then_builds_with_the_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run(["build", str(TARIFF), "--out", tmp])
            self.assertEqual(code, 1)
            self.assertIn("pinned sha256", json.loads(out)["errores"][0])
            code, out = run(["build", str(TARIFF), "--out", tmp, "--accept-unpinned"])
            self.assertEqual(code, 0)
            result = json.loads(out)
            self.assertEqual(result["conteos"]["fracciones"], 21)
            self.assertIn("csv/fracciones.csv", result["archivos"])
            self.assertTrue((Path(tmp) / "SHA256SUMS").is_file())

    def test_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(["build", str(Path(tmp) / "nope")])[0], 2)
            code, _ = run(["build", str(TARIFF), "--out", tmp, "--format", "xlsx"])
            self.assertEqual(code, 2)
            code, out = run(["verify", str(TARIFF)])  # fixtures carry HTML only, no Word files
            self.assertEqual(code, 1)
            self.assertEqual(len(json.loads(out)), len(SOURCES))

    def test_a_missing_html_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            partial = Path(tmp) / "capture"
            shutil.copytree(TARIFF, partial)
            (partial / SOURCES["tarifa16"].html).unlink()
            code, out = run(
                ["build", str(partial), "--out", str(Path(tmp) / "out"), "--accept-unpinned"]
            )
            self.assertEqual(code, 1)
            self.assertIn("LIGIE_2022_tarifa16_13oct26.html", json.loads(out)["errores"][0])


class CaptureTest(unittest.TestCase):
    def test_source_url_with_a_mirror(self) -> None:
        source = SOURCES["tarifa16"]
        self.assertEqual(source_url(source, DEFAULT_BASE_URL), source.url)
        self.assertEqual(
            source_url(source, "https://mirror.example/leyes"),
            "https://mirror.example/leyes/ref/ligie_2022/LIGIE_2022_tarifa16_13oct26.doc",
        )

    def test_capture_downloads_checks_and_converts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mirror = Path(tmp) / "mirror"
            for source in SOURCES.values():
                target = mirror / source.url.removeprefix(DEFAULT_BASE_URL)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"not the real file")
            soffice = Path(tmp) / "soffice"
            soffice.write_text(FAKE_SOFFICE.format(python=sys.executable), encoding="utf-8")
            soffice.chmod(soffice.stat().st_mode | stat.S_IEXEC)
            base = mirror.as_uri() + "/"
            with self.assertRaises(CaptureError) as refused:
                capture(Path(tmp) / "a", base_url=base, soffice=str(soffice), delay=0, log=False)
            self.assertIn("differ from their pinned sha256", str(refused.exception))
            rows = capture(
                Path(tmp) / "b",
                base_url=base,
                soffice=str(soffice),
                delay=0,
                accept_unpinned=True,
                log=False,
            )
            self.assertEqual(len(rows), len(SOURCES))
            self.assertFalse(any(r["pinned"] for r in rows))
            for source in SOURCES.values():
                self.assertTrue((Path(tmp) / "b" / source.html).is_file(), source.html)
            with self.assertRaises(CaptureError):  # never into a folder that has files
                capture(Path(tmp) / "b", base_url=base, soffice=str(soffice), delay=0, log=False)

    def test_no_libreoffice_is_a_clear_error(self) -> None:
        saved = os.environ.pop("SOFFICE", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with (
                    unittest.mock.patch("tigie_nico_mx.capture.shutil.which", return_value=None),
                    unittest.mock.patch(
                        "tigie_nico_mx.capture.MAC_SOFFICE", str(Path(tmp) / "none")
                    ),
                ):
                    with self.assertRaises(CaptureError) as missing:
                        capture(Path(tmp) / "c", delay=0, log=False)
                self.assertIn("LibreOffice not found", str(missing.exception))
        finally:
            if saved is not None:
                os.environ["SOFFICE"] = saved


if __name__ == "__main__":
    unittest.main()
