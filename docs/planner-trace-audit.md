# Planner, contratos EDA y Traza — contrato de auditoría v1

## Alcance implementado

| Auditoría | Implementación |
| --- | --- |
| AUD-001/006 | Política determinista v2, prioridad del screening, identidad aditiva, omisiones ANOVA y Ruff |
| AUD-022 | Resultado completo/parcial por columna, estados y validación de parámetros Python/TypeScript |
| AUD-028 | Correspondencia explícita de métodos y reutilización de Kruskal-Wallis |
| AUD-025 | Snapshot persistido de pregunta, dataset, plan, decisiones y configuración |
| AUD-026 | Instrumentación conectada al flujo HTTP real; screening separado del presupuesto |
| AUD-029 | Opciones operativas del análisis almacenado y configuración efectiva visible |
| AUD-027 | Pantalla `/trace`, enlaces a resultados y contexto histórico explícito |
| AUD-015 | Textos y configuración coherentes con capacidades operativas |

## 1. Política de selección y ejemplos

El recorrido es `DataUnderstanding → Association → Planner → Analysis → Critic → Insight`.
Planner no calcula estadísticas ni envía filas a un LLM. Recibe metadatos y
asociaciones ordenadas; el resumen local de grupos se inyecta mediante un puerto.

1. Se excluyen tipos no analizables, constantes numéricas y columnas sin muestra mínima.
2. El pool por tipo contiene hasta 4 columnas en `fast`, y hasta 12 en `standard`.
   Prioriza menciones exactas en la pregunta, columnas del screening y el resto
   en orden determinista (continuas antes que códigos enteros; nombre como desempate).
3. Candidatas: pares numéricos, pares categóricos, categoría/numérica e identidades.
4. Para ANOVA se comprueban grupos antes de asignar presupuesto: al menos dos grupos
   completos con al menos dos observaciones cada uno. Se conserva la advertencia de
   ANOVA omitido aunque la pareja tampoco supere el screening.
5. Si hay asociaciones del screening, se conservan sus pares, candidatas nombradas
   por la pregunta y comprobaciones de identidad. No se vuelve silenciosamente a
   todas las candidatas si las seleccionadas resultan inviables.
   Si no hay asociaciones (screening vacío/no disponible), se usa el fallback de metadatos.
6. Orden: más menciones exactas en la pregunta, menor rango de screening, identidad
   antes de otras candidatas sin ranking, familia y orden de generación estable.
7. El método primario del screening se ejecuta primero cuando está soportado.
   Los diagnósticos conservan sus dependencias; no se ejecutan antes de su baseline.
8. `fast` selecciona como máximo una hipótesis por familia; `standard` permite más.
   Ambos respetan hipótesis y llamadas máximas. Los métodos truncados por presupuesto
   quedan en `omitted_methods`; las candidatas descartadas conservan un motivo.

### Identidad aditiva

Un nombre con el token `total` o `sum` solo propone una comprobación. Se enumeran
pares de componentes dentro del pool acotado, con prioridad explícita de la pregunta
y preferencia de columnas continuas. La identidad de tres variables no se elimina
por no ser un par del screening. Su ejecución consume presupuesto; el modo rápido
puede comprobar una sola propuesta. El nombre no demuestra que la identidad sea cierta.
La herramienta calcula residuos y coincidencias con su tolerancia existente.

| Entrada | Decisión esperada |
| --- | --- |
| Screening `y/z` antes de `a/b`, sin pregunta | `y/z` antes de `a/b`, aunque el nombre sea posterior |
| Pregunta menciona `a` y `b`, screening prioriza `y/z` | La candidata nombrada `a/b` tiene prioridad |
| Screening de pares y columnas `tax`, `interest`, `total` | La propuesta `tax + interest = total` sigue siendo elegible |
| Screening recomienda Kruskal-Wallis | Se planifica `kruskal_wallis`, no ANOVA |
| Grupo ANOVA con una observación completa | Se omite antes de gastar llamadas, con advertencia |
| Presupuesto cero | Planner/Analysis omitidos y decisión explicada; screening se mide aparte |

## 2. Correspondencia EDA → Analysis

| Screening | Método ejecutable |
| --- | --- |
| `pearson`, `spearman` | Mismo nombre; diagnósticos numéricos adicionales según contexto y presupuesto |
| `chi_square`, `cramers_v` | Mismo nombre |
| `anova` | `anova_one_way` |
| `kruskal_wallis` | `kruskal_wallis` |
| `mutual_information` | Evidencia complementaria de screening; sin herramienta equivalente en Analysis |
| Cualquier método desconocido | Advertencia de no soportado; no se sustituye silenciosamente |

