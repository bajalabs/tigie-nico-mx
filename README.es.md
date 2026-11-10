[English](README.md) · **Español**

# tigie-nico-mx

[![CI](https://github.com/bajalabs/tigie-nico-mx/actions/workflows/ci.yml/badge.svg)](https://github.com/bajalabs/tigie-nico-mx/actions/workflows/ci.yml)
[![Código: MIT](https://img.shields.io/badge/c%C3%B3digo-MIT-blue.svg)](LICENSE)
[![Datos: CC0-1.0](https://img.shields.io/badge/datos-CC0--1.0-lightgrey.svg)](LICENSE-DATA)
[![Versión](https://img.shields.io/github/v/release/bajalabs/tigie-nico-mx)](https://github.com/bajalabs/tigie-nico-mx/releases/latest)

La Tarifa de la Ley de los Impuestos Generales de Importación y de Exportación (TIGIE 2022) con sus
NICO y cada arancel fechado por el decreto que lo fijó, en archivos abiertos (CSV, SQLite y JSON)
para importadores, agentes aduanales, analistas y desarrolladores.

- **8,183 fracciones arancelarias** con su descripción oficial, unidad de medida (UMT) y las cuotas
  de IGI e IGE que publica el texto vigente.
- **11,507 NICO vigentes** (11,528 con los 21 suprimidos), con la fecha en que cada uno se creó o
  se suprimió.
- **19,480 tramos de arancel** (IGI e IGE) desde la entrada en vigor de la LIGIE 2022
  (12-12-2022), cada uno con su decreto del DOF, fecha de inicio y de término, y su acotación cuando
  la medida cubre solo parte de la fracción.
- El árbol completo: 22 secciones, 97 capítulos, 1,235 partidas y 5,619 subpartidas (5,612 del
  Sistema Armonizado 2022 y 7 nacionales del capítulo 98), con el texto en español de la propia
  TIGIE, nunca textos de la OMA.

Todo se construye, de forma reproducible, a partir de los archivos Word que publica la Cámara de
Diputados, cada uno fijado por su sha256.

## Inicio rápido

Requisitos: Python 3.12 o posterior (solo biblioteca estándar) y, para descargar y convertir las
fuentes, LibreOffice (`brew install --cask libreoffice` en macOS, `sudo apt-get install -y
libreoffice-writer` en Ubuntu, o la variable `SOFFICE` con la ruta de `soffice`).

```sh
git clone https://github.com/bajalabs/tigie-nico-mx.git
cd tigie-nico-mx
python3 -m unittest                        # pruebas sobre los fixtures, en segundos
python3 -m tigie_nico_mx capture captura   # descarga 25 archivos Word (78 MB), verifica su sha256 y los convierte (unos 3 min)
python3 -m tigie_nico_mx build captura     # escribe dist/ (unos 10 s)
sqlite3 dist/tigie.sqlite "SELECT tipo, valor, desde, hasta FROM medidas WHERE fraccion = '72081003' ORDER BY tipo DESC, desde"
```

Con [uv](https://docs.astral.sh/uv/) funciona igual: `uv run python -m tigie_nico_mx ...`.

Si solo quiere los datos, cada versión adjunta los archivos de `dist/` en
[Releases](https://github.com/bajalabs/tigie-nico-mx/releases/latest), con su `SHA256SUMS`.

## Qué contiene

Conteos de la versión 1.0.0 (texto vigente de la Cámara al 14-10-2026; decretos hasta el DOF del
13-10-2026):

| Tabla | Filas | Qué es |
|---|---:|---|
| `secciones` | 22 | Secciones I a XXII con su título y sus capítulos |
| `capitulos` | 97 | Capítulos 01 a 98 (no existe el 77); `sistema_armonizado` = 0 solo para el 98 |
| `partidas` | 1,235 | Partidas de 4 dígitos, con el subcapítulo cuando la Tarifa lo usa |
| `grupos` | 1,024 | Subpartidas de un guion que la Tarifa no codifica; código de navegación de 5 dígitos |
| `subpartidas` | 5,619 | Subpartidas de 6 dígitos (5,612 del SA 2022, 7 del capítulo 98) |
| `fracciones` | 8,183 | Fracciones de 8 dígitos con UMT y cuotas publicadas y calculadas |
| `nicos` | 11,528 | NICO de 2 dígitos (11,507 vigentes, 21 suprimidos) |
| `medidas` | 19,480 | Tramos de IGI (11,277 generales y 17 con acotación) e IGE (8,186) |
| `notas` | 4,683 | Notas de sección y de capítulo, anotaciones de NICO, notas de la Cámara |
| `historial_descripciones` | 19 | Textos anteriores y nuevos de 14 fracciones que un decreto redactó de nuevo |
| `fuentes` | 25 | Cada archivo de origen con URL, fecha del DOF, codNota y sha256 |
| `aplicacion` | 34 | Qué se aplicó de cada decreto y qué no, con el motivo |
| `cotejo` | 22 | Diferencias entre la cuota calculada y la que muestra el texto vigente |

1,785 fracciones han tenido un IGI general fijado por un decreto distinto de la ley original; la de
historia más larga tiene seis tramos. 8,134 fracciones tienen al menos un NICO vigente.

### Archivos

| Archivo | Tamaño | Contenido |
|---|---:|---|
| `csv/*.csv` | 13.9 MB en total | Una tabla por archivo, UTF-8 sin BOM, con encabezado |
| `tigie-nico-mx-csv.zip` | 0.9 MB | Los mismos CSV comprimidos |
| `tigie.sqlite` | 16.9 MB | Las tablas con índices, la tabla `edicion` y cuatro vistas |
| `tigie.json` | 19.9 MB | Un documento: cada fracción con sus NICO, medidas y textos anidados |
| `resumen.json` | 26 KB | Conteos, hashes de las fuentes, aplicación de decretos, cotejo, advertencias |
| `SHA256SUMS` | 1.4 KB | sha256 de cada archivo anterior |

La construcción es determinista: la misma captura produce los mismos bytes (sin marcas de tiempo),
de modo que `SHA256SUMS` se puede comparar entre construcciones.

En Excel, abra los CSV con *Datos > Desde texto/CSV* y el origen *65001: Unicode (UTF-8)*; algunos
campos de texto contienen saltos de línea entre comillas.

## Diccionario de datos

Las fechas son ISO (`AAAA-MM-DD`). Los códigos van sin puntos y con ceros a la izquierda; léalos
como texto. Las cuotas siguen la convención de la Tarifa: un porcentaje sin el signo (`15`,
`210.44`), `Ex.` (exento), `Prohibida`, o un arancel específico o mixto tal como se publica (`AE
(0.36 Dls EUA por Kg)`, `AMX (20%+0.36 Dls por Kg de azúcar)`). Las primeras columnas de
`subpartidas`, `fracciones`, `nicos` y `medidas` son un contrato: nunca se renombran ni se quitan;
las columnas nuevas se agregan al final. En SQLite, un campo vacío es `NULL`.

**`fracciones`**

| Columna | Descripción |
|---|---|
| `fraccion` | 8 dígitos (`72081003` es 7208.10.03) |
| `subpartida` | 6 dígitos |
| `descripcion` | Texto de la fracción en el texto vigente, sin las notas que la Cámara agrega (esas van a `notas`) |
| `umt` | Unidad de medida de la Tarifa (`Kg`, `Pza`, `L`, `M²`, …), tal como se publica; vacía en las 43 fracciones prohibidas, donde la columna dice «Prohibida» |
| `igi_vigente`, `ige_vigente` | Cuotas de importación y exportación que muestra el texto vigente de la Cámara |
| `partida`, `capitulo` | 4 y 2 dígitos |
| `igi_calculado`, `ige_calculado` | Cuota general calculada a partir de los decretos en la fecha de corte (`edicion.fecha_corte_calculado`, 14-10-2026 por omisión; `build --as-of` la cambia) |
| `alta` | Primer día de vigencia de la fracción (12-12-2022, o la fecha del decreto que la creó) |
| `nicos_vigentes` | Número de NICO vigentes en la fecha de corte |
| `orden` | Orden de la fracción en la Tarifa |

**`subpartidas`**: `subpartida` (6 dígitos), `partida` (4), `capitulo` (2), `descripcion` (texto de
la TIGIE), `grupo` (el grupo sin código de 5 dígitos al que pertenece una subpartida de dos guiones,
o vacío), `sistema_armonizado` (1 para los capítulos 01–97; 0 para el 98, que es nacional), `orden`.

**`nicos`**

| Columna | Descripción |
|---|---|
| `fraccion`, `nico`, `codigo` | Fracción de 8 dígitos, NICO de 2, y el código de 10 que se declara en el pedimento |
| `descripcion` | Texto del NICO en el acuerdo |
| `alta` | Primer día de vigencia (12-12-2022 para el acuerdo base; 01-07-2023 y 22-03-2024 para sus modificaciones) |
| `baja` | Primer día en que el NICO ya no existe (fue suprimido); vacío si sigue vigente |
| `fuente_alta`, `fuente_baja` | Acuerdo del DOF que lo creó y que lo suprimió |

**`medidas`**

| Columna | Descripción |
|---|---|
| `fraccion` | 8 dígitos |
| `tipo` | `IGI` (importación) o `IGE` (exportación) |
| `valor` | La cuota del tramo |
| `desde` | Primer día en que rige |
| `hasta` | **Último** día en que rige (inclusivo); vacío si sigue abierta |
| `decreto` | `DOF dd-mm-aaaa: título` de la publicación que fijó la cuota |
| `alcance` | Vacío si la medida cubre toda la fracción; si no, la acotación («Únicamente pan de caja») |
| `valor_numerico` | Porcentaje ad valorem (0 para `Ex.`); vacío para específicos, mixtos y prohibidas |
| `decreto_fecha`, `decreto_codnota`, `decreto_url` | Fecha del DOF, número de nota del DOF y copia de la Cámara |
| `nota` | Por qué rige ese tramo y qué lo terminó (abrogación, eliminación de la lista, etc.) |

Para cada fracción y tipo, los tramos generales (`alcance` vacío) nunca se traslapan; la cuota de un
día es la del tramo que lo contiene. Un tramo con `alcance` convive con el general: es una
exención o cuota parcial para algunas mercancías de la fracción.

**Otras tablas**

- `secciones`: `seccion` (I–XXII), `numero`, `titulo`, `capitulos` (separados por espacios).
- `capitulos`: `capitulo`, `seccion`, `descripcion`, `sistema_armonizado`, `orden`.
- `partidas`: `partida`, `capitulo`, `descripcion`, `subcapitulo`, `orden`.
- `grupos`: `grupo` (5 dígitos, solo para navegar; no es un código oficial), `partida`,
  `descripcion`, `orden`.
- `notas`: `nivel` (`seccion`, `capitulo`, `partida`, `grupo`, `subpartida`, `fraccion`), `codigo`,
  `tipo` (`notas_seccion`, `notas_capitulo`, `anotaciones_nico`, `subcapitulo`, `sin_codigo`,
  `nota_camara`), `texto`, `fuente`.
- `historial_descripciones`: `fraccion`, `desde`, `hasta` (inclusivo), `descripcion`, `decreto`.
- `fuentes`: `clave`, `archivo`, `url`, `dof`, `codnota`, `titulo`, `sha256`, `papel`.
- `aplicacion`: `clave`, `decreto`, `aplicado` (`si`/`no`), `que`, `fracciones`, `motivo`.
- `cotejo`: `fraccion`, `tipo`, `publicado`, `calculado`, `medida_parcial`, `ultima_nota_camara`.

**Vistas de SQLite** (la fecha es la del equipo que consulta):

- `v_fracciones`: cada fracción con la descripción de su subpartida, grupo, partida, capítulo y
  sección.
- `v_arancel_hoy`: IGI e IGE generales de hoy por fracción, y las cuotas parciales vigentes.
- `v_medidas_hoy`: los tramos que rigen hoy.
- `v_nicos_vigentes`: los NICO vigentes hoy.

## Consultas de ejemplo

Historia del IGI y el IGE de una fracción (7208.10.03, acero laminado en caliente):

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

Los NICO de una subpartida (8414.51, ventiladores), con los que se crearon y suprimieron:

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

La cuota de una fecha (maíz blanco, 1005.90.04, el 31-12-2023):

```sql
SELECT valor, decreto FROM medidas
WHERE fraccion = '10059004' AND tipo = 'IGI' AND alcance IS NULL
  AND desde <= '2023-12-31' AND (hasta IS NULL OR hasta >= '2023-12-31');
-- 50, DOF 23-06-2023
```

El arancel de hoy, con las exenciones parciales:

```sql
SELECT fraccion, igi, ige, igi_parcial FROM v_arancel_hoy WHERE fraccion = '19054001';
-- 19054001 | 10 | Ex. | Ex. (Únicamente pan de caja.)
```

Desde Python, sin dependencias:

```python
import csv

with open("dist/csv/fracciones.csv", encoding="utf-8", newline="") as f:
    fracciones = {r["fraccion"]: r for r in csv.DictReader(f)}
print(fracciones["84713001"]["descripcion"], fracciones["84713001"]["igi_vigente"])
```

## Cómo se construye

1. **Fuentes.** [`tigie_nico_mx/sources.json`](tigie_nico_mx/sources.json) lista los 25 archivos
   Word de la Cámara de Diputados ([índice de la LIGIE](https://www.diputados.gob.mx/LeyesBiblio/ref/ligie_2022.htm)),
   cada uno con su URL, fecha del DOF, codNota y sha256: el texto vigente consolidado
   (`doc/LIGIE_2022.doc`, regenerado por la Cámara el 14-10-2026), la ley como se publicó (DOF
   07-06-2022), sus dos reformas, los dieciséis decretos que modifican la Tarifa (más dos que
   modifican aranceles-cupo) y los tres acuerdos de NICO.
2. **Captura.** `python3 -m tigie_nico_mx capture <carpeta>` descarga cada archivo con un segundo de
   pausa, compara su sha256 con el fijado y se detiene si difiere (un hash nuevo significa que la
   Cámara regeneró el texto, normalmente por un decreto nuevo). Después convierte cada Word a HTML
   con LibreOffice (`soffice --headless --convert-to html`, perfil desechable). La conversión se
   probó con LibreOffice 26.2.
3. **Árbol.** `tigie.py` lee la Tarifa entre «TARIFA» y «Artículo 2o.»: secciones, capítulos y sus
   notas, y una tabla por capítulo con código, guiones, descripción, unidad e impuestos. Separa de
   cada descripción las notas que la Cámara agrega («Arancel modificado … DOF …»). El nivel de 6
   dígitos del Sistema Armonizado 2022 sale del texto de la propia TIGIE, nunca de textos de la OMA.
4. **NICO.** `nico.py` lee el Artículo Primero del acuerdo del DOF 22-08-2022 (en vigor con la
   LIGIE) y de sus modificaciones (DOF 30-06-2023, en vigor el 01-07-2023; DOF 22-03-2024), que crean
   NICO en su Artículo Primero y suprimen otros en el Segundo.
5. **Aranceles.** `decrees.py` y `timeline.py` parten de las cuotas de la ley como se publicó (en
   vigor el 12-12-2022) y aplican cada decreto en orden: los cambios **permanentes** sustituyen la
   cuota de la Tarifa desde su fecha; las cuotas **temporales** rigen por su periodo y al terminar
   vuelve la cuota de la Tarifa; las abrogaciones, derogaciones y eliminaciones de la lista de la
   canasta básica las terminan antes; cuando dos se traslapan rige el decreto posterior; una cuota
   permanente posterior termina las temporales anteriores de su fracción. Las fechas de entrada en
   vigor se leyeron a mano de los transitorios, y el código verifica que el texto todavía diga lo que
   se leyó.
6. **Exportación.** `build.py` arma las tablas y `export.py` escribe CSV, SQLite, JSON, el ZIP, el
   resumen y `SHA256SUMS`.

### Decretos aplicados y no aplicados

| DOF | Publicación | Se aplicó |
|---|---|---|
| 07-06-2022 | Decreto por el que se expide la LIGIE | Cuotas base de 8,177 fracciones, en vigor el 12-12-2022 |
| 22-08-2022 | Acuerdo de NICO | NICO base, en vigor el 12-12-2022 |
| 18-11-2022 | Exención temporal de arancel (codNota 5671925) | 72 fracciones; abrogado por el de la canasta básica desde el 07-01-2023 |
| 18-11-2022 | Modificación de la Tarifa (codNota 5671926) | Art. Primero: 9 descripciones; art. Segundo: 112 fracciones de acero al 15% con su calendario, derogado desde el 16-08-2023; art. Cuarto: 5 fracciones hasta el 30-09-2024; art. Quinto: 2 fracciones COVID-19 hasta el 09-05-2023 |
| 06-01-2023 | Canasta básica | 105 fracciones exentas desde el 07-01-2023 (incluidas las acotaciones) |
| 16-01-2023 | Maíz blanco, exportación | IGE temporal de 1 fracción, abrogado el 24-06-2023 |
| 18-05-2023 | Canasta básica | Altas y bajas de 6 fracciones |
| 23-06-2023 | Maíz blanco | IGI e IGE temporales de 1 fracción hasta el 31-12-2023 |
| 30-06-2023 | Modificación de NICO | Altas y supresiones desde el 01-07-2023 |
| 15-08-2023 | Modificación de la Tarifa | 392 fracciones temporales; abrogado desde el 23-04-2024 |
| 27-12-2023 | Canasta básica | Vigencia ampliada al 31-12-2024 |
| 22-03-2024 | Modificación de NICO | Altas y supresiones desde el 22-03-2024 |
| 22-04-2024 | Modificación de la Tarifa (codNota 5724207) | 544 fracciones temporales del 23-04-2024 al 23-04-2026 |
| 08-05-2024 | Reforma a dos decretos | 2 fracciones salen de la lista anterior; 1 cuota permanente desde el 09-05-2024 |
| 19-12-2024 | Modificación de la Tarifa | 155 fracciones temporales del 20-12-2024 al 23-04-2026 |
| 31-12-2024 | Canasta básica | Altas y bajas de 37 fracciones desde el 01-01-2025 |
| 21-07-2025 | Reforma a la LIGIE | Capítulo 03: 6 fracciones creadas y 5 reformadas, en vigor el 17-01-2026 |
| 10-11-2025 | Modificación de la Tarifa | 8 cuotas permanentes (azúcar) desde el 11-11-2025 |
| 29-12-2025 | Reforma de fracciones de la Tarifa | 1,463 cuotas permanentes desde el 01-01-2026; terminan las temporales anteriores de 512 fracciones |
| 31-12-2025 | Canasta básica | Bajas de 33 fracciones desde el 01-01-2026; vigencia hasta el 31-12-2026 |
| 23-04-2026 | Modificación de la Tarifa | 185 cuotas permanentes desde el 24-04-2026 |
| 13-10-2026 | Modificación de la Tarifa | 1 fracción (9803.00.01) exenta del 14-10-2026 al 14-10-2031 |

No se aplicó, con su motivo en `aplicacion.csv`: el artículo Tercero del decreto del 18-11-2022
(91 fracciones textiles, derogado antes de entrar en vigor); sus artículos Sexto a Décimo Quinto y
los artículos de los decretos del 19-12-2024 y del 23-04-2026 que modifican otros decretos (IMMEX,
PROSEC, región fronteriza, vehículos usados, cupos); las facilidades administrativas de la canasta
básica (no cambian la cuota); y los dos decretos de aranceles-cupo (DOF 22-04-2024, café en
cápsulas, y DOF 26-03-2026), que fijan la cuota dentro de un cupo y no el IGI general.

### Cotejo con el texto vigente

El resumen compara, para cada fracción, la cuota calculada al 14-10-2026 con la que muestra el texto
vigente de la Cámara: 16,366 cuotas comparadas, 22 diferencias (`cotejo.csv`), todas explicadas:

- 8 son exenciones parciales de la canasta básica («Únicamente de gallina», «Únicamente pan de
  caja»): la Cámara muestra `Ex.` para toda la fracción; aquí la cuota general queda y la exención va
  como medida con `alcance`.
- 12 son cuotas temporales que ya terminaron y que el texto vigente todavía muestra: vacunas
  COVID-19 (hasta el 09-05-2023), vehículos de la partida 8702 (hasta el 30-09-2024), 4 fracciones
  del decreto del 15-08-2023 (abrogado el 23-04-2024), el maíz blanco (IGI e IGE, hasta el
  31-12-2023) y la pimienta, eliminada de la canasta básica el 01-01-2025.
- 2 son errores de la consolidación en 5212.11.01 y 5212.12.01: el decreto del DOF 29-12-2025 fija 25
  y 35; la Cámara muestra 35 y 10.

## Limitaciones

- **Fracciones sin NICO.** 49 fracciones no tienen NICO vigente: las 43 prohibidas (el acuerdo no las
  lista) y las 6 que la reforma del DOF 21-07-2025 creó en el capítulo 03, para las que aún no se
  publica NICO.
- **Cuotas no numéricas.** 145 tramos no tienen `valor_numerico`: 95 prohibiciones y 50 aranceles
  específicos o mixtos (`AE`, `AMX`), que se conservan como texto tal como se publican, sin
  separarlos en componentes.
- **Solo la cuota general.** El IGI es el de la Tarifa, aplicable a mercancías sin trato
  preferencial. No incluye tasas de tratados (T-MEC y otros), PROSEC, IMMEX, Regla Octava,
  aranceles-cupo, cuotas compensatorias, regulaciones y restricciones no arancelarias, ni las Notas
  Nacionales (acuerdo del DOF 02-12-2022) o la correlación TIGIE 2020-2022 (acuerdo del DOF
  14-07-2022), que la Cámara también lista y aquí no se leen.
- **Desde el 12-12-2022.** No cubre la TIGIE 2020 ni las cuotas anteriores a la LIGIE 2022.
- **Copias de la Cámara.** Las fuentes son las copias informativas de la Cámara de Diputados; la
  edición oficial es la del DOF. Las descripciones se toman como están, con sus erratas (por ejemplo,
  una fracción usa la unidad `M2` y las demás `M²`).
- **Fechas leídas a mano.** Las fechas de entrada en vigor y de término vienen de los transitorios
  de cada decreto; el código verifica la frase en que se basa cada una, pero un error de lectura es
  posible. Las fechas futuras (la canasta básica hasta el 31-12-2026, 9803.00.01 hasta el
  14-10-2031) son las que dicen los decretos al 13-10-2026; un decreto posterior requiere una nueva
  versión.
- **Conversión con LibreOffice.** El lector espera el HTML que exporta LibreOffice; se probó con la
  versión 26.2. Otra versión podría exportar tablas de forma distinta; las pruebas y el cotejo lo
  detectarían.

## Licencia

El código está bajo [MIT](LICENSE). Los datos se dedican al dominio público con
[CC0 1.0](LICENSE-DATA). Los textos de origen son legislativos y administrativos federales y, conforme
al artículo 14, fracción VIII, de la Ley Federal del Derecho de Autor, no son objeto de protección
como derecho de autor. No se incluyen textos de la Organización Mundial de Aduanas ni datos de UN
Comtrade.

Estos datos no sustituyen la clasificación arancelaria ni la asesoría de un agente aduanal: antes de
un pedimento, verifique la cuota en el DOF.

## Cita

Vea [CITATION.cff](CITATION.cff). Por ejemplo: Baja Labs (2026). *tigie-nico-mx: TIGIE 2022 con
NICO y aranceles fechados por decreto* (versión 1.0.0).
https://github.com/bajalabs/tigie-nico-mx

## Contribuir

Los reportes de errores en los datos son lo más valioso: abra un *issue* con la plantilla «Error en
los datos» e indique la fracción, la fecha y el decreto del DOF. Para cambios de código, vea
[CONTRIBUTING.md](CONTRIBUTING.md).
