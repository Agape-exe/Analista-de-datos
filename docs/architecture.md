# Arquitectura inicial

## Cliente web

`frontend/` contiene el cliente React/TypeScript del mismo sistema. Consume FastAPI
por HTTP y presenta los contratos Pydantic expuestos en OpenAPI. Los tipos de API
se generan para TypeScript; las reglas de lectura y clasificación siguen en Python.
New Analysis y Dataset Overview se conectan a `/intake`, separado del futuro
workflow completo de `/analysis`. Detalles en [frontend.md](frontend.md).

## Límites

Dominio depende únicamente de Pydantic y biblioteca estándar. Los Protocols en
`ports` dependen de DTO y modelos. Los adaptadores implementan esos Protocols.
La aplicación invoca `AnalysisWorkflow`, sin importar LangGraph. Los agentes
reciben `AgentContext` y devuelven `AgentResult`, sin importar CSV ni SQLAlchemy.

```text
API → Application → Ports ← Adapters / Orchestration
                       ↓
                     Domain
Bootstrap → construcción de implementaciones y dependencias
```

`application/dto/analysis_input.py` usa los modelos tipados de opciones de
`config/settings.py`. Es una dependencia explícita del esqueleto para compartir
validación; los modelos del dominio no importan Settings.

## Datos y fuentes

`AnalysisInput.source` discrimina CSV, TSV, TXT delimitado y SQL. CSV y TSV tienen
adaptadores seleccionados mediante `DataSourceRouter`. SQL referencia una conexión
y una tabla; su adaptador y el de TXT están pendientes.

`LoadedDataset` es un dataclass local con `LocalTable` como interfaz de acceso a
columnas. `PandasLocalTable` vive en el lector delimitado compartido. No se serializa en el estado
del grafo y no se pasa al LLM. Una futura capa de ejecución administrará referencias
de datasets e inyectará su acceso local a las tools.

Los lectores validan encabezados y anchura de filas antes de inferir tipos físicos.
El servicio local aplica reglas puras de clasificación y genera un perfil básico
con conteos de nulos/únicos. Las reglas infieren roles estructurales, no significado
de negocio confirmado. Las rutas se reciben por contrato.

## Contratos

- `AnalysisResult`: formato común, estados SUCCESS/FAILED/SKIPPED, valores JSON,
  duraciones en segundos y estadísticas opcionales. No admite resultados calculados
  en estados no exitosos.
- `DataDictionary`: entradas con fuente y confianza, sin columnas duplicadas.
- `AgentUpdate`: actualización tipada; solo campos explícitos se aplican al estado.
- `AgentState`: estado propio de una ejecución LangGraph. Los agentes no lo reciben
  como memoria global compartida; reciben un contexto explícito validado.
- `LLMRequest`: instrucciones y contexto agregado. Al agregar proveedores, construir
  resúmenes acotados, nunca incluir filas crudas en `summary`.
- `ExperimentMetrics`: indicadores no medidos en `None`. No equiparar ausencia de
  medición con una puntuación cero.

## Flujo actual

`build_use_case` inyecta `DataUnderstandingService` mediante el puerto
`DataUnderstanding` en el primer agente. El servicio lee la fuente a través de
`DataSource`, aplica reglas del dominio y devuelve datos locales y metadatos. El
agente solo propaga perfil, diccionario, dataset_id y métricas. Los demás agentes
siguen siendo skeletons con LLM desactivado y registry vacío.

El grafo detiene la ejecución si una etapa devuelve FAILED. Después de un intake
exitoso, las siguientes etapas siguen devolviendo SKIPPED. El reporte incluye
`dataset_profile`, `data_dictionary` y el tiempo de intake en `profiling_time`.

El reporte registra `run_id`, estado, advertencias, estados de etapas y duraciones.
El resultado final es SKIPPED o FAILED, nunca un análisis exitoso ficticio. El
timeout aplica a toda la ejecución. Errores no recuperados se convierten en un
reporte FAILED con tiempo total; cancelaciones externas se propagan. Los errores
fatales no conservan todavía checkpoints parciales.

Los contadores LLM/tool son cero en este skeleton porque esas operaciones no
existen aún. Al implementarlas, instrumentar las fronteras reales y reemplazar
estos contadores. No añadir llamadas reales sin actualizar esa instrumentación.

## Persistencia y reportes

`AnalysisRepository` y `ReportRenderer` son contratos. SQLAlchemy únicamente
proporciona factorías de engine/sesiones; no existen tablas ni repositorio completo.
La URL predeterminada usa SQLite en memoria y no crea archivos al importar.

## Extensión prevista

1. Administrar referencias locales de datasets para la futura ejecución de tools;
   el intake actual devuelve datos locales pero no los guarda en un registry global.
2. Implementar profiling avanzado y una primera tool, con test estadístico significativo.
3. Agregar proveedor LLM mediante inyección, sin cambiar el contrato de agentes.
4. Implementar planner y ejecución con límites de hipótesis y tool calls.
5. Agregar critic loop acotado por `max_critic_cycles`.
6. Agregar fan-out de tools independientes, reducers determinísticos y límites
   de concurrencia; el flag `parallel_tools` hoy solo es configuración preparada.
7. Implementar insights respaldados por Evidence y métricas experimentales.

Para tareas CPU intensivas, diseñar ejecución en procesos o workers internos;
una firma async por sí sola no hace paralelos los cálculos. No se requieren
microservicios para esa evolución.
