# Contratos de Planner y Analysis

## 1. Objetivo del módulo

El módulo Planner & Analysis debe convertir una pregunta de análisis y el resumen
del dataset en un plan reproducible de solicitudes estadísticas, ejecutar esas
solicitudes sobre los datos locales y entregar resultados trazables al flujo común.

En el estado actual, esta capacidad todavía es un skeleton: `PlannerAgent` y
`AnalysisAgent` son invocables, pero devuelven `SKIPPED`; no hay ejecución de
tools ni proveedor LLM activo.

## 2. Responsabilidades de Planner Agent

### Existente

- `PlannerAgent` está en `app/agents/planner.py`, conserva el puerto LLM para
  compatibilidad futura y no lo invoca mientras el proveedor siga deshabilitado.
- `DeterministicAnalysisPlanner`, en
  `app/application/services/analysis_planning.py`, construye planes reproducibles
  sólo a partir de `AgentContext`, perfil, diccionario y configuración efectiva.
- Genera hipótesis exploratorias sin conclusiones causales y devuelve
  `AnalysisPlan` mediante `AgentUpdate.analysis_plan` cuando tiene pasos válidos.
- Prioriza columnas mencionadas en la pregunta; los empates se resuelven por tipo
  y nombre de columna para mantener orden estable.
- En FAST MODE limita la exploración a una hipótesis por familia compatible
  (numérica, categórica o ANOVA), además de respetar `max_hypotheses` y
  `max_tool_calls`.

Reglas implementadas: dos numéricas proponen `pearson` y `spearman`; dos
categóricas proponen `chi_square` y `cramers_v`; una categórica seguida de una
numérica propone `anova_one_way`. `partial_correlation` se añade sólo si la
pregunta nombra explícitamente una variable numérica de control después de un
indicador de control/ajuste. El plan nunca ejecuta una tool ni accede a filas.

El Planner devuelve `SKIPPED` con advertencia si faltan metadatos, no hay variables
compatibles, el presupuesto de tools es cero o el perfil tiene menos filas que
`minimum_sample_size`. Un identificador inconsistente entre contexto y perfil se
trata como fallo real de planificación.

### Propuesto para una implementación posterior

- Incorporar un proveedor LLM inyectado para enriquecer propuestas, manteniendo el
  plan determinístico como fallback y sin enviar filas completas.
- Coordinar la selección de análisis adicionales con Critic y la ejecución real
  con Analysis Agent.

## 3. Responsabilidades de Analysis Agent

### Existente

- `AnalysisAgent` está en `app/agents/analyst.py`.
- Recibe un `ToolRegistry` explícito además del proveedor LLM.
- El registry permite registrar instancias, consultar nombres, resolver una
  solicitud compatible y ejecutar solo tools autorizadas; rechaza nombres vacíos,
  registros duplicados, tools desconocidas y solicitudes no compatibles.
- `AnalyticsTool` define `name`, `supports(request)` y `execute(request)`.

### Propuesto para una implementación posterior

- Validar cada `AnalysisStep` y resolver su tool registrada.
- Ejecutar las solicitudes respetando dependencias, límites de llamadas, timeout
  y la configuración de paralelismo.
- Persistir en `AgentUpdate.analysis_results` los `AnalysisResult` exitosos,
  fallidos o omitidos, junto con warnings y errores del `AgentResult`.
- No convertir una ausencia de tool, un error estadístico o una muestra insuficiente
  en un resultado exitoso ficticio.

## 4. Contratos existentes y ubicación real

- `Hypothesis`, `ToolRequest`, `AnalysisStep`, `AnalysisPlan`, `AnalysisResult` y
  `AssociationResult`: `app/domain/models/analysis.py`.
- `AgentContext`, `AgentUpdate` y `AgentResult`: `app/application/dto/agent.py`.
- `AgentState`: `app/orchestration/state.py`.
- `AnalyticsTool`: `app/ports/analytics_tool.py`.
- `ToolRegistry`: `app/analytics/registry.py`.
- Puerto común de agentes: `app/ports/agent.py`.
- Configuración efectiva y overrides por ejecución:
  `app/config/settings.py` y `app/application/dto/analysis_input.py`.
- Grafo y adaptación de contexto/updates: `app/orchestration/graph.py`.

`AnalysisResult` solo permite valores estadísticos calculados cuando el estado es
`SUCCESS`; incluye método, variables, tamaño de muestra, warnings, duración y
metadatos. Los estados se definen en `app/domain/enums/statuses.py`.