`WorkflowKruskalTool` vive en exploración, reutiliza `measures.kruskal_wallis` y se
inyecta en bootstrap como `AnalyticsTool`. Analysis no importa implementaciones
privadas de exploración. Para los grupos se preserva la política EDA de excluir
grupos con menos de dos observaciones y se incluyen sus advertencias. Critic y la
presentación reconocen el estadístico H y el tamaño de efecto epsilon cuadrado.

## 3. Contrato EDA y ejemplos JSON compartidos

Fuente ejecutable para ambos lenguajes:
[`tests/fixtures/eda-result-variants.json`](../tests/fixtures/eda-result-variants.json).

- `status=SUCCESS`, `completeness=complete`: operación calculada.
- `status=SUCCESS`, `completeness=partial`: al menos una columna exitosa y otra omitida/fallida.
- `status=SKIPPED`: no aplicable; `result`, `effect_size` y `p_value` sin estadísticas.
- `status=FAILED`: entrada/cálculo inválido; tampoco incluye estadísticas calculadas.
- `column_results[columna]` conserva `status`, `result` y `warnings` de cada columna.
  Una columna omitida/fallida nunca contiene un resultado calculado.
- Los resultados válidos permanecen en el payload anterior `result`, para no obligar
  a los consumidores a migrar toda su lectura. Los campos adicionales son opcionales
  al leer resultados históricos.

En profiling, una columna con error no descarta las columnas ya calculadas. Si
ninguna produce resultado, el estado global es FAILED si hubo errores, o SKIPPED
si todas son omisiones. La insuficiencia de muestra de outliers usa ahora SKIPPED
explícito, no un SUCCESS que contenga una omisión oculta. La interfaz entiende tanto
este formato como el antiguo marcador `skipped` al leer resultados heredados.

Validación antes del cálculo:

- Variables distintas; columnas desconocidas y aridad incorrecta son errores.
- `relationship_ranking`: `top_k` entero 1..1000; `significance_level` numérico finito entre 0 y 1.
- `correlation_matrix` y `chart_correlation_heatmap`: `method=pearson|spearman`.
- `grouped_summary`: `max_groups` entero 1..máximo configurado.
- Parámetros desconocidos, booleanos usados como enteros y conversiones silenciosas se rechazan.

`api.ts` se genera desde OpenAPI. `edaOutcome` distingue variantes en TypeScript;
el transporte valida estados y resultados parciales antes de entregarlos a la UI.
`ColumnOutcomes` muestra omisiones/fallos sin presentar ceros ficticios.

## 4. Reporte ampliado y compatibilidad

El contrato anterior conserva sus campos. Se añaden campos opcionales/defaults:

| Campo | Contenido |
| --- | --- |
| `audit_version` | `"1"` para snapshots nuevos; `null` en reportes antiguos |
| `dataset_id`, `user_question` | Identidad del dataset y pregunta del análisis |
| `analysis_plan` | Hipótesis, pasos, dependencias, solicitudes, política y decisiones |
| `planning_decisions` | Decisiones incluso cuando no se pudo crear un plan |
| `screening_candidates` | Asociaciones ordenadas que recibió Planner |
| `screening_summary` | Ranking, ajustes de p, exclusiones y límites del screening calculado |
| `screening_configuration` | Opciones EDA efectivas, incluida semilla y límites |
| `requested_configuration` | Overrides solicitados, no configuración de infraestructura |
| `configuration` | Configuración efectiva de Analysis/performance |
| `capabilities` | Paralelismo, ciclo crítico y LLM actualmente desactivados |
| `execution_trace` | Eventos correlacionados y medidos |

No se serializa `AnalysisInput.source`, rutas locales, conexiones, credenciales ni
filas crudas. Los planes contienen nombres de variables, no tablas. SQLite/PostgreSQL
persisten el mismo payload JSON; no hace falta migrar las filas antiguas.

El timeout/fallo conserva el contexto y las etapas completadas, el plan y los
eventos disponibles. No inventa resultados para una herramienta interrumpida.
Reproducir cálculos requiere conservar externamente el mismo dataset y entorno
(`uv.lock`); el snapshot reproduce las decisiones, no almacena los datos originales.

## 5. Eventos y métricas reales

Bootstrap envuelve todas las herramientas del registro utilizado por la aplicación.
El adaptador de screening usa el mismo instrumentador con `scope=screening`.
Los agentes se instrumentan en el adaptador LangGraph, manteniendo application
independiente de observabilidad e infraestructura.

Cada evento nuevo tiene `event_id`, `sequence`, `run_id`, `kind`, `status` y
`duration_seconds`. Los eventos de herramientas añaden `scope`, agente, método,
dataset, paso, hipótesis, resultado y advertencias cuando existen.

- `metrics.tool_calls`: invocaciones reales presupuestadas de Analysis.
- `metrics.screening_calls`: invocaciones de screening; no consumen aquel presupuesto.
- Pasos bloqueados por dependencias, presupuesto o resolución aparecen como eventos
  de paso; no incrementan llamadas de herramientas.
