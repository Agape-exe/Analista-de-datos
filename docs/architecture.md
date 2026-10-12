# Arquitectura inicial

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

`AnalysisInput.source` discrimina CSV, TSV, TXT delimitado y SQL. Solo CSV tiene
adaptador. SQL referencia una conexión y una tabla; no recibe credenciales.

`LoadedDataset` es un dataclass local con `LocalTable` como interfaz de acceso a
columnas. `PandasLocalTable` vive en el adaptador CSV. No se serializa en el estado
del grafo y no se pasa al LLM. Una futura capa de ejecución administrará referencias
de datasets e inyectará su acceso local a las tools.

El CSV mínimo obtiene conteo y esquema de tipos inferidos por pandas. Esto no
equivale a un perfil estadístico ni a comprensión semántica. Las rutas se reciben
por contrato; no existe ruta de dataset fija en código.

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

`build_use_case` inyecta un LLM desactivado y registry vacío en cinco skeletons.
El grafo lineal solo recorre etapas; no carga la fuente ni ejecuta tools. El agente
de comprensión conserva un diccionario suministrado, sin inferir uno.

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

1. Conectar intake al caso de uso y administrar referencias locales de datasets.
2. Implementar profiling y una primera tool, con test estadístico significativo.
3. Agregar proveedor LLM mediante inyección, sin cambiar el contrato de agentes.
4. Implementar planner y ejecución con límites de hipótesis y tool calls.
5. Agregar critic loop acotado por `max_critic_cycles`.
6. Agregar fan-out de tools independientes, reducers determinísticos y límites
   de concurrencia; el flag `parallel_tools` hoy solo es configuración preparada.
7. Implementar insights respaldados por Evidence y métricas experimentales.

Para tareas CPU intensivas, diseñar ejecución en procesos o workers internos;
una firma async por sí sola no hace paralelos los cálculos. No se requieren
microservicios para esa evolución.
