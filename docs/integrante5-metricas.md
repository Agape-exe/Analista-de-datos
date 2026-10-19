# Métricas del integrante 5

Implementación local del 18 de octubre de 2026. Acceso desde Evaluación →
Métricas o `/metrics`. Se genera o recupera el reporte en Hallazgos (`/report`).
Los apartados iniciales conservan las validaciones de implementación anteriores.

## AUD-043 — Hallazgos y evidencia

La parte implementable quedó revisada en la cabecera de I5: Hallazgos conserva
la identidad de `run_id` y `dataset_id` provista por `ReportProvider`, y las dos
descargas siguen apuntando al mismo reporte (`analysis-report.json` usa el
objeto recibido; Markdown usa `/reports/{run_id}/markdown`). La navegación ahora
es explícita y accesible: cada `Insight.evidence_ids` enlaza solo a una
`Evidence` presente, cada evidencia enlaza solo a su `analysis_id` presente y
las referencias ausentes se muestran sin enlace. Los métodos conocidos tienen
etiquetas legibles, mientras que los desconocidos se conservan literalmente.

Se muestran limitaciones del insight y de la evidencia, advertencias del
resultado y advertencias/errores globales. Los resultados parciales, históricos,
`FAILED` y `SKIPPED` conservan su estado, datos disponibles y mensajes; no se
convierten ausencias en ceros ni se fabrica evidencia o procedencia. Si un
`analysis_id` histórico está omitido, la interfaz usa un ancla local estable
solo para ese resultado y no lo presenta como una identidad contractual.

Prueba añadida: referencias insight → evidencia → resultado, método legible,
limitaciones, advertencias y referencia ausente sin enlace. Resultado de la
cabecera documentada en esta entrega: arquitectura 174 archivos OK; 24 pruebas
de arquitectura; 20 pruebas backend afectadas; 53 pruebas frontend de
Hallazgos/ReportProvider/Summary/Metrics/Trace; ESLint OK; build TypeScript/Vite
OK. El primer intento Vitest fue bloqueado por `EPERM` de resolución Windows y
la repetición con permisos del entorno pasó; no se modificaron límites,
reintentos ni aserciones.

### Parte bloqueada

AUD-043 no clasifica significancia estadística, no cierra afirmaciones de
significancia o causalidad, no modifica Critic y no inventa procedencia ni
razones ausentes del contrato. Queda esperando los contratos y pruebas de
AUD-002 y AUD-036 de Integrante 4, en particular cualquier clasificación o
proveniencia adicional que deba consumir Hallazgos. La rama local contiene la
referencia de trabajo `origin/feature/critic-relations-queries` (AUD-036), pero
no está integrada en esta rama; AUD-002 tampoco está disponible como contrato
utilizable aquí.

AUD-044 Chat no se implementa: no se verificó AUD-039 fusionado en la base con
contrato, endpoint y pruebas utilizables.