- SKIPPED no se cuenta como fallo. Los eventos de agente incluyen warnings/errores.
- Los eventos se ordenan por finalización; las duraciones de agente incluyen sus
  herramientas y no deben sumarse con ellas para calcular el total.
- Valores no medidos permanecen `null`, especialmente en reportes históricos.

## 6. Configuración del análisis almacenado

`POST /analysis/datasets/{dataset_id}` acepta, por ejemplo:

```json
{
  "user_question": "Evaluar income y spend controlando por age.",
  "configuration": {
    "analysis": {"mode": "standard", "max_hypotheses": 3, "max_tool_calls": 6, "minimum_sample_size": 20},
    "performance": {"timeout_seconds": 30}
  }
}
```

Límites públicos: hipótesis 1..20, herramientas 0..100, muestra mínima 2..250000,
timeout finito >0 y <=120 segundos. Omitir opciones usa los settings del servidor;
`null`, campos extra, modos desconocidos y opciones no operativas dan 422.

La ejecución es secuencial. `fast` cambia la selección de familias; `standard`
amplía candidatas, no activa LLM ni un modo profundo. Los defaults son 3 hipótesis,
8 llamadas, muestra mínima 20, timeout 120 segundos, cero ciclos críticos y sin
paralelismo. Las claves antiguas de configuración local siguen siendo legibles,
pero su configuración efectiva normaliza ciclo/paralelismo a 0/false.

En Hallazgos se eligen únicamente opciones operativas y se muestra el snapshot
efectivo del reporte; una configuración actual del formulario no modifica un reporte previo.

## 7. Pantalla Traza y contexto

`/trace` usa el reporte mantenido por `ReportProvider`, incluyendo reportes
recuperados por ID sin dataset cargado. No vuelve a ejecutar herramientas.
Presenta agentes, tiempos, plan, decisiones, eventos, omisiones y enlaces a los
resultados por `analysis_id`. Cabecera y contenido identifican el reporte, no
atribuyen un reporte recuperado al dataset de intake activo. Nuevo dataset invalida
el reporte anterior y cancela solicitudes; un resultado tardío no sustituye el contexto.

Un reporte sin `audit_version` muestra **Reporte histórico sin instrumentación
verificable**. La ausencia de plan/eventos/tiempos se presenta como ausencia, no como
ejecución ficticia ni duración cero.

## 8. Pruebas y límites conocidos

Pruebas específicas: `test_eda_audit_contract.py`, `test_audit_trace_api.py`,
`test_audit_failure_snapshot.py`, pruebas Planner, `eda-contract.test.ts`,
`ReportPage.test.tsx` y recorrido Playwright de reporte completo con Traza.
La prueba de arquitectura conserva el snapshot OpenAPI previo y compara todas sus
propiedades/rutas, permitiendo solo las ampliaciones explícitas de este contrato.

Se reprodujeron en un worktree limpio de `e101e96` dos fallos preexistentes de
`tests/unit/test_critic.py`: `test_critic_reports_significant_results_without_robustness_as_preliminary`
y `test_critic_skips_when_no_result_is_significant`. Sus expectativas de filtrado por
significación difieren de la revisión descriptiva actual. No se cambia esa política
estadística para ocultar los fallos. La ampliación de Critic aquí solo reconoce Kruskal-Wallis.

### Validación local de esta entrega

- `uv run python scripts/check_architecture.py`: arquitectura correcta, 174 archivos de aplicación.
- `uv run pytest tests/architecture -q`: **24 aprobadas**.
- `uv run pytest -q`: **634 aprobadas, 2 fallos preexistentes** descritos arriba.
- `uv run ruff check .` y `uv run ruff format --check .`: correctos.
- `npm.cmd run generate:api`, `npm.cmd run lint`, `npm.cmd run build`: correctos.
- `npm.cmd test`: **191 aprobadas** en 16 archivos.
- Playwright con `PLAYWRIGHT_CHANNEL=msedge`, `e2e/report.spec.ts`, filtro
  `member 5 report|EDA and a complete report`: **2 aprobadas**. Incluye carga,
  configuración, eventos reales, Traza, enlaces a resultados, descargas,
  recuperación por ID y vista móvil. No se ejecutó toda la suite E2E.

Chromium administrado por Playwright no estaba instalado; se utilizó Microsoft Edge
disponible en el equipo. Una ejecución concurrente de ESLint/Playwright tuvo una
carrera con la limpieza de `test-results`; los checks secuenciales pasaron. Un test
de interfaz excedió la espera de 1 s bajo carga concurrente de pytest; la suite
frontend completa posterior pasó sin modificar ni omitir esa prueba.
