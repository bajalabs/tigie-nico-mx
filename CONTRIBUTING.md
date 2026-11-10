# Contribuir / Contributing

Gracias por ayudar. Las contribuciones más valiosas son los **errores en los datos**: una cuota,
una fecha, un NICO o una descripción que no coincide con el DOF. Abra un *issue* con la plantilla
«Error en los datos» e indique la fracción (8 dígitos), la fecha, lo que dicen los datos, lo que dice
el DOF y la publicación (fecha y título, o el enlace).

Thank you for helping. The most valuable contributions are **data errors**: a duty, date, NICO or
description that does not match the DOF. Open an issue with the "Data error" template.

## Construir y probar / Build and test

Python 3.12 or later, standard library only.

```sh
python3 -m unittest                        # the tests, on the fixtures in tests/fixtures/tariff
python3 -m tigie_nico_mx capture captura   # needs network and LibreOffice
python3 -m tigie_nico_mx build captura     # writes dist/
python3 -m tigie_nico_mx verify captura    # every Word file against its pinned sha256
```

`uv run python -m tigie_nico_mx ...` works the same. Code style: `ruff format` and `ruff check`
with the settings in `pyproject.toml` (line length 100).

## Proponer un cambio / Proposing a change

1. Open an issue first for anything larger than a typo, so the approach can be agreed.
2. Keep the column contract: the first columns of `subpartidas`, `fracciones`, `nicos` and `medidas`
   are never renamed or removed; new columns go at the end (`COLUMNS` in `tigie_nico_mx/build.py`).
3. Add or update a test. Tests run on small fixtures cut from the real files by
   `scripts/make_fixtures.py`; to cover a new fracción, add it to `FRACCIONES` there and regenerate
   them from a capture: `python3 scripts/make_fixtures.py captura tests/fixtures/tariff`.
4. Describe in the pull request what changed in the data (counts before and after, the
   `cotejo` differences) and add an entry to `CHANGELOG.md`.

## Un decreto nuevo / A new decree

When the Cámara regenerates `LIGIE_2022.doc` after a new decree, `capture` stops because a hash
differs. To add the decree:

1. Add the decree's Word file to `tigie_nico_mx/sources.json` (URL, DOF date, codNota from SIDOF,
   title, sha256) and update the consolidated text's sha256 and `consolidated_on`.
2. Read its transitorios by hand and add a step in `tigie_nico_mx/decrees.py` that applies it,
   with `require(...)` on the phrase each date relies on, and a `skipped(...)` for any article that
   does not change a general duty.
3. Rebuild, check that `cotejo.csv` gains no unexplained difference, and add a test.

## Conducta / Conduct

Be respectful and specific. Cite the DOF when you disagree with a value. Maintainers may close
issues that are not about this repository's data or code.