Estado de publicación de esta revisión: commit de implementación
`72c52932776e45a1e500ffcc30bf53381a102e13` (`fix(i5): make report evidence
traceable`). La última CI remota documentada para PR #41 es
[39130025022](https://github.com/Alexander20L/Analista-de-datos/actions/runs/39130025022)
(global fallida; los cuatro E2E de Métricas/Traza pasan). El PR sigue siendo el
PR #41, base `develop`, sin merge ni despliegue Render; el estado remoto actual
no pudo consultarse desde este entorno por resolución DNS.
La revisión actual, correcciones y evidencia de publicación/Actions están en
[Entrega de I5](integrante5-entrega.md). No se desplegó en Render.

## Integración y fuentes

Se leyeron `AGENTS.md`, `architecture.md`, `aud-007-ci.md`, los contratos
Python/TypeScript y los flujos reales de intake, reportes, navegación y reset.
Solo existe el AGENTS de la raíz.

`MetricsPage` consume directamente `useReport()` dentro del `ReportProvider`
que envuelve las rutas. No mantiene una copia del reporte ni solicita el endpoint
de métricas por separado. Reutiliza los reportes completos que ya proporcionan
`POST /analysis/datasets/{dataset_id}` y `GET /reports/{run_id}`.
`GET /reports/{run_id}/metrics` devuelve el mismo `ExperimentMetrics`, pero no
incluye por sí solo la identidad y los estados necesarios para esta pantalla.

Fuente de verdad: `app/shared/domain/models/metrics.py`,
`app/shared/domain/models/report.py` y `frontend/src/types/api.ts`.
Los 23 campos de `ExperimentMetrics` se enumeran exhaustivamente con
`satisfies Record<keyof Metrics, string>`; las etiquetas reutilizan `reports/labels.ts`.

| Campos de `report.metrics` | Presentación |
| --- | --- |
| precision, recall, f1_score, false_positive_rate, pattern_detection_rate, spurious_detection_rate | Escala original 0–1 |
| hypothesis_consistency, insight_consistency, tool_selection_consistency, conclusion_agreement, semantic_similarity | Escala original 0–1 |
| completion_rate, human_intervention_rate, valid_tool_selection_rate, invalid_analysis_rate | Escala original 0–1 |
| total_response_time, time_to_first_insight, profiling_time, analytics_time | Segundos |
| llm_calls, tool_calls | Llamadas |
| tokens_used | Tokens |
| iterations | Iteraciones |

Se muestran los números recibidos sin recalcular tasas, convertir a porcentajes,
completar contadores ni inferir puntuaciones a partir de resultados.
`null`, `undefined` y campos omitidos se presentan como **No disponible**;
el cero se presenta como **0**, incluso en tiempos de etapas.

La procedencia visible utiliza `run_id`, la identidad que proporciona el provider,
`configuration.execution_scope` cuando existe, `status`, `stage_statuses`,
`stage_durations`, `warnings` y `errors`. La identidad del reporte proviene de
`dataset_profile.dataset_id`; una generación sin ese perfil conserva la identidad
del dataset solicitado según la lógica previa del provider. Una recuperación
histórica sin perfil no hereda la identidad del dataset activo.

`ReportContextCard` extrae la presentación que ya usaba Hallazgos y la comparte
con Métricas: origen generado/recuperado, dataset coincidente/distinto/desconocido
y reporte anterior durante una nueva solicitud, fallo o cancelación.
No se asocia un reporte recuperado de otro dataset al dataset activo.

## Estados y limitaciones del contrato

- SUCCESS: reporte completado, sin asumir que todas sus métricas están medidas.
- SKIPPED: reporte con etapas omitidas; conserva mediciones disponibles.
- FAILED: ejecución fallida; identifica mediciones potencialmente parciales.
- Los estados de cada etapa se muestran con su código y traducción. No se
  deduce un estado por métrica ni se convierten ausencias en SKIPPED.
- Los motivos se muestran literalmente desde las advertencias y errores del
  backend. Si no existen, se indica que no se proporcionaron.
- La carga de intake y la solicitud de reporte tienen mensajes diferenciados.
  Sin reporte, incluso en acceso directo, se presenta el estado vacío y acceso
  a Hallazgos, sin peticiones ni estadísticas de demostración.

El contrato HTTP no incluye estados o motivos individuales de ausencia por
métrica, ni garantiza una procedencia experimental detallada (ground truth,
semilla o repeticiones). No se inventa esa información. `execution_scope` solo
se muestra cuando llega: FinalizeAnalysis distingue `finalization_only` y
`upstream_plus_finalization`; el ensamblador del workflow no garantiza ese campo.
No se infiere un alcance completo cuando está ausente.

Como describe `integrante5-evaluacion.md`, BenchmarkRunner puede calcular calidad
con ground truth y RepeatabilityRunner concordancia en sus artefactos de
experimento. La pantalla no ejecuta esos protocolos ni incorpora sus resultados
a un reporte HTTP que no los contenga. Los tiempos y contadores presentes son
mediciones del reporte integrado, incluidas las entregadas por otros módulos.

## Contexto y limpieza

Se conserva el comportamiento del provider existente, verificado también por sus
10 pruebas: la clave combina dataset ID y `contextRevision`. Cambiar de ruta no
desmonta el provider. Nuevo análisis ejecuta `IntakeProvider.reset`, cambia la
revisión, oculta inmediatamente el contexto anterior y aborta la solicitud.
Las respuestas verifican tanto el abort como la identidad de la solicitud antes
de escribir; una respuesta vieja no repuebla el contexto ni termina la carga
de una solicitud nueva. No fue necesario cambiar los providers.

Los reportes anteriores retenidos tras un fallo/cancelación se etiquetan como
anteriores. La pantalla conserva las mediciones del reporte identificado, incluso
si es histórico o parcial, sin atribuirlas al dataset activo.
La persistencia continúa en memoria del cliente durante la sesión; recargar
la página pierde ese contexto. No se añadió almacenamiento permanente.

## Validación local

Comandos npm desde `frontend`; uv y Git desde la raíz. Se siguieron los locks,
el límite de dos workers de AUD-007 y Chromium configurado. Las comprobaciones
que lo necesitaron se ejecutaron con permisos ampliados después de errores del
aislamiento de Windows.

| Comando | Resultado |
| --- | --- |
| `npm test -- --maxWorkers=2 --reporter=default --reporter=junit --outputFile=../.pytest_cache/metrics-vitest.xml` | **200 aprobadas, 15 archivos**, 52,53 s |
| `npm test -- src/features/metrics/MetricsPage.test.tsx --maxWorkers=2` | **10 aprobadas**, 13,39 s, verificación posterior a la redacción final |
| `npm run build` | **Correcto**, TypeScript y Vite, 1641 módulos |
| `npm run lint` | **Falló: 3997 errores**, todos en siete archivos generados de `frontend/playwright-report/trace/` existentes antes de esta implementación |
| `npm run lint -- --format json --output-file ../.pytest_cache/metrics-eslint.json` | Reproduce los 3997 errores y documenta **cero errores en el código fuente y E2E** |
| `npm exec --no -- eslint src/features/metrics src/features/reports/ReportContextCard.tsx src/features/reports/ReportPage.tsx src/app/App.tsx src/components/layout/Sidebar.tsx src/test/report-fixture.ts e2e/metrics.spec.ts` | **Correcto**, comprobación adicional de todos los archivos de código modificados |
| `uv run python scripts/check_architecture.py` | **Correcto**, 173 archivos |
| `uv run pytest tests/architecture -q` | **24 aprobadas**, 3,15 s |
| `git diff --check` | **Correcto** |

Se añadieron 10 pruebas de comportamiento con App, rutas y providers reales:
SUCCESS/SKIPPED/FAILED, ceros/nulos/omisiones, causas, alcance, identidad histórica,
reporte de otro dataset, sustitución, navegación, carga, respuesta tardía tras
reset y respuesta completada después de cambiar de pantalla. No se omiten
pruebas ni se amplían sus timeouts. La suite previa de 190 pruebas también pasa.

Fallos encontrados y corregidos durante el desarrollo: opciones `exact` no
admitidas por `ByRoleOptions` de Testing Library, y una expectativa que usaba el
nombre del archivo enviado en vez del filename de la respuesta fixture. La
primera ejecución completa con las nuevas pruebas dio 199 aprobadas y 1 fallida
por esa expectativa; la ejecución final indicada arriba pasa las 200.
El primer intento restringido de Vitest falló antes de ejecutar pruebas con
`EPERM realpath .../src/test/setup.ts`; la repetición con permisos ampliados sí
ejecutó la suite. El Python global no estaba operativo y uv restringido no pudo
consultar su intérprete; las comprobaciones posteriores usaron el entorno del
proyecto con permisos ampliados.

### E2E y evidencia pendiente

Se ejecutó:

```powershell
$env:CI='true'
$env:PLAYWRIGHT_CHANNEL='chromium'
$env:PLAYWRIGHT_HTML_OUTPUT_DIR='../.pytest_cache/metrics-playwright-report'
$env:PLAYWRIGHT_JUNIT_OUTPUT_FILE='../.pytest_cache/metrics-e2e.xml'
npm run test:e2e -- e2e/metrics.spec.ts e2e/report-context.spec.ts e2e/navigation-context.spec.ts e2e/report.spec.ts --reporter=list,html,junit --output=../.pytest_cache/metrics-e2e-results
```

**8 fallidas antes de aserciones por `browserType.launch: spawn UNKNOWN`** al
lanzar Chromium 1248. Uvicorn y Vite sí arrancaron. Es el mismo bloqueo de
lanzamiento Windows descrito en AUD-007; se reprodujo también en las seis pruebas
existentes. No demuestra un fallo funcional ni aprueba los recorridos nuevos.
Los informes anteriores se conservan usando directorios de salida distintos.
Se generaron JUnit, informe HTML y ocho trazas en `.pytest_cache/metrics-*`.

Las dos E2E nuevas cubren un reporte real con comparación de ID/contadores con
la respuesta HTTP, navegación, reset, recarga y ancho móvil; y una recuperación
retenida por interceptación para comprobar el reset durante la espera. La prueba
unitaria resuelve además un fetch que ignora abort, cubriendo esa carrera sin
depender de la cancelación de red del navegador.

Falta ejecutar los recorridos E2E y revisar visualmente la pantalla en un entorno
donde Chromium arranque. Tampoco hay evidencia de CI remota. No se declara la
pantalla completamente validada. Los cuatro fallos backend y dos errores Ruff
documentados por AUD-007 no se reejecutaron ni se modificaron en esta entrega;
no se presentan como resultados de esta sesión.

Los siete archivos del lint son `codeMirrorModule-BEB2e8M3.js` (1236 errores),
`defaultSettingsView-D-g2vrvf.js` (2045), `urlMatch-L3liM589.js` (8),
`index.7-c5LSTW.js` (63), `snapshot.B_Jk1wbt.js` (16), `sw.bundle.js` (484) y
`uiMode.CYwC_gH1.js` (145). Son artefactos locales no seguidos, con fechas
anteriores al inicio de esta implementación. No se editaron, borraron ni
excluyeron; este es un fallo del lint sobre el árbol local con esos artefactos,
no evidencia de un fallo de lint del código en un checkout limpio.

## Archivos y conservación del árbol

Cambios propios: `frontend/src/app/App.tsx`, `frontend/src/components/layout/Sidebar.tsx`,
`frontend/src/features/reports/ReportPage.tsx`, el componente nuevo
`frontend/src/features/reports/ReportContextCard.tsx`,
`frontend/src/features/metrics/{MetricsPage.tsx,metric-fields.ts,MetricsPage.test.tsx}`,
`frontend/src/test/report-fixture.ts`, `frontend/e2e/metrics.spec.ts` y este documento.

La revisión final del diff conserva las ocho modificaciones previas:
`.env.example`, `.gitignore`, `app/api/main.py`, `app/shared/config/settings.py`,
`docs/aud-037-summary.md`, `frontend/playwright.config.ts`,
`tests/integration/test_production_api_guards.py` y `tests/unit/test_deployment_settings.py`.
También permanecen todos los paths previamente no seguidos: `.github/`, el
upload_guard, AUD-007, benchmarks, diagnósticos y documentación de staging/capacidad,
y sus pruebas. No se editó ninguno de esos archivos. No se usaron operaciones
destructivas ni se cambiaron algoritmos, contratos públicos, dependencias,
lockfiles o el límite de archivos de **2.097.152 bytes**.

## Continuación: vista Traza (18 de octubre de 2026)

Implementación en `frontend/src/features/trace/TracePage.tsx`, estilos en
`trace.css`, ruta `/trace` en `src/app/App.tsx` y menú Evaluación → Traza en
`src/components/layout/Sidebar.tsx`. Reutiliza los componentes Card/Button,
tablas con captions y cabeceras accesibles, avisos de carga/errores y
`ReportContextCard`. La tabla de llamadas permite desplazamiento horizontal
con teclado en pantallas estrechas. No hay datos de demostración en la vista.

### Contrato verificado antes de implementar

| Campo | Modelo y opcionalidad | Semántica comprobada |
| --- | --- | --- |
| `execution_trace` | `list[dict[str, JsonValue]]`, default `[]`; opcional en OpenAPI/TypeScript | Lista abierta de objetos JSON, sin esquema de evento cerrado ni campos internos obligatorios. Los productores actuales registran llamadas instrumentadas, no estados/transiciones de agentes. |
| `stage_statuses` | `dict[str, AnalysisStatus]`, default `{}`; opcional en OpenAPI/TypeScript | Resultado de cada agente registrado, indexado por `agent.name`; SUCCESS, SKIPPED o FAILED. |
| `stage_durations` | `dict[str, Duration]`, default `{}`; opcional en OpenAPI/TypeScript | Tiempo transcurrido de la etapa, en segundos, indexado por el mismo `agent.name`. Duration es float >= 0; cero es válido. |

Referencias (rutas desde la raíz):

- `app/shared/domain/models/report.py:AnalysisReport`,
  `app/shared/domain/models/metrics.py:Duration`,
  `app/shared/domain/enums/statuses.py:AnalysisStatus`,
  `frontend/src/types/api.ts:AnalysisReport` y
  `tests/fixtures/openapi_develop.json`: estructura y valores por defecto.
- `app/shared/adapters/observability/telemetry.py`: `InstrumentedLLMProvider`
  añade `{kind: "llm", status, duration_seconds}` al terminar una llamada;
  `InstrumentedAnalyticsTool` añade `{kind: "tool", method: self.name, status,
  duration_seconds}`. Ambos usan `perf_counter()` y append en finally,
  incluyendo excepciones. El LLM emite SUCCESS o FAILED; la herramienta usa
  el estado de AnalysisResult, que también admite SKIPPED. No hay timestamps,
  identificadores de llamada/etapa ni motivos por llamada en estos productores.
  `RunTelemetry.events` conserva el orden de inserción al finalizar llamadas;
  no garantiza orden de inicio ni permite deducir concurrencia de llamadas.
  La lista JSON conserva ese orden; el contrato no promete cronología general.
- `app/modules/analysis/adapters/orchestration/graph.py:_agent_node` mide
  `agent.run` con `TimingRecorder`, guarda el estado y duración con la misma
  clave de agente. Solo registra esas entradas cuando el agente devuelve un
  resultado. `build_graph` es actualmente lineal y corta tras FAILED; eso no
  convierte el contrato público de mapas en una secuencia cronológica.
  `LangGraphWorkflow.run` asigna `telemetry.events` a la traza del reporte.
  Ante excepción o timeout crea un reporte FAILED con traza disponible y
  mapas por defecto vacíos, sin reconstruir las etapas parcialmente ejecutadas.
- `app/shared/application/timing.py:TimingRecorder.measure`: segundos
  transcurridos monotónicos, acumulados por clave dentro del recorder. No
  equivalen a tiempo de CPU ni a marcas de reloj. El wrapper de cada agente
  usa un recorder propio. El tiempo de llamada puede estar incluido dentro
  del tiempo de etapa: no se suman llamadas y etapas ni se construye un total.
- `app/shared/application/reporting.py:assemble_report`: FAILED si hay
  errores generales o alguna etapa FAILED; SUCCESS si hay estados y todos
  son SUCCESS; SKIPPED en los demás casos. El estado del reporte es agregado,
  independiente del resultado de una llamada concreta. Una llamada fallida
  puede ser manejada por un agente sin convertir toda la ejecución en FAILED.
- `app/modules/reporting/application/use_cases/finalize_analysis.py`: otro
  productor válido informa solamente Insight, usa su resultado como estado
  del reporte, mide la finalización en segundos y deja la traza por defecto
  vacía. Una traza vacía no prueba ausencia de ejecución ni de llamadas no
  instrumentadas. No se aplica el algoritmo agregador a todos los productores.
- `app/modules/reporting/adapters/persistence/report_repository.py` guarda
  `model_dump_json()` y recupera con `model_validate_json()`. Los campos
  omitidos en payloads históricos se completan con las colecciones vacías
  del modelo; una vez normalizados no se puede distinguir omisión de vacío.
  `adapters/http/routes.py` entrega AnalysisReport en GET /reports/{run_id};
  el cliente también consume el reporte de POST /analysis/datasets/{dataset_id}.
  El endpoint de métricas no incluye la traza. El renderer Markdown actual
  no presenta ninguno de los tres campos; no se alteró su salida pública.

Las claves de ambos mapas se relacionan por igualdad exacta de nombre de etapa.
No existe una clave de etapa en las llamadas emitidas actualmente: `method`
identifica la herramienta, no al agente. Traza no une llamadas y etapas por
posición, nombre del método, duración ni otra heurística. Muestra la unión de
claves de los mapas, incluso duración sin estado o estado sin duración, como
información de etapas. No convierte esos mapas en eventos ni los ordena como
una ejecución. Las etiquetas de etapa conservan además la clave original.

El contrato estricto del backend no acepta null para estas tres colecciones ni
para valores Duration/AnalysisStatus. Sí permite omitirlas, y cada propiedad
interna de un objeto de traza es JsonValue (incluido null). La vista tolera además
duraciones nulas recibidas, sin convertirlas en cero; se prueban expresamente
como tolerancia de lectura, no como salida normal del backend. Los estados
desconocidos se muestran literalmente aunque el enum actual sea cerrado.
Los campos JSON adicionales de una entrada se presentan literalmente con su
nombre; no se inventan detalles cuando no vienen.

Contradicción de presentación encontrada: `reports/labels.ts` traduce SKIPPED
como “Pendiente” y Hallazgos habla de etapas pendientes; no significa un estado
RUNNING ni una transición pendiente en el contrato. Métricas ya utiliza
“Omitido”; Traza muestra `SKIPPED · Omitido`. Se conserva el código original y
no se modifica el comportamiento previo de Hallazgos dentro de esta entrega.

### Contexto, reportes históricos y errores

Traza lee exclusivamente `useReport()` y `useIntake()`, sin copia del reporte,
petición propia ni persistencia adicional. El mismo objeto proporciona las
llamadas y ambos mapas en cada render: una sustitución no puede mezclar campos
del reporte anterior. Las identidades de run/dataset se conservan al navegar
entre Hallazgos, Métricas y Traza. Se muestran dataset activo y procedencia del
reporte por separado, incluyendo reportes de otro dataset o sin perfil.

Se conservan los mecanismos de selección y reset del ReportProvider existente:
dataset ID + contextRevision, ocultación inmediata del contexto anterior,
AbortController y comprobación de identidad de petición antes de escribir.
Nuevo análisis limpia la vista; una respuesta tardía que ignore abort tampoco
la repuebla. Las peticiones que terminan mientras Traza está visible actualizan
el contexto compartido. Durante una nueva petición o tras su fallo/cancelación,
el reporte retenido se identifica explícitamente como anterior.

La pantalla cubre carga, fallo de obtención, ausencia de reporte y navegación
directa sin contexto. La sesión del cliente sigue siendo volátil: recargar
`/trace` muestra el estado sin reporte y permite ir a Hallazgos para recuperarlo.
Una etapa FAILED o un reporte FAILED cargado no se representa como error de
obtención. Los errores/advertencias generales no se asignan a etapas concretas.

Un reporte histórico puede omitir los tres campos, cualquiera de los mapas o la
traza. Se distinguen la propiedad de traza ausente y la lista vacía cuando llegan
así al cliente (con la limitación de normalización del servidor indicada arriba).
Los estados/duraciones disponibles siguen visibles aunque no haya entradas.
Un cero se muestra como `0 s`; null/undefined/omisión como “No disponible”.
Las duraciones mantienen la precisión numérica recibida, sin redondear tiempos
pequeños a cero y con sufijo `s` y cabeceras en segundos.

### Pruebas y comprobaciones de esta continuación

Se añadieron `src/test/trace-fixture.ts`, 12 pruebas con App/providers/rutas reales
en `src/features/trace/TracePage.test.tsx` y dos E2E en `e2e/trace.spec.ts`.
El fixture de llamadas replica los campos de los wrappers de telemetría; sus
valores son datos explícitos de prueba. Los casos JSON abiertos y nulos se
mantienen separados del fixture normal. Se cubren llamadas, orden recibido,
unidades, cero/ausencia, SUCCESS/SKIPPED/FAILED, estados desconocidos, detalles
recibidos, reportes históricos/parciales, traza sin etapas, etapas sin traza,
error de red, carga que termina en Traza, sustitución completa, reporte retenido,
identidad entre rutas y reset con respuesta tardía que ignora abort.

La E2E real genera el reporte mediante HTTP y compara identidad, entradas de
traza, estados y duraciones con la respuesta; recorre Hallazgos/Métricas/Traza,
comprueba anchos de 1440/390 px, reset y recarga. La segunda retiene una respuesta
para comprobar el reset durante la recuperación. Se ejecutaron junto con las
E2E previas afectadas sin cambiar ni debilitar sus aserciones.

Comandos uv/Git desde la raíz; npm desde `frontend`:

| Comando | Resultado de esta sesión |
| --- | --- |
| `uv run python scripts/check_architecture.py` | Correcto, 173 archivos Python. |
| `uv run pytest tests/architecture -q` | 24 aprobadas, 1,19 s. |
| `uv run pytest tests/unit/test_telemetry.py tests/integration/test_graph.py tests/integration/test_insight_workflow.py tests/integration/test_reporting_api.py tests/integration/test_member5_finalization.py -q` | 15 aprobadas, 9,58 s. Se verificaron productores/serialización sin modificar backend. |
| `npm test -- --maxWorkers=2 --reporter=default --reporter=junit --outputFile=../.pytest_cache/trace-vitest.xml` | 212 aprobadas, 16 archivos, 58,42 s. Incluye las 200 existentes y las 12 nuevas. |
| `npm test -- src/features/trace/TracePage.test.tsx --maxWorkers=2` | 12 aprobadas, 19,82 s; comprobación posterior a explicitar los casos parametrizados missing/empty. |
| `npm run build` | Correcto; build final con estilos adaptables, 1643 módulos, 9,70 s en Vite, TypeScript aprobado. |
| `npm run lint -- --format json --output-file ../.pytest_cache/trace-lint-before.json` | Antes de implementar: 3997 errores, cero warnings, en siete archivos generados de Playwright. |
| `npm run lint -- --format json --output-file ../.pytest_cache/trace-lint-after.json` | Después: los mismos 3997 errores en los mismos siete archivos; cero errores en fuentes/E2E. No se excluyeron ni editaron los artefactos. |
| `npm exec --no -- eslint src/features/trace src/test/trace-fixture.ts src/app/App.tsx src/components/layout/Sidebar.tsx e2e/trace.spec.ts` | Correcto en todos los archivos de código añadidos/modificados por esta continuación. |
| `git diff --check` | Correcto. |

Los primeros intentos restringidos de uv fallaron con acceso denegado al consultar
el intérprete; Vitest falló antes de pruebas con EPERM en realpath de setup.ts y
Vite con EPERM en realpath de main.tsx. Las repeticiones con permisos ampliados
ejecutaron las comprobaciones indicadas arriba.

La primera suite con permisos ampliados tuvo 209 aprobadas y tres fallos de
espera al buscar el resumen/enlace de asociaciones (App.test.tsx y dos pruebas
de AssociationsPage.test.tsx). Se conserva el resultado en
`.pytest_cache/trace-vitest-first.xml`. Tras terminar los otros procesos de
build/E2E, la repetición completa pasó las 212 sin cambiar fuentes, aserciones
ni timeouts de esas pruebas. No se clasifica esa ejecución fallida como un
defecto preexistente demostrado: es un fallo transitorio observado; la carga
concurrente es una posible explicación, no una causa probada.

E2E ejecutadas con los servidores reales Uvicorn/Vite:

```powershell
$env:CI='true'
$env:PLAYWRIGHT_CHANNEL='chromium'
$env:PLAYWRIGHT_HTML_OUTPUT_DIR='../.pytest_cache/trace-playwright-report'
$env:PLAYWRIGHT_JUNIT_OUTPUT_FILE='../.pytest_cache/trace-e2e.xml'
npm run test:e2e -- e2e/trace.spec.ts e2e/metrics.spec.ts e2e/report-context.spec.ts e2e/navigation-context.spec.ts e2e/report.spec.ts --reporter=list,html,junit --output=../.pytest_cache/trace-e2e-results
```

**10 fallidas antes de aserciones**: `browserType.launch: spawn UNKNOWN` al
intentar lanzar Chromium 1248, incluyendo las dos nuevas y ocho existentes.
Los servidores sí arrancaron. Se conservan JUnit, HTML y trazas en los paths
anteriores; no se sobrescribieron los informes de Métricas. Esto es un bloqueo
del entorno al iniciar el navegador y no una validación funcional E2E. Sigue
pendiente ejecutar esas diez pruebas y revisar visualmente la tabla y su
desplazamiento a 1440/390 px en un entorno donde Chromium funcione.

No se desplegó ni se ejecutó GitHub Actions o Render. Los resultados locales no
demuestran aprobación de CI o de staging. Los fallos backend/Ruff históricos
de AUD-007 no se reejecutaron globalmente ni se presentan como verificados aquí.

### Diff y conservación de cambios locales

Esta continuación añade solamente `frontend/src/features/trace/{TracePage.tsx,
TracePage.test.tsx,trace.css}`, `frontend/src/test/trace-fixture.ts` y
`frontend/e2e/trace.spec.ts`; modifica App/Sidebar para la ruta y menú y amplía
este documento. No modifica algoritmos, backend, contratos, locks ni el límite
de **2 MiB (2.097.152 bytes)**.

Antes de editar se guardaron el diff binario y hashes SHA-256 de todos los
archivos locales modificados/no seguidos en `.pytest_cache/trace-before.patch`
y `trace-before-hashes.json`. La comparación final confirma que todos conservan
su hash salvo App, Sidebar y este documento, editados intencionalmente. En App
y Sidebar se comprobó también que retirar únicamente las adiciones de Traza
reproduce el contenido anterior (normalizando finales de línea); los cambios
previos de Métricas permanecen. El documento anterior se conserva íntegro como
prefijo, contrastado con `.pytest_cache/trace-doc-before.md`. No se restauró,
limpió ni borró ningún archivo local previo.

## Revisión de entrega I5

La continuación de integración está en la
[comparación Linux PR/develop](integrante5-integracion-linux.md): los tres
fallos E2E restantes se reprodujeron en ambas aplicaciones. Se conserva la
separación entre la validación de estas pantallas y la aprobación global de CI.

Se corrigió una omisión de esta pantalla: Métricas recorría solamente
`stage_statuses` y ocultaba tiempos válidos de etapas sin estado. Ahora utiliza
la unión de claves de estados y duraciones, igual que Traza, conservando cero
y mostrando «No disponible» cuando no se recibió el estado o el tiempo.
La nueva prueba falló antes del cambio (10 aprobadas, 1 fallida) y la suite
completa posterior aprobó 213 pruebas. No cambia el contrato ni calcula eventos.

Se verificaron los productores de telemetría, el grafo y los contratos HTTP/
persistencia con 15 pruebas backend aprobadas. El backend de esta rama es
idéntico al de `origin/develop` revisado. Los cuatro fallos globales y dos
errores Ruff se reprodujeron expresamente en un checkout de esa base.
El inventario archivo por archivo, la conservación de Render y los resultados
actuales están en [la revisión de entrega](integrante5-entrega.md).

En Actions real sobre `d6acf37`, los dos E2E de Métricas y los dos de Traza
pasan en Chromium Linux, con anchos de 1440/390 px. La suite completa conserva
17 aprobadas y tres fallidas en recorridos existentes; backend/Ruff también
siguen fallando. Se mantienen los informes y no se declara CI aprobada.
La tabla de jobs, URL, SHA y atribución de fallos está en la revisión de entrega.

## Integración final de Métricas, Hallazgos, Relaciones y Chat

Con `develop` en `896f583`, Métricas continúa consumiendo el objeto compartido
de `ReportProvider`: no solicita `/metrics` por separado, no recalcula valores y
mantiene la distinción entre cero y ausencia. La suite focal actual aprobó los
69 casos de Resumen, Métricas, Traza, Reportes, Chat y Relaciones.

Hallazgos muestra ahora `relationship_assessments` con clasificación,
justificación, referencias de evidencia y la procedencia literal que AUD-036
añade a `limitations`. Sus enlaces llevan a Relaciones, Métricas, Traza y Chat;
insight → evidencia → resultado conserva IDs reales del reporte.

Chat usa únicamente `GET /questions/catalog` y
`POST /reports/{run_id}/questions` de AUD-039. Conserva historial por reporte,
lo mantiene al navegar, lo limpia al cambiar/resetear el contexto, permite
cancelar la espera y descarta respuestas tardías. Las respuestas ANSWERED sin
referencias y las abstenciones con referencias se rechazan como contrato
inválido. No se añadió proveedor LLM ni se inventaron preguntas, evidencia o
causalidad.

La E2E local de Windows no alcanzó aserciones por el bloqueo conocido
`browserType.launch: spawn UNKNOWN`. Las E2E de Chat y Relaciones quedan
pendientes de la CI Linux de la cabecera publicada; no se presentan como
validadas localmente.

Adicionalmente, se integró en `TracePage.tsx` y `ReportPage.tsx` el bloque de
«Plan y decisiones», «Eventos reales» con tabla de llamadas instrumentadas,
enlaces contextuales a resultados con ancla `#result-*` y «Volver al reporte»,
alcanzando 291/291 pruebas aprobadas en la suite completa de Vitest (28 archivos).
