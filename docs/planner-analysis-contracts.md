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

- `PlannerAgent` está en `app/agents/planner.py` y hereda de `SkeletonAgent`.
- Recibe `AgentContext` y puede devolver `AgentResult` mediante el puerto común.
- El contexto ya expone pregunta de usuario, perfil, diccionario, asociaciones,
  configuración y un posible `AnalysisPlan`.

### Propuesto para una implementación posterior

- Priorizar hipótesis representadas por `Hypothesis`.
- Producir un `AnalysisPlan` con pasos ordenados (`AnalysisStep`) y solicitudes
  `ToolRequest` válidas para el registry.
- Respetar `max_hypotheses`, `max_tool_calls`, el modo `fast` y las variables
  disponibles en el perfil/diccionario.
- Mantener el razonamiento del LLM resumido; las filas completas no forman parte
  del contexto enviado al proveedor.

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

## 6. Herramientas estadísticas previstas para el MVP

El repositorio tiene espacios para `profiling`, `association`, `statistics`,
`anomalies` y `clustering` en `app/analytics/`, pero sus implementaciones de
producción aún no están registradas. La primera integración debe coordinarse con
Integrante 2 y usar el contrato `AnalyticsTool`.

`ToolRegistry.execute(request)` resuelve la tool por el método de `ToolRequest` y
exige que `supports(request)` sea verdadero antes de delegar la ejecución. No hay
tools productivas registradas ni algoritmos estadísticos implementados en esta
sesión.

Como alcance previsto, sujeto a aprobación, el MVP puede comenzar con profiling
estadístico básico y asociación/correlación, seguido por las tools determinísticas
que el equipo acuerde. No se agregan aquí algoritmos ni agentes por técnica.

## 7. Límites de ejecución y FAST MODE

Los límites ya modelados son `max_hypotheses`, `max_tool_calls`,
`max_critic_cycles`, `minimum_sample_size`, `timeout_seconds` y
`parallel_tools`. Los defaults empaquetados están en
`app/config/defaults.toml`; el modo por defecto es `fast`.

Actualmente estos valores solo configuran el skeleton: el grafo aplica el timeout
global, pero no ejecuta tools, no hace fan-out paralelo y no consume presupuestos
de hipótesis o llamadas. La implementación futura debe hacer cumplir esos límites
en la frontera de Planner/Analysis y mantener contadores reales en métricas.

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
- Logging de etapas y `TimingRecorder` para trazabilidad y tiempos.

## 10. Cambios o decisiones pendientes de aprobación

- Cómo conectar el ciclo de vida de `DatasetRegistry` al workflow y a las cargas
  temporales sin serializar filas en `AgentState` ni retener rutas inválidas.
- Catálogo inicial, nombres y esquemas de parámetros de las tools con Integrante 2.
- Política de dependencias entre `AnalysisStep` y comportamiento ante ciclos o
  solicitudes no soportadas.
- Semántica de ejecución paralela, límites por tool y cancelación bajo FAST MODE.
- Contrato del critic loop para pedir análisis adicionales sin romper el plan ni
  superar presupuestos.
- Política de persistencia de resultados y errores para reporte y reanudación.
- Los modelos compartidos actuales no se modifican en esta sesión; cualquier
  cambio incompatible queda deliberadamente pendiente de aprobación.
