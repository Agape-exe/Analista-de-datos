# Data Intake & Understanding

> Actualización del integrante 5: ver [guía de integración](integrante5-integracion.md).
> Las descripciones del skeleton de análisis reflejan la base original; la API de
> análisis y reporting se extendió en esta entrega.

## AUD-013 — Calidad del dataset registrado

`GET /datasets/{dataset_id}/quality` evalúa faltantes, filas completamente
duplicadas y dos reglas deterministas sobre el dataset publicado por `/intake`.
Usa `IntakeResponse.profile.dataset_id`; no recibe un archivo ni ejecuta intake,
perfilado estadístico o limpieza otra vez. La futura pantalla AUD-014 puede
consumir este contrato sin depender de nuevas capacidades de Exploration.
No se implementa frontend, AUD-014 ni AUD-018.

### Contrato y estados

Sin parámetros adicionales ni configuración de reglas desde HTTP. La ruta sigue
la convención del preview AUD-009. Respuesta Pydantic/OpenAPI `DatasetQuality`:

| Campo | Significado |
| --- | --- |
| `dataset_id` | Identificador existente, no uno secuencial nuevo |
| `status` | `EVALUATED` o `NOT_EVALUATED` para tablas sin filas o sin columnas |
| `total_rows`, `total_columns`, `total_cells` | Dimensiones y producto filas × columnas |
| `missing.missing_cells`, `missing.missing_percentage` | Faltantes sobre todas las celdas |
| `missing.incomplete_rows`, `missing.complete_rows` | Filas con al menos un faltante y complemento |
| `missing.columns` | Nombre, tipo técnico, conteo y porcentaje faltante por columna, en orden original |
| `duplicates.duplicate_rows` | Apariciones adicionales: se excluye la primera de cada grupo |
| `duplicates.duplicate_groups` | Grupos distintos con dos o más filas iguales |
| `duplicates.duplicate_percentage` | Apariciones adicionales / total de filas × 100 |
| `rules` | Identificador, descripción, estado, conteo observado y motivo cuando corresponde |

Los porcentajes son números en escala **0–100**, sin umbrales de aceptación ni
redondeo obligatorio. Un denominador cero produce 0%; eso no acredita una regla.
En una tabla con cero columnas y N filas se cuentan N filas completas por
ausencia de faltantes, pero las reglas y la evaluación son `NOT_EVALUATED`.

Reglas iniciales (sin puntuación global ni umbrales oficiales inventados):

- `NO_MISSING_VALUES`: PASS si no hay celdas faltantes; FAIL si hay alguna.
- `NO_DUPLICATE_ROWS`: PASS si no hay filas duplicadas adicionales; FAIL si hay alguna.
- Ambas son NOT_EVALUATED si no existen filas o columnas. `observed_count` es
  null y `reason` explica la ausencia de evidencia. En FAIL se devuelve el conteo
  real y un motivo; en PASS el conteo es cero. Métricas y decisiones son campos
  separados. Las reglas puras pueden ampliarse sin un motor genérico ni cambios
  de infraestructura; no hay API de reglas arbitrarias.

### Nulos y duplicados: definición exacta

Se respetan los nulos de la tabla tipada por Intake: campos CSV/TSV vacíos o con
solo espacios se cargan como nulos. Los textos literales `NA`, `NULL`, `NaN` y
`nan` **son valores válidos**, no marcadores de ausencia. En proveedores de
prueba se admiten None, pd.NA, NaN y NaT; todos representan ausencia. El texto
vacío de un proveedor ya registrado se conserva como texto: no se repite la
normalización de ingreso. Los conteos del perfil registrado se reutilizan si
coinciden dataset_id, dimensiones y columnas; si faltan, se cuentan las máscaras
de nulos locales. Se presupone la inmutabilidad del dataset registrado.

Dos filas son duplicadas si coinciden en **todas las columnas correspondientes**,
con igualdad de valores tipados. Los nulos en la misma posición son iguales entre
sí. No hay ordenamiento, filtrado, trim, conversión de texto a número, normalización
de mayúsculas ni modificación del índice. Un valor repetido en una sola columna
no convierte la fila completa en duplicada.

