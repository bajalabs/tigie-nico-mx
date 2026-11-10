"""Mexico's import and export tariff (TIGIE 2022 of the LIGIE) with its NICOs and every duty dated
by the decree that set it, built from the Cámara de Diputados' copies of the DOF publications.

- `capture.py` downloads the Word files named in `sources.json`, checks each one against its pinned
  sha256 and converts it to HTML with LibreOffice;
- `html.py` reads a LibreOffice HTML export in document order;
- `tigie.py` parses the Tarifa: sections, chapters, partidas, subpartidas, the uncoded one-dash
  groups and the fracciones with their Spanish description, unit (UMT), cuotas and notes;
- `nico.py` reads the NICO acuerdo of DOF 22-08-2022 and its two modifications;
- `decrees.py` and `timeline.py` turn every decree into dated IGI and IGE segments;
- `build.py` assembles the tables; `export.py` writes CSV, SQLite, JSON and SHA256SUMS.

The Harmonized System 2022 six-digit level comes from the TIGIE's own Spanish text (its 2-, 4- and
6-digit rows), never from WCO text.
"""

__version__ = "1.0.0"