## 5. Flujo de información entre módulos

El flujo actual es:

```text
DataUnderstanding → Planner (SKIPPED) → Analysis (SKIPPED) → Critic → Insight
```

`AgentState` contiene el estado serializable del workflow. Para cada nodo,
`app/orchestration/graph.py` construye un `AgentContext` explícito y aplica solo
los campos presentes en `AgentUpdate`. El contexto no contiene `LocalTable`, una
sesión de persistencia ni filas crudas.

El intake local usa `LoadedDataset` y `LocalTable` en
`app/application/dto/datasource.py`; `PandasLocalTable` vive en
`app/adapters/datasource/delimited_source.py`. `DatasetRegistry`, en
`app/application/services/dataset_registry.py`, mantiene por instancia las
referencias de datasets ya validados. Registra IDs únicos, verifica que cada
columna declarada esté disponible con el número de filas esperado y permite
recuperar, liberar o limpiar referencias. No es serializable ni global, por lo
que cada ejecución puede usar una instancia aislada y liberar sus datos al final.

El intake existente no se conecta todavía a ese registry: las cargas HTTP usan
archivos temporales que se eliminan al terminar el intake. Conectar el registry al
workflow requiere acordar el ciclo de vida de los datos locales sin retener rutas
temporales inválidas.

Tras la ejecución futura, `analysis_results` quedará en `AgentState` y será visible
para Critic mediante el siguiente `AgentContext`. `Evidence` y
`RelationshipAssessment` ya existen para la salida del crítico, pero el loop de
solicitudes adicionales aún no está implementado.

## 6. Herramientas estadísticas para el MVP

Las tools determinísticas de correlación están en
`app/analytics/statistics/correlation.py` y reciben un `DatasetRegistry` por
inyección. Sus métodos autorizados son:

- `pearson`: dos variables numéricas distintas en `ToolRequest.variables`.
- `spearman`: dos variables numéricas distintas en `ToolRequest.variables`; SciPy
  calcula rangos y maneja empates.
- `partial_correlation`: dos variables numéricas distintas en `variables` y una
  variable de control numérica en
  `parameters={"control_variable": "nombre_columna"}`.

Cada tool obtiene únicamente las columnas requeridas desde el dataset local por
`dataset_id`. Trabaja con observaciones completas, registra tamaño muestral,
coeficiente, valor p y tiempo de ejecución. La correlación parcial calcula
residuos lineales frente a una única variable de control e informa esa variable y
los grados de libertad en metadatos.

Las tools rechazan datasets o columnas desconocidos, valores no numéricos o
infinitos, muestras insuficientes, columnas constantes, controles sin variación y
resultados no finitos. En esos casos devuelven `AnalysisResult` con `FAILED`, sin
estadísticos calculados. Los resultados exitosos incluyen una advertencia explícita:
asociación estadística no demuestra causalidad.

Las tools estadísticas mixtas están en `app/analytics/statistics/mixed.py` y usan
la misma inyección local de `DatasetRegistry`. Sus métodos autorizados son:

- `chi_square`: dos variables categóricas distintas en `variables`. Construye una
  tabla de contingencia y devuelve estadístico Chi-cuadrado, valor p, grados de
  libertad, dimensiones y tamaño muestral. Usa `chi2_contingency` sin corrección
  de continuidad; advierte si hay frecuencias esperadas menores de cinco.
- `cramers_v`: dos variables categóricas distintas en `variables`. Reutiliza la
  misma tabla y Chi-cuadrado sin corrección de continuidad, y devuelve V de Cramér
  estándar (sin corrección por sesgo), valor p y dimensiones de la tabla.
- `anova_one_way`: `variables[0]` es la categoría de grupo y `variables[1]` el
  resultado numérico. Devuelve F, valor p, eta cuadrado, número de grupos y grados
  de libertad entre y dentro de grupos.

Las categorías admitidas son texto no vacío o códigos enteros; no se discretizan
variables continuas automáticamente. Las tres tools excluyen observaciones con
valores faltantes. También rechazan etiquetas ambiguas, tablas/categorías
insuficientes, valores numéricos no finitos, muestras insuficientes y resultados
degenerados. ANOVA exige al menos dos observaciones por grupo válido, no realiza
post-hoc y advierte que sus supuestos no se evalúan automáticamente.