En columnas mixtas object, booleanos, enteros, floats, Decimal y texto se distinguen
por familia: True, 1, 1.0, Decimal('1') y "1" son distintos; "001" conserva sus
ceros. Dentro de una misma familia rige igualdad de valor, por ejemplo Decimal
`1.20` y `1.2`. En tipos nativos/nullable de Pandas se usa la igualdad del tipo
ya cargado; una coerción anterior a AUD-013 no puede deshacerse. Se admiten
fechas/horas y duraciones escalares; estructuras anidadas, bytes, complejos,
categorías, tipos no reconocidos e infinitos se rechazan. No se invocan métodos
de representación ni serialización de objetos arbitrarios.

Ejemplo `001,Ana / 002,Luis / 002,Luis`: tres filas, una aparición duplicada
adicional y un grupo. Un grupo de tres filas iguales tiene dos adicionales.
Se devuelven solo agregados: ninguna fila, índice, ejemplo de celda o ruta local.

### Implementación y límites

- `EvaluateDatasetQuality` resuelve `DatasetProvider`, valida presupuestos y
  coherencia de conteos, construye el DTO y aplica reglas puras de domain.
- `DatasetQualityReader` es un puerto nuevo específico; no cambia `LocalTable`,
  `DatasetProvider` ni contratos compartidos.
- `PandasDatasetQualityReader` opera sobre `PandasLocalTable` en un worker local.
  Calcula máscaras por columna y un acumulador de filas incompletas, reutilizando
  los conteos existentes. Factoriza cada columna y compara filas de códigos
  enteros con Pandas; las colisiones de hash se resuelven por igualdad, no por
  una estimación probabilística. Las máscaras/claves se construyen por columna,
  sin copiar el DataFrame original ni convertirlo a JSON o listas de filas.
- Bootstrap y `create_app` inyectan dependencias; HTTP solo coordina protecciones,
  caso de uso y traducción de errores. Application/domain no importan Pandas ni
  FastAPI. La cancelación espera al worker para no liberar capacidad prematuramente.
- Se reutilizan almacén LRU, perfil, identificadores, rate limit `exploration` y
  reserva de capacidad compartidos. `missing_values` continúa intacta: su salida
  se comprueba contra calidad en integración. No se importa su implementación
  privada entre módulos ni se materializan todas las columnas con `column()`.

Política local `QualityLimits` (inyectable, sin ajustes nuevos de despliegue):

| Presupuesto por evaluación | Máximo |
| --- | --- |
| Filas | 250.000 |
| Columnas | 1.000 |
| Celdas | 2.000.000 |
| Memoria estimada de valores (`memory_usage(deep=True)`, sin índice) | 64 MiB |
| Texto escalar | 65.536 caracteres |
| Respuesta JSON UTF-8, incluidos nombres, métricas y reglas | 1 MiB |

Los límites de forma se comprueban antes de recorrer datos y también dentro del
adaptador; memoria antes de factorizar; texto antes de hash/claves; metadatos
antes de evaluar y JSON final antes de devolver. Los enteros/Decimal object
tienen además guardas de tamaño de representación interna. No se truncan
valores ni se muestrea para producir conteos aparentemente exactos.

Complejidad esperada O(filas × columnas + longitud del contenido), con memoria
auxiliar O(filas × columnas) para códigos enteros (hasta unos 16 MB), máscaras
O(filas) y claves de una columna cada vez. Pandas también utiliza tablas hash y
buffers temporales. **64 MiB es un presupuesto de datos de entrada, no una cota
exacta del RSS total**; los límites de forma y concurrencia acotan esas otras
asignaciones. No hay cola nueva, servicio distribuido, caché adicional sin límite
ni plazo de ejecución garantizado. Para datasets mayores se rechaza la operación
completa; no se prometen métricas parciales. La política puede ajustarse mediante
composición, con validación positiva, sin confundirla con reglas de calidad.

### Errores, seguridad y persistencia

| HTTP / código | Situación |
| --- | --- |
| 404 `DATASET_NOT_FOUND` | Nunca registrado, expulsado por LRU o perdido tras reinicio |
| 413 `QUALITY_TOO_LARGE` | Evaluación o respuesta excede presupuestos |
| 422 `QUALITY_UNSUPPORTED` | Tabla, estructura, tipo de valor o conteos inconsistentes no soportados |
| 429 `REQUEST_RATE_LIMITED` | Límite compartido de solicitudes (`Retry-After`) |
| 429 `ANALYSIS_CAPACITY_EXCEEDED` | Capacidad de operaciones compartida ocupada (`Retry-After`) |

