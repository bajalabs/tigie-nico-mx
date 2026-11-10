**English** · [Español](README.es.md) (the Spanish edition is the primary one)

# tigie-nico-mx

[![CI](https://github.com/bajalabs/tigie-nico-mx/actions/workflows/ci.yml/badge.svg)](https://github.com/bajalabs/tigie-nico-mx/actions/workflows/ci.yml)
[![Code: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![Data: CC0-1.0](https://img.shields.io/badge/data-CC0--1.0-lightgrey.svg)](LICENSE-DATA)
[![Release](https://img.shields.io/github/v/release/bajalabs/tigie-nico-mx)](https://github.com/bajalabs/tigie-nico-mx/releases/latest)

Mexico's import and export tariff (the TIGIE 2022 of the Ley de los Impuestos Generales de
Importación y de Exportación) with its NICOs and every duty dated by the decree that set it, as open
CSV, SQLite and JSON files for importers, customs brokers, analysts and developers.

- **8,183 tariff lines (fracciones)** with their official Spanish description, unit of measure (UMT)
  and the import (IGI) and export (IGE) duties the consolidated text shows.
- **11,507 NICOs in force** (11,528 including the 21 suppressed), each with the date it was created
  or suppressed.
- **19,480 dated duty segments** (IGI and IGE) since the LIGIE 2022 entered into force
  (2022-12-12), each with its DOF decree, start and end date, and its scope ("acotación") when a
  measure covers only some goods of the line.
- The whole tree: 22 sections, 97 chapters, 1,235 headings and 5,619 subheadings (5,612 of the
  Harmonized System 2022 and 7 national ones in chapter 98), with the TIGIE's own Spanish text,
  never WCO text.

Everything is built reproducibly from the Word files the Cámara de Diputados publishes, each pinned
by its sha256.

## Quick start

Requirements: Python 3.12 or later (standard library only) and, to download and convert the
sources, LibreOffice (`brew install --cask libreoffice` on macOS, `sudo apt-get install -y
libreoffice-writer` on Ubuntu, or set `SOFFICE` to the path of `soffice`).

```sh
git clone https://github.com/bajalabs/tigie-nico-mx.git
cd tigie-nico-mx
python3 -m unittest                       # tests on the fixtures, seconds
python3 -m tigie_nico_mx capture capture  # downloads 25 Word files (78 MB), checks each sha256, converts them (about 3 min)
python3 -m tigie_nico_mx build capture    # writes dist/ (about 10 s)
sqlite3 dist/tigie.sqlite "SELECT tipo, valor, desde, hasta FROM medidas WHERE fraccion = '72081003' ORDER BY tipo DESC, desde"
```

With [uv](https://docs.astral.sh/uv/) it works the same: `uv run python -m tigie_nico_mx ...`.

If you only want the data, every release attaches the files of `dist/` to
[Releases](https://github.com/bajalabs/tigie-nico-mx/releases/latest), with their `SHA256SUMS`.

## What is inside

Counts of version 1.0.0 (the Cámara's consolidated text as of 2026-10-14; decrees up to the DOF of
2026-10-13):

| Table | Rows | What it is |
|---|---:|---|
| `secciones` | 22 | Sections I–XXII with their title and chapters |
| `capitulos` | 97 | Chapters 01–98 (there is no 77); `sistema_armonizado` = 0 only for 98 |
| `partidas` | 1,235 | 4-digit headings, with the subchapter where the Tarifa uses one |
| `grupos` | 1,024 | One-dash subheadings the Tarifa prints without a code; 5-digit navigation code |
| `subpartidas` | 5,619 | 6-digit subheadings (5,612 HS 2022, 7 in chapter 98) |
| `fracciones` | 8,183 | 8-digit tariff lines with UMT and published and computed duties |
| `nicos` | 11,528 | 2-digit NICOs (11,507 in force, 21 suppressed) |
| `medidas` | 19,480 | IGI segments (11,277 general, 17 scoped) and IGE segments (8,186) |
| `notas` | 4,683 | Section and chapter notes, NICO annotations, the Cámara's notes |
| `historial_descripciones` | 19 | Old and new texts of the 14 lines a decree rewrote |
| `fuentes` | 25 | Every source file with URL, DOF date, codNota and sha256 |
| `aplicacion` | 34 | What was applied from each decree and what was not, with the reason |
| `cotejo` | 22 | Differences between the computed duty and the one the consolidated text shows |

1,785 lines have had a general IGI set by a decree other than the original law; the longest history
has six segments. 8,134 lines have at least one NICO in force.

### Files

| File | Size | Content |
|---|---:|---|
| `csv/*.csv` | 13.9 MB in all | One table per file, UTF-8 without BOM, header row |
| `tigie-nico-mx-csv.zip` | 0.9 MB | The same CSVs, zipped |
| `tigie.sqlite` | 16.9 MB | The tables with indexes, the `edicion` table and four views |
| `tigie.json` | 19.9 MB | One document: each line with its NICOs, measures and texts nested |
| `resumen.json` | 26 KB | Counts, source hashes, decree application, cross-check, warnings |
| `SHA256SUMS` | 1.4 KB | sha256 of every file above |

The build is deterministic: the same capture gives the same bytes (no timestamps), so `SHA256SUMS`
can be compared between builds.

## Data dictionary

Dates are ISO (`YYYY-MM-DD`). Codes carry no dots and keep their leading zeros; read them as text.
Duties follow the Tarifa's convention: a percent without the sign (`15`, `210.44`), `Ex.` (exempt),
`Prohibida` (prohibited), or a specific or mixed duty as published (`AE (0.36 Dls EUA por Kg)`, `AMX
(20%+0.36 Dls por Kg de azúcar)`). The first columns of `subpartidas`, `fracciones`, `nicos` and
`medidas` are a contract: never renamed or removed; new columns are added at the end. In SQLite an
empty field is `NULL`. Column names are Spanish, as in the law.

**`fracciones`** (tariff lines)

| Column | Meaning |
|---|---|
| `fraccion` | 8 digits (`72081003` is 7208.10.03) |
| `subpartida` | 6 digits |
| `descripcion` | The line's text in the consolidated Tarifa, without the notes the Cámara appends (those are in `notas`) |
| `umt` | Unit of measure as published (`Kg`, `Pza`, `L`, `M²`, …); empty for the 43 prohibited lines, whose unit cell reads "Prohibida" |
| `igi_vigente`, `ige_vigente` | Import and export duties as the Cámara's consolidated text shows them |
| `partida`, `capitulo` | 4 and 2 digits |
| `igi_calculado`, `ige_calculado` | General duty computed from the decrees on the cut-off date (`edicion.fecha_corte_calculado`, 2026-10-14 by default; `build --as-of` changes it) |
| `alta` | First day the line exists (2022-12-12, or the date of the decree that created it) |
| `nicos_vigentes` | NICOs in force on the cut-off date |
| `orden` | Position in the Tarifa |

**`subpartidas`**: `subpartida` (6 digits), `partida` (4), `capitulo` (2), `descripcion` (TIGIE text),
`grupo` (the uncoded 5-digit group a two-dash subheading belongs to, or empty), `sistema_armonizado`
(1 for chapters 01–97; 0 for 98, which is national), `orden`.

**`nicos`**

| Column | Meaning |
|---|---|
| `fraccion`, `nico`, `codigo` | 8-digit line, 2-digit NICO, and the 10-digit code declared on the pedimento |
| `descripcion` | The NICO's text in the acuerdo |
| `alta` | First day in force (2022-12-12 for the base acuerdo; 2023-07-01 and 2024-03-22 for its modifications) |
| `baja` | First day the NICO no longer exists (suppressed); empty while in force |
| `fuente_alta`, `fuente_baja` | The DOF acuerdo that created it and the one that suppressed it |

**`medidas`** (duty segments)

| Column | Meaning |
|---|---|
| `fraccion` | 8 digits |
| `tipo` | `IGI` (import) or `IGE` (export) |
| `valor` | The duty of the segment |
| `desde` | First day in force |
| `hasta` | **Last** day in force (inclusive); empty while open |
| `decreto` | `DOF dd-mm-yyyy: title` of the publication that set it |
| `alcance` | Empty when the measure covers the whole line; otherwise the scope ("Únicamente pan de caja") |
| `valor_numerico` | Ad valorem percent (0 for `Ex.`); empty for specific, mixed and prohibited |
| `decreto_fecha`, `decreto_codnota`, `decreto_url` | DOF date, DOF note number, and the Cámara's copy |
| `nota` | Why the segment applies and what ended it (abrogation, removal from a list, …) |

For each line and type, the general segments (empty `alcance`) never overlap; the duty on a day is
the one of the segment that contains it. A scoped segment lives beside the general one: a partial
exemption or duty for some goods of the line.

**Other tables**

- `secciones`: `seccion` (I–XXII), `numero`, `titulo`, `capitulos` (space-separated).
- `capitulos`: `capitulo`, `seccion`, `descripcion`, `sistema_armonizado`, `orden`.
- `partidas`: `partida`, `capitulo`, `descripcion`, `subcapitulo`, `orden`.
- `grupos`: `grupo` (5 digits, navigation only; not an official code), `partida`, `descripcion`,
  `orden`.
- `notas`: `nivel` (`seccion`, `capitulo`, `partida`, `grupo`, `subpartida`, `fraccion`), `codigo`,
  `tipo` (`notas_seccion`, `notas_capitulo`, `anotaciones_nico`, `subcapitulo`, `sin_codigo`,
  `nota_camara`), `texto`, `fuente`.
- `historial_descripciones`: `fraccion`, `desde`, `hasta` (inclusive), `descripcion`, `decreto`.
- `fuentes`: `clave`, `archivo`, `url`, `dof`, `codnota`, `titulo`, `sha256`, `papel`.
- `aplicacion`: `clave`, `decreto`, `aplicado` (`si`/`no`), `que`, `fracciones`, `motivo`.
- `cotejo`: `fraccion`, `tipo`, `publicado`, `calculado`, `medida_parcial`, `ultima_nota_camara`.

**SQLite views** (today is the date of the machine running the query):

- `v_fracciones`: each line with the descriptions of its subheading, group, heading, chapter and
  section.
- `v_arancel_hoy`: today's general IGI and IGE per line, plus the partial duties in force.
- `v_medidas_hoy`: the segments in force today.
- `v_nicos_vigentes`: the NICOs in force today.

## Example queries

A line's duty history (7208.10.03, hot-rolled steel):

```sql
SELECT tipo, valor, desde, hasta, decreto, alcance
FROM medidas WHERE fraccion = '72081003' ORDER BY tipo DESC, desde;
```

```text
IGI  15   2022-12-12  2023-05-31  DOF 18-11-2022: Decreto por el que se modifica la Tarifa …
IGI  10   2023-06-01  2023-08-15  DOF 18-11-2022: Decreto por el que se modifica la Tarifa …
IGI  25   2023-08-16  2024-04-22  DOF 15-08-2023: Decreto por el que se modifica la Tarifa …
IGI  25   2024-04-23  2025-12-31  DOF 22-04-2024: Decreto por el que se modifica la Tarifa …
IGI  35   2026-01-01              DOF 29-12-2025: Decreto por el que se reforman diversas fracciones …
IGE  Ex.  2022-12-12              DOF 07-06-2022: Decreto por el que se expide la Ley …
```

The NICOs of a subheading (8414.51, fans), with those created and suppressed:

```sql
SELECT n.codigo, n.descripcion, n.alta, n.baja
FROM nicos n JOIN fracciones f USING (fraccion)
WHERE f.subpartida = '841451' ORDER BY n.codigo;
```

```text
8414510100  Ventiladores, de uso doméstico.                            2022-12-12  2023-07-01
8414510101  Ventiladores de techo.                                     2023-07-01
8414510199  Los demás.                                                 2023-07-01
8414510200  Ventiladores anticondensantes de 12 V, corriente directa.  2022-12-12
8414519900  Los demás.                                                 2022-12-12  2023-07-01
8414519901  Ventiladores de techo.                                     2023-07-01
8414519999  Los demás.                                                 2023-07-01
```

The duty on a given day (white maize, 1005.90.04, on 2023-12-31):

```sql
SELECT valor, decreto FROM medidas
WHERE fraccion = '10059004' AND tipo = 'IGI' AND alcance IS NULL
  AND desde <= '2023-12-31' AND (hasta IS NULL OR hasta >= '2023-12-31');
-- 50, DOF 23-06-2023
```

Today's duty, with partial exemptions:

```sql
SELECT fraccion, igi, ige, igi_parcial FROM v_arancel_hoy WHERE fraccion = '19054001';
-- 19054001 | 10 | Ex. | Ex. (Únicamente pan de caja.)
```

From Python, without dependencies:

```python
import csv

with open("dist/csv/fracciones.csv", encoding="utf-8", newline="") as f:
    fracciones = {r["fraccion"]: r for r in csv.DictReader(f)}
print(fracciones["84713001"]["descripcion"], fracciones["84713001"]["igi_vigente"])
```

## How it is built

1. **Sources.** [`tigie_nico_mx/sources.json`](tigie_nico_mx/sources.json) lists the 25 Word files of
   the Cámara de Diputados ([LIGIE index](https://www.diputados.gob.mx/LeyesBiblio/ref/ligie_2022.htm)),
   each with its URL, DOF date, codNota and sha256: the consolidated text (`doc/LIGIE_2022.doc`,
   regenerated by the Cámara on 2026-10-14), the law as first published (DOF 2022-06-07), its two
   reforms, the sixteen decrees that modify the Tarifa (plus two that modify tariff-rate quotas) and
   the three NICO acuerdos.
2. **Capture.** `python3 -m tigie_nico_mx capture <dir>` downloads each file one second apart,
   compares its sha256 with the pinned one and stops if it differs (a new hash means the Cámara
   regenerated the text, usually after a new decree). It then converts each Word file to HTML with
   LibreOffice (`soffice --headless --convert-to html`, a throwaway profile). The conversion was
   tested with LibreOffice 26.2.
3. **Tree.** `tigie.py` reads the Tarifa between "TARIFA" and "Artículo 2o.": sections, chapters and
   their notes, and one table per chapter with code, dashes, description, unit and duties. It splits
   the Cámara's appended notes ("Arancel modificado … DOF …") off each description. The HS 2022
   six-digit level comes from the TIGIE's own text, never from WCO text.
4. **NICOs.** `nico.py` reads Artículo Primero of the acuerdo of DOF 2022-08-22 (in force with the
   LIGIE) and of its modifications (DOF 2023-06-30, in force 2023-07-01; DOF 2024-03-22), which
   create NICOs in their Artículo Primero and suppress others in their Segundo.
5. **Duties.** `decrees.py` and `timeline.py` start from the law's duties as published (in force
   2022-12-12) and apply every decree in order: **permanent** changes replace the Tarifa's duty from
   their date; **temporary** duties apply for their period, after which the Tarifa's duty applies
   again; abrogations, derogations and removals from the basic-basket list end them early; where two
   overlap the later decree rules; a later permanent duty ends the earlier temporary ones on its
   line. Entry-into-force dates were read by hand from each decree's transitorios, and the code
   checks the text still says what was read.
6. **Export.** `build.py` assembles the tables and `export.py` writes CSV, SQLite, JSON, the ZIP,
   the summary and `SHA256SUMS`.

### Decrees applied and not applied

| DOF | Publication | Applied |
|---|---|---|
| 2022-06-07 | Decree issuing the LIGIE | Base duties of 8,177 lines, in force 2022-12-12 |
| 2022-08-22 | NICO acuerdo | Base NICOs, in force 2022-12-12 |
| 2022-11-18 | Temporary exemption (codNota 5671925) | 72 lines; abrogated by the basic-basket decree from 2023-01-07 |
| 2022-11-18 | Tarifa amendment (codNota 5671926) | Art. Primero: 9 descriptions; art. Segundo: 112 steel lines at 15% with their phase-down, derogated from 2023-08-16; art. Cuarto: 5 lines until 2024-09-30; art. Quinto: 2 COVID-19 lines until 2023-05-09 |
| 2023-01-06 | Basic basket (canasta básica) | 105 lines exempt from 2023-01-07 (scoped ones included) |
| 2023-01-16 | White maize, export | Temporary IGE on 1 line, abrogated 2023-06-24 |
| 2023-05-18 | Basic basket | Additions and removals, 6 lines |
| 2023-06-23 | White maize | Temporary IGI and IGE on 1 line until 2023-12-31 |
| 2023-06-30 | NICO modification | Creations and suppressions from 2023-07-01 |
| 2023-08-15 | Tarifa amendment | 392 temporary lines; abrogated from 2024-04-23 |
| 2023-12-27 | Basic basket | In force until 2024-12-31 |
| 2024-03-22 | NICO modification | Creations and suppressions from 2024-03-22 |
| 2024-04-22 | Tarifa amendment (codNota 5724207) | 544 temporary lines, 2024-04-23 to 2026-04-23 |
| 2024-05-08 | Amendment of two decrees | 2 lines leave the earlier list; 1 permanent duty from 2024-05-09 |
| 2024-12-19 | Tarifa amendment | 155 temporary lines, 2024-12-20 to 2026-04-23 |
| 2024-12-31 | Basic basket | Additions and removals, 37 lines, from 2025-01-01 |
| 2025-07-21 | LIGIE reform | Chapter 03: 6 lines created and 5 reformed, in force 2026-01-17 |
| 2025-11-10 | Tarifa amendment | 8 permanent duties (sugar) from 2025-11-11 |
| 2025-12-29 | Reform of Tarifa lines | 1,463 permanent duties from 2026-01-01; ends the earlier temporary duties of 512 lines |
| 2025-12-31 | Basic basket | Removal of 33 lines from 2026-01-01; in force until 2026-12-31 |
| 2026-04-23 | Tarifa amendment | 185 permanent duties from 2026-04-24 |
| 2026-10-13 | Tarifa amendment | 1 line (9803.00.01) exempt 2026-10-14 to 2031-10-14 |

Not applied, with the reason in `aplicacion.csv`: Artículo Tercero of the 2022-11-18 decree (91
textile lines, derogated before it took effect); its Artículos Sexto to Décimo Quinto and the
articles of the 2024-12-19 and 2026-04-23 decrees that amend other decrees (IMMEX, PROSEC, border
region, used vehicles, quotas); the basic basket's administrative facilities (no duty change); and
the two tariff-rate-quota decrees (DOF 2024-04-22, coffee capsules, and DOF 2026-03-26), which set
the in-quota duty, not the general IGI.

### Cross-check against the consolidated text

The summary compares, for every line, the duty computed for 2026-10-14 with the one the Cámara's
consolidated text shows: 16,366 duties compared, 22 differences (`cotejo.csv`), all explained:

- 8 are partial basic-basket exemptions ("Únicamente de gallina", "Únicamente pan de caja"): the
  Cámara shows `Ex.` for the whole line; here the general duty stays and the exemption is a scoped
  measure.
- 12 are temporary duties that have ended but the consolidated text still shows: COVID-19 vaccines
  (until 2023-05-09), heading 8702 vehicles (until 2024-09-30), 4 lines of the 2023-08-15 decree
  (abrogated 2024-04-23), white maize (IGI and IGE, until 2023-12-31) and pepper, removed from the
  basic basket on 2025-01-01.
- 2 are errors of the consolidation on 5212.11.01 and 5212.12.01: the decree of DOF 2025-12-29 sets
  25 and 35; the Cámara shows 35 and 10.

## Limitations

- **Lines without a NICO.** 49 lines have no NICO in force: the 43 prohibited ones (the acuerdo does
  not list them) and the 6 lines the reform of DOF 2025-07-21 created in chapter 03, for which no
  NICO has been published yet.
- **Non-numeric duties.** 145 segments have no `valor_numerico`: 95 prohibitions and 50 specific or
  mixed duties (`AE`, `AMX`), kept as published text and not split into components.
- **General duty only.** The IGI is the Tarifa's, for goods without preferential treatment. Not
  included: treaty rates (USMCA and others), PROSEC, IMMEX, Regla Octava, tariff-rate quotas,
  countervailing duties, non-tariff regulations, nor the Notas Nacionales (acuerdo of DOF 2022-12-02)
  or the TIGIE 2020-2022 correlation (acuerdo of DOF 2022-07-14), which the Cámara also lists and
  this build does not read.
- **From 2022-12-12.** The TIGIE 2020 and duties before the LIGIE 2022 are not covered.
- **The Cámara's copies.** The sources are the Cámara de Diputados' informative copies; the DOF
  edition is the official one. Descriptions are taken as they are, typos included (one line uses
  the unit `M2`, the rest `M²`).
- **Dates read by hand.** Entry-into-force and end dates come from each decree's transitorios; the
  code checks the phrase each one relies on, but a misreading is possible. Future dates (the basic
  basket until 2026-12-31, 9803.00.01 until 2031-10-14) are what the decrees say as of 2026-10-13; a
  later decree needs a new release.
- **LibreOffice conversion.** The reader expects LibreOffice's HTML export and was tested with
  version 26.2. Another version could export tables differently; the tests and the cross-check
  would show it.

## Licence

The code is [MIT](LICENSE). The data is dedicated to the public domain under [CC0 1.0](LICENSE-DATA).
The source texts are Mexican federal legislative and administrative texts, which carry no copyright
under the Ley Federal del Derecho de Autor, artículo 14, fracción VIII. No World Customs
Organization text and no UN Comtrade data is included.

This data does not replace tariff classification or a customs broker's advice: before filing a
pedimento, check the duty in the DOF.

## Citation

See [CITATION.cff](CITATION.cff). For example: Baja Labs (2026). *tigie-nico-mx: TIGIE 2022 with
NICOs and duties dated by decree* (version 1.0.0). https://github.com/bajalabs/tigie-nico-mx

## Contributing

Data error reports are the most valuable contribution: open an issue with the "Data error" template
and give the line, the date and the DOF decree. For code changes, see
[CONTRIBUTING.md](CONTRIBUTING.md).