`ToolRegistry.execute(request)` resuelve la tool por el método de `ToolRequest` y
exige que `supports(request)` sea verdadero antes de delegar la ejecución. No hay
registro global ni conexión al workflow: las tools se registrarán por ejecución
cuando se acuerde el ciclo de vida del dataset.

El repositorio conserva espacios para `profiling`, `association`, `anomalies` y
`clustering`; no se implementan aquí otras técnicas estadísticas ni agentes por
técnica.

## 7. Límites de ejecución y FAST MODE

Los límites ya modelados son `max_hypotheses`, `max_tool_calls`,
`max_critic_cycles`, `minimum_sample_size`, `timeout_seconds` y
`parallel_tools`. Los defaults empaquetados están en
`app/config/defaults.toml`; el modo por defecto es `fast`.

Planner ya consume `minimum_sample_size`, `max_hypotheses`, `max_tool_calls` y
`mode` para construir un plan acotado; no incrementa métricas porque no ejecuta
tools ni llama al LLM. El grafo aún no ejecuta tools, no hace fan-out paralelo ni
consume presupuestos durante Analysis. La implementación futura debe mantener esos
límites en la frontera de ejecución e instrumentar operaciones reales.

## 8. Dependencias con los demás integrantes

- **Integrante 1:** `DataSource`, `DatasetProfile`, `DatasetSchema`,
  `DataDictionary` y acceso local al dataset. Planner necesita sus metadatos; Analysis
  necesita una referencia local, no filas enviadas al LLM.
- **Integrante 2:** profiling, asociaciones y primeras tools estadísticas. Se
  requiere acordar nombres de tools, variables, parámetros y semántica de resultados.
- **Integrante 4:** `CriticAgent`, evidencia, evaluación de relaciones y solicitudes
  adicionales. El `AgentContext` ya tiene `analysis_results`, `evidence` y
  `relationship_assessments`, pero falta definir el contrato operativo del loop.
- **Integrante 5:** métricas, evidencia/reporting y API. Debe consumirse el
  `AnalysisResult` común y conservarse trazabilidad de duración, warnings y errores.

Los contratos compartidos permiten conexión básica sin cambios incompatibles.
Cualquier cambio de dominio, DTO o puerto requiere coordinación y revisión cruzada.

## 9. Componentes existentes reutilizables

- `SkeletonAgent` y el puerto `Agent` para el ciclo `AgentContext` → `AgentResult`.
- `ToolRegistry` para registro explícito de implementaciones.
- `AnalyticsTool` y `AnalysisResult` como frontera determinística.
- `AgentState`, `_agent_node` y `build_graph` para integración LangGraph.
- `EffectiveConfiguration` para overrides allowlisted por ejecución.
- `DataSourceRouter`, lectores CSV/TSV, `LocalTable` y `DatasetRegistry` para
  cálculo local aislado.
- `PearsonCorrelationTool`, `SpearmanCorrelationTool` y
  `PartialCorrelationTool` para asociación numérica determinística con SciPy.
- `ChiSquareIndependenceTool`, `CramersVTool` y `OneWayAnovaTool` para
  asociaciones categóricas y comparación unifactorial de medias con SciPy.
- Logging de etapas y `TimingRecorder` para trazabilidad y tiempos.

## 10. Cambios o decisiones pendientes de aprobación

- Cómo conectar el ciclo de vida de `DatasetRegistry` al workflow y a las cargas
  temporales sin serializar filas en `AgentState` ni retener rutas inválidas.
- Catálogo inicial, nombres y esquemas de parámetros de las tools con Integrante 2.
- Registro por ejecución de las tools de correlación cuando se integre Analysis
  Agent, manteniendo el aislamiento de `DatasetRegistry`.
- Registro por ejecución de las tools mixtas y decisión de Planner sobre cuándo
  una variable codificada puede tratarse como categoría o resultado numérico.
- Integración de `AnalysisPlan` con Analysis Agent, registro por ejecución de tools
  y validación final de muestras efectivas después de excluir faltantes.
- Política de dependencias entre `AnalysisStep` y comportamiento ante ciclos o
  solicitudes no soportadas.
- Semántica de ejecución paralela, límites por tool y cancelación bajo FAST MODE.
- Contrato del critic loop para pedir análisis adicionales sin romper el plan ni
  superar presupuestos.
- Política de persistencia de resultados y errores para reporte y reanudación.
- Los modelos compartidos actuales no se modifican en esta sesión; cualquier
  cambio incompatible queda deliberadamente pendiente de aprobación.