Los errores esperados no incluyen valores, filas, rutas ni detalles internos.
La respuesta exitosa usa `Cache-Control: no-store`; los logs compartidos solo
registran identificador de solicitud, método y estado, sin celdas. El almacén es
temporal, por capacidad LRU y por proceso, **sin TTL ni persistencia durable**.
Si un dataset deja de estar disponible debe cargarse de nuevo. No existe
aislamiento multiusuario/autenticación; usar datos sintéticos o públicos en demos
y proteger el acceso al servidor. Esta entrega no implementa autenticación.

### Reproducción HTTP en PowerShell

Desde la raíz del worktree, iniciar en otra terminal:

```powershell
uv run uvicorn app.api.main:app --host 127.0.0.1 --port 8013
```

Carga sintética, consulta y evidencia fuera del repositorio:

```powershell
$csvPath = Join-Path (Split-Path (Get-Location) -Parent) 'aud013-synthetic.csv'
[IO.File]::WriteAllText($csvPath, "id,nombre,valor`n001,Ana,10`n002,Luis,`n002,Luis,`n",
    [Text.UTF8Encoding]::new($false))
$loaded = curl.exe -sS -F "file=@$csvPath" -F 'delimiter=,' http://127.0.0.1:8013/intake |
    ConvertFrom-Json
$datasetId = $loaded.profile.dataset_id
Invoke-RestMethod "http://127.0.0.1:8013/datasets/$datasetId/quality" |
    ConvertTo-Json -Depth 10 | Tee-Object -FilePath ..\aud013-quality-http-evidence.txt
curl.exe -sS -i http://127.0.0.1:8013/datasets/inexistente/quality
```

Ejemplo de respuesta (dataset_id ilustrativo; el real es un UUID de Intake):

```json
{
  "dataset_id": "uuid-generado-por-intake",
  "status": "EVALUATED",
  "total_rows": 3,
  "total_columns": 3,
  "total_cells": 9,
  "missing": {
    "missing_cells": 2,
    "missing_percentage": 22.22222222222222,
    "incomplete_rows": 2,
    "complete_rows": 1,
    "columns": [
      {"column_name": "id", "data_type": "string", "missing_count": 0, "missing_percentage": 0},
      {"column_name": "nombre", "data_type": "string", "missing_count": 0, "missing_percentage": 0},
      {"column_name": "valor", "data_type": "Int64", "missing_count": 2, "missing_percentage": 66.66666666666667}
    ]
  },
  "duplicates": {"duplicate_rows": 1, "duplicate_percentage": 33.333333333333336, "duplicate_groups": 1},
  "rules": [
    {"rule_id": "NO_MISSING_VALUES", "description": "Ausencia de valores faltantes", "status": "FAIL", "observed_count": 2, "reason": "Se observaron incumplimientos de la regla."},
    {"rule_id": "NO_DUPLICATE_ROWS", "description": "Ausencia de filas completamente duplicadas", "status": "FAIL", "observed_count": 1, "reason": "Se observaron incumplimientos de la regla."}
  ]
}
```

Para un dataset limpio repetir la carga con `id,valor / 001,10 / 002,20`: ambos
conteos son cero y ambas reglas PASS. Las pruebas utilizan estos escenarios y
proveedores sintéticos para tablas vacías, tipos mixtos/no soportados y límites.

### Pruebas y compatibilidad

