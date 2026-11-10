# Changelog / Cambios

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/): a removed or renamed column is a major version, a new
column, table or decree is a minor version, a data correction is a patch.

## [1.0.0] - 2026-11-10

### Added

- The TIGIE 2022 tree from the Cámara de Diputados' consolidated text as of 2026-10-14: 22
  sections, 97 chapters, 1,235 partidas, 1,024 uncoded one-dash groups, 5,619 subpartidas (5,612
  Harmonized System 2022, 7 in chapter 98) and 8,183 fracciones with their UMT and published
  duties.
- 11,528 NICOs (11,507 in force) from the acuerdo of DOF 22-08-2022 and its modifications of DOF
  30-06-2023 and 22-03-2024, with their creation and suppression dates.
- 19,480 dated IGI and IGE segments from the LIGIE as published (in force 12-12-2022) through the
  decree of DOF 13-10-2026, with partial measures ("acotaciones") as scoped IGI.
- Notes, description histories, the source manifest with sha256, the decrees applied and not
  applied, and a cross-check against the consolidated Tarifa (22 explained differences).
- Outputs: one CSV per table, a ZIP of them, a SQLite database with four views, a JSON edition, a
  build summary and `SHA256SUMS`, all deterministic.
- The `capture`, `verify` and `build` commands (`python3 -m tigie_nico_mx`), standard library only.