```powershell
uv sync --locked
uv run python -m pytest tests/unit/test_dataset_quality.py -q
uv run python -m pytest tests/integration/test_dataset_quality_api.py -q
uv run python scripts/check_architecture.py
uv run python -m pytest tests/architecture -q
uv run python -m pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

`openapi_develop.json` y `openapi_preview.json` se mantienen intactas; la prueba
de contrato compara la única ruta nueva y sus seis esquemas con
`openapi_quality.json`, y exige igualdad completa del resto. Se validan intake,
preview, Exploration, LRU, protecciones, inmutabilidad y ausencia de relectura o
filtraciones. Los tipos para AUD-014 pueden generarse con el script oficial del
frontend; esta entrega valida la generación y un consumidor TypeScript fuera
del repositorio, y compila el frontend existente sin modificarlo.

#### Validación local de AUD-013 — 17 de octubre de 2026

Worktree `Analista-de-datos-aud013`, rama `feat/aud-013-data-quality`, base
`098db077378be909345ae4677fe609035dff049d` de `origin/develop`, con PR #28, #29,
#33 y #34 incorporados. No se encontró una especificación adicional de AUD-013
en la documentación vigente ni en la búsqueda de issues por su identificador.

| Verificación | Línea base | Con AUD-013 |
| --- | --- | --- |
| `uv sync --locked` | Correcto | Correcto |
| Comprobador AST | 167 archivos, correcto | 172 archivos, correcto |
| Arquitectura | 24 aprobadas | 24 aprobadas |
| Suite backend | 468 aprobadas, 4 fallidas | 563 aprobadas, las mismas 4 fallidas |
| Unitarias nuevas | No existían | 70 aprobadas |
| Integración nueva | No existía | 25 aprobadas |
| Ruff general | 2 errores ajenos | Los mismos 2 errores |
| Formato Python | 257 archivos correctos | 264 archivos correctos |
| OpenAPI | Contratos existentes | Contratos anteriores intactos y snapshot aditiva |
| Generación TypeScript, consumidor del DTO y build existente | Sin cambios frontend | Correctos |

Los fallos completos, reconfirmados antes y después, corresponden a:

- `test_anova_planning.py::test_fast_mode_uses_next_valid_anova_after_omitting_sparse_pair`.
- `test_critic_pipeline.py::test_default_csv_produces_measured_critic_and_insights_without_a_question`.
- `test_critic.py::test_critic_reports_significant_results_without_robustness_as_preliminary`.
- `test_critic.py::test_critic_skips_when_no_result_is_significant`.

Ruff mantiene F841 `unranked` en analysis_planning.py:273 y F401
`AssociationResult` en test_planner_agent.py:10. No se modificaron esos módulos
ni pruebas. No se identifican regresiones nuevas en las comprobaciones ejecutadas.

Evidencia local fuera del repositorio, en el directorio padre del worktree:
`aud013-quality-http-evidence.txt` contiene respuestas HTTP reales de TestClient
para datos con faltantes/duplicados, datos limpios, preview compatible y errores
404/413/422. Los logs `aud013-unit-tests.log`, `aud013-integration-tests.log`,
`aud013-final-architecture*.log`, `aud013-final-pytest.log`, `aud013-final-ruff.log`
y `aud013-final-format.log` conservan las ejecuciones. La generación oficial
se redirigió a `aud013-generated-api.ts`, fuera del worktree; el consumidor
`aud013-types-consumer.ts` compiló con TypeScript estricto. No se modificaron
tipos frontend ni se implementó AUD-014. Resultados locales, no CI de GitHub.

## Uso directo

Desde la raíz del proyecto:

```python
import asyncio

from app.shared.contracts.analysis_input import AnalysisInput
from app.bootstrap import build_data_understanding
from app.shared.config.settings import Settings


async def main() -> None:
    service = build_data_understanding(Settings())
    result = await service.understand(
        AnalysisInput(source={"kind": "tsv", "path": "tests/fixtures/sample.tsv"})
    )
    print(result.summary().model_dump_json(indent=2))


asyncio.run(main())
```

Para el fixture de tres filas, el resumen contiene `rows=3`, `columns=5`,
`numeric_columns=["amount"]`, `categorical_columns=["segment", "active"]`,
`temporal_columns=["created_at"]` e `identifiers=["customer_id"]`. También expone
`text_columns`, `unknown_columns` y `data_dictionary`. Estos datos provienen de
la lectura y clasificación del fixture.

## Lectura

- CSV acepta delimitador y encoding en su contrato; TSV usa tabulador.
- Se valida archivo legible, encabezado no vacío, nombres únicos y anchura exacta
  de filas, incluidas filas con campos faltantes. Las líneas completamente vacías
  se omiten. Encabezados se normalizan quitando espacios externos y BOM UTF-8.
- Se rechazan fuentes sin filas y fuentes completamente vacías de valores.
- Solo campos vacíos o de espacios se tratan como nulos. `NA`, `NULL` y `NaN`
  permanecen como texto; no se presupone una convención de valores faltantes.
- Enteros/decimales y booleanos textuales true/false se detectan conservadoramente.
  Códigos con ceros iniciales y conversiones numéricas que perderían precisión
  permanecen como texto. Fechas conservan sus valores originales.
- SQL y TXT devuelven un error de adaptador no configurado.

## Tipos y roles

`data_type` registra el tipo físico observado. `semantic_type` usa:
`numeric`, `categorical`, `temporal`, `identifier`, `text`, `unknown`.

- IDs: nombre explícito y valores discretos, UUID o códigos con ceros iniciales
  suficientemente únicos. Un número continuo único sigue siendo numérico.
- IDs repetidos siguen siendo candidatos; se advierte que pueden ser claves
  foráneas. La clasificación no garantiza una clave primaria válida.
- Fechas: formato configurado y proporción mínima de valores reconocidos. El
  default exige coincidencia de todos los valores no nulos con un mismo formato.
  Fechas ambiguas como `01/02/2026` no son temporales sin configurar su formato.
- Booleanos son categóricos. Números de baja cardinalidad permanecen numéricos
  salvo un rol explícito y compatible en el diccionario.
- Texto corto con cardinalidad configurada es categórico; nombres de texto libre
  y cadenas fuera de esa política se clasifican como texto.
- Columnas sin valores observados son desconocidas.

Los umbrales están en `[data_intake]` de `defaults.toml`; se sobrescriben mediante
TOML externo o `MDA_DATA_INTAKE__...`. Esta política es global al servicio; los
overrides por análisis siguen limitados a analysis/performance. Los nombres de
tokens se configuran en minúsculas. No se ejecuta EDA estadístico avanzado ni LLM.

## Diccionario y esquema suministrados

El diccionario se recibe como `AnalysisInput.data_dictionary` y se valida con
Pydantic. No se añade un formato de archivo distinto al contrato compartido.

- Entradas originales conservan source, descripción, unidad y confianza.
- Columnas omitidas reciben entradas `inferred`.
- Campos faltantes de entradas originales se completan y se identifican en
  `inferred_fields`; eso no convierte su source original en official.
- `inference_reason` explica el fundamento estructural. Las descripciones inferidas
  indican que el significado de negocio no está verificado. No se inventan unidades
  ni puntuaciones de confianza: confidence queda en None si no fue suministrada.
- Un rol explícito compatible tiene prioridad. Numeric y temporal se contrastan
  con valores observados. Las discrepancias y roles no soportados producen warnings;
  se conserva la declaración original y el perfil refleja los valores observados.
- Las entradas de columnas inexistentes se excluyen del diccionario efectivo con
  una advertencia. La entrada original no se modifica.
- Un esquema con columnas diferentes falla. Tipos físicos declarados distintos
  generan advertencias, sin forzar conversiones silenciosas. Nulos en columnas
  declaradas no-nullables causan un error de validación.

## Integración y contratos compartidos

### AUD-009 — Vista previa backend del dataset registrado

`GET /datasets/{dataset_id}/preview` devuelve una página de los valores ya
registrados por `/intake`. Sigue la convención `/datasets/{dataset_id}/...` de
exploración y pertenece al adaptador HTTP de Data Intake. No se crea una pantalla
React: la futura AUD-010 podrá consumir este contrato usando
`IntakeResponse.profile.dataset_id`.

| Parámetro | Predeterminado | Rango |
| --- | --- | --- |
| `dataset_id` | Obligatorio | Identificador opaco devuelto por intake |
| `offset` | 0 | Entero entre 0 y 9007199254740991, inclusive |
| `limit` | 20 | Entero entre 1 y 100, inclusive |

La posición comienza en cero; no es un identificador de negocio ni una referencia
persistente a una fila. No se ordena, filtra ni modifica el dataset. Un `offset`
igual o superior al total devuelve una página vacía con `has_more=false` y
`next_offset=null`. También se admiten datasets vacíos de proveedores de prueba,
aunque el intake normal rechaza archivos sin filas.

Respuesta `DatasetPreview`:

- `dataset_id`: dataset consultado.
- `columns`: esquema observado en orden original, con `name`, `data_type` y
  `nullable`, reutilizando `ColumnSchema`.
- `rows`: arrays de valores. **`rows[i][j]` corresponde a `columns[j]`**;
  no se incluyen índices internos de Pandas.
- `total_rows`, `offset`, `limit`, `returned_rows`, `has_more`, `next_offset`:
  metadatos de paginación. `limit` conserva lo solicitado aunque la última página
  tenga menos filas. Solo hay `next_offset` cuando quedan registros.

Ejemplo: después de cargar un CSV sintético `id,valor` con los registros
`001,10`, `002,20` y `003,30`, consultar:

```http
GET /datasets/{dataset_id}/preview?offset=0&limit=2
```

```json
{
  "dataset_id": "<UUID devuelto por intake>",
  "columns": [
    { "name": "id", "data_type": "string", "nullable": false },
    { "name": "valor", "data_type": "Int64", "nullable": false }
  ],
  "rows": [["001", 10], ["002", 20]],
  "total_rows": 3,
  "offset": 0,
  "limit": 2,
  "returned_rows": 2,
  "has_more": true,
  "next_offset": 2
}
```

#### Lectura y límites

`PreviewDataset` resuelve el dataset mediante `DatasetProvider` y delega la lectura
al nuevo puerto `DatasetPreviewReader`. `PandasDatasetPreviewReader` opera sobre
`PandasLocalTable.frame.iloc[offset:offset+limit]` y solo después itera las tuplas.
La extracción se ejecuta en un thread mediante `asyncio.to_thread`. No llama a
`column()`, no convierte el DataFrame completo, no relee el CSV/TSV, no calcula
estadísticas ni repite el perfilado.

`LocalTable` y sus consumidores no cambian. Los accesos actuales a columnas de
profiling/herramientas siguen materializando columnas completas y pueden consumir
memoria proporcional al número de filas; preview evita esa estrategia. El dataset
completo continúa en el almacén existente: AUD-009 no elimina su coste de memoria
ni convierte la carga inicial en una lectura por streaming.

Los límites fijos del contrato están centralizados en `domain/preview.py`:

| Recurso por consulta | Máximo |
| --- | --- |
| Filas | 100 |
| Columnas | 1000 |
| Celdas de la página efectiva | 10000 |
| Respuesta JSON UTF-8 completa, incluidos metadatos | 1048576 bytes (1 MiB) |
| Valor o nombre/tipo de columna serializado a JSON UTF-8 | 65536 bytes (64 KiB), incluidas comillas y escapes |

20 filas permite una primera vista pequeña; 100 limita la página pedida. Los
límites de celdas, columnas y bytes cubren tablas anchas y celdas extensas, para
las que limitar filas no basta. Se validan los metadatos antes de leer valores,
se cuenta el tamaño incrementalmente y se verifica el JSON final. No se truncan
valores ni se reducen páginas silenciosamente. Si el exceso depende de filas,
el cliente puede pedir menos; una celda o un esquema excesivos pueden impedir
consultar esa página incluso con `limit=1`. Son techos de esta capacidad, no
nuevos ajustes de despliegue o de upload.

#### Serialización y errores

Texto, enteros, flotantes finitos y booleanos conservan sus tipos JSON. Los
identificadores como `"001"` permanecen texto. `None`, `pd.NA`, `NaN` numérico,
`NaT` y `Decimal("NaN")` se representan como `null`; el texto literal `"nan"`
continúa siendo texto. Fechas, horas y timestamps usan ISO 8601, conservando la
zona horaria y precisión disponibles. Los temporales de CSV/TSV que intake
mantiene como texto conservan su texto. `Decimal` finito se devuelve como cadena
decimal exacta para evitar pérdida por conversión a float. Los enteros no se
recortan a la precisión de JavaScript: un cliente debe tener en cuenta los
enteros fuera de su rango seguro al interpretar JSON.

Infinitos, objetos, contenedores, binarios y tipos no soportados no se convierten
silenciosamente: se rechaza la página. Tampoco se reduce la precisión de
flotantes NumPy de más de 64 bits. No hay fallback que materialice columnas
completas para proveedores antiguos; una tabla distinta de `PandasLocalTable`
necesita su propio adaptador del puerto antes de poder servir valores.

| HTTP | Código | Comportamiento |
| --- | --- | --- |
| 404 | `DATASET_NOT_FOUND` | Dataset nunca registrado, descartado, expulsado por LRU o perdido al reiniciar; cargar nuevamente |
| 422 | Validación FastAPI | Paginación inválida o parámetros desconocidos |
| 413 | `PREVIEW_TOO_LARGE` | Excede alguno de los presupuestos; no devuelve una muestra truncada |
| 422 | `PREVIEW_UNSUPPORTED` | Valor o tabla no representable de forma segura; no incluye el valor ni detalles internos |
| 429 | `REQUEST_RATE_LIMITED` | Comparte el ámbito `exploration` con las tools y su `Retry-After` |
| 429 | `ANALYSIS_CAPACITY_EXCEEDED` | Comparte la reserva de operaciones existente y su `Retry-After` |

La capacidad compartida cubre lectura y preparación de la página; no se crea un
limitador ni un sistema de concurrencia nuevos. Las respuestas incluyen
`X-Request-ID`; las páginas correctas incluyen `Cache-Control: no-store`. No se
registran valores de celdas ni se incluyen filas, rutas internas o excepciones
del proveedor en mensajes de error.

El almacén es local al proceso, con LRU por cantidad de datasets y sin TTL. Una
consulta correcta actualiza su uso LRU mediante el proveedor existente. No hay
persistencia durable ni recuperación después de reiniciar. El proyecto no añade
autenticación ni aislamiento multiusuario en esta tarea: conocer un dataset_id
puede permitir acceder a su contenido. Usar datasets sintéticos o públicos para
demostraciones y restringir el acceso al servicio según su entorno.

#### Evidencia reproducible en PowerShell

Desde la raíz del worktree, el siguiente ejemplo ejecuta HTTP contra la aplicación
real mediante TestClient, sin necesitar un servidor externo. La carga utiliza el
flujo `/intake`, el almacenamiento temporal y el LRU reales. `Tee-Object` conserva
una captura de terminal fuera del repositorio:

```powershell
@'
import json
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.shared.config.settings import Settings

with TestClient(create_app(Settings(_env_file=None))) as client:
    loaded = client.post("/intake", files={
        "file": ("synthetic.csv", b"id,valor\n001,10\n002,20\n003,30\n", "text/csv")
    })
    print("POST /intake:", loaded.status_code)
    dataset_id = loaded.json()["profile"]["dataset_id"]
    for path in [
        f"/datasets/{dataset_id}/preview?offset=0&limit=2",
        f"/datasets/{dataset_id}/preview?offset=2&limit=2",
        f"/datasets/{dataset_id}/preview?offset=3&limit=2",
        "/datasets/missing/preview",
        f"/datasets/{dataset_id}/preview?limit=101",
    ]:
        response = client.get(path)
        print("GET", path, response.status_code)
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
'@ | uv run python - | Tee-Object -FilePath ..\aud009-preview-evidence.txt

uv run python -m pytest tests/unit/test_dataset_preview.py tests/integration/test_dataset_preview_api.py -q |
    Tee-Object -FilePath ..\aud009-preview-tests-evidence.txt
```

Esperado: carga 200; páginas con 2, 1 y 0 filas; dataset ausente 404 con
`DATASET_NOT_FOUND`; límite 101 rechazado con 422. Las pruebas adicionales
comprueban TSV, serialización, 413, LRU, límites compartidos 429, inmutabilidad,
ausencia de relectura y extracción de tres filas sobre un DataFrame de 500000.

La prueba de arquitectura conserva intacta `openapi_develop.json`: todas las
rutas, componentes y operation IDs anteriores deben seguir coincidiendo. Se
añade únicamente `/datasets/{dataset_id}/preview` y el esquema `DatasetPreview`,
verificados en `openapi_preview.json`. Los contratos de `/intake`,
`/analysis/datasets/{dataset_id}` y `/datasets/{dataset_id}/tools/{tool_name}`
permanecen iguales. Los tipos del frontend se podrán regenerar al implementar
AUD-010; AUD-009 no cambia archivos React ni el cliente actual.

#### Validación de AUD-009 — 17 de octubre de 2026

Worktree aislado `Analista-de-datos-aud009`, rama
`feat/aud-009-dataset-preview`, creado exclusivamente desde `origin/develop`
actualizado: `f95c211b699aa68a04d2fb49cf30e40dd8a3f7d4`. Se verificó que incluye
las integraciones de los PR #28 y #29. No se modificó el worktree de AUD-011 ni
se realizaron commits, push, PR, merge o rebase.

| Verificación | Línea base sin cambios | Con AUD-009 |
| --- | --- | --- |
| `uv sync --locked` | Correcto | Correcto |
| Comprobador de arquitectura | 162 archivos Python, correcto | 167 archivos Python, correcto |
| `pytest tests/architecture -q` | 24 aprobadas | 24 aprobadas |
| `pytest` completo | 375 aprobadas, 4 fallidas | 468 aprobadas, las mismas 4 fallidas |
| Tests nuevos de preview | No existían | 93 aprobadas |
| Intake, guardas de producción, store y arquitectura | Cubiertos por la suite | 49 aprobadas en ejecución dirigida adicional |
| `ruff check .` | 2 errores ajenos | Los mismos 2 errores |
| `ruff format --check .` | 249 archivos correctos | 257 archivos correctos |
| Ruff limitado a archivos modificados/nuevos de AUD-009 | No aplica | Correcto |

Se ejecutaron también las pruebas nuevas de forma individual: **58 unitarias**
y **35 de integración**, todas aprobadas. La extracción acotada utiliza 500000 filas y prohíbe
`column()`, `to_dict()` y `to_json()`, comprobando que el iterador recibe únicamente
las tres filas solicitadas y que el DataFrame conserva su contenido.

Los cuatro fallos backend reproducidos antes y después corresponden a:

- `test_anova_planning.py::test_fast_mode_uses_next_valid_anova_after_omitting_sparse_pair`.
- `test_critic_pipeline.py::test_default_csv_produces_measured_critic_and_insights_without_a_question`.
- `test_critic.py::test_critic_reports_significant_results_without_robustness_as_preliminary`.
- `test_critic.py::test_critic_skips_when_no_result_is_significant`.

Ruff mantiene F841 (`unranked`) en
`app/modules/analysis/application/services/analysis_planning.py:273` y F401
(`AssociationResult`) en `tests/unit/test_planner_agent.py:10`.
Los archivos y algoritmos de esos módulos se conservaron intactos.

Se reconfirmó la base frontend con `npm ci`, `npm test`, `npm run lint` y
`npm run build`: 35 pruebas aprobadas y el mismo fallo de ReportPage
(`null metrics stay unmeasured and no insights are invented`); ESLint conserva
el import `methodLabel` sin uso en `ReportPage.tsx:6`; el build pasa.
La generación OpenAPI se verificó en un archivo temporal fuera del worktree:
los tipos anteriores coinciden con los generados desde la snapshot original,
y la nueva operación/DTO generan correctamente. Un consumidor TypeScript del
preview generado compila con `tsc --noEmit --strict`. No se editaron archivos
de frontend, dependencias o contratos compartidos existentes.

La evidencia HTTP reproducible mostró carga 200 y páginas de 2, 1 y 0 filas,
404 `DATASET_NOT_FOUND` y 422 para `limit=101`. Las pruebas verificaron además
presupuestos 413 y protecciones compartidas 429. No quedan fallos nuevos de
AUD-009; la suite general conserva los fallos ajenos documentados.

`DataUnderstandingAgent` recibe el puerto `DataUnderstanding`, no un lector CSV
concreto ni un LLM. Devuelve SUCCESS con `AgentUpdate.dataset_id`, perfil,
diccionario y métricas. Fallos esperados de entrada devuelven FAILED y frenan el
grafo. Las cuatro etapas posteriores continúan como skeletons.

El resultado del servicio contiene `LoadedDataset` únicamente para uso local.
No se incluye la tabla en AgentContext, AgentState, AnalysisReport ni LLMRequest.
La futura ejecución de tools deberá administrar su ciclo de vida local de forma
explícita; `dataset_id` por sí solo no implementa un almacén de datos.

Cambios compartidos para el equipo:

- `DatasetProfile` mantiene row_count y columns; añade invariantes y `summary()`.
- `ColumnProfile.semantic_type` se restringe a los seis roles; añade procedencia,
  explicación y warnings. Semánticas específicas de negocio se mantienen en
  DataDictionaryEntry, no se confunden con estos roles estructurales.
- `DataDictionaryEntry` añade inferred_fields e inference_reason opcionales.
- `AgentUpdate` añade dataset_id y metrics; `AnalysisReport` añade perfil y diccionario.
- `build_agents` ahora requiere un puerto DataUnderstanding inyectado.
- Settings añade data_intake; sus valores provienen de defaults.toml.

`profiling_time` mide lectura, validación y clasificación básicas. El reporte global
continúa SKIPPED hasta implementar el análisis completo. `/analysis` permanece en
501 y `/health` en 200, según el contrato inicial de la API.
