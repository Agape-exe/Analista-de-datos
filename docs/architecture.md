# Arquitectura

La integración conserva intake, EDA, Planner/Analysis, Critic, Insight, persistencia
y reportes dentro del mismo monolito. Ver [validación final](integracion-main-final.md)
y [contratos de Planner/Analysis](planner-analysis-contracts.md).

## Cliente web

El cliente React/TypeScript consume FastAPI y usa tipos generados desde OpenAPI.
New Analysis y Dataset Overview usan intake; Associations consume herramientas EDA;
Report ejecuta análisis por carga y recupera reportes por run_id. Las reglas de
lectura, estadística y clasificación permanecen en Python.

## Límites

El dominio depende únicamente de Pydantic y biblioteca estándar. Los Protocols en
ports dependen de DTO y modelos; los adaptadores implementan esos Protocols.
La aplicación invoca AnalysisWorkflow sin importar LangGraph. Los agentes reciben
AgentContext y devuelven AgentResult sin importar CSV ni SQLAlchemy.

```text
API → Application → Ports ← Adapters / Orchestration
                       ↓
                     Domain
Bootstrap → construcción de implementaciones y dependencias
```

application/dto/analysis_input.py comparte validación de configuración con
config/settings.py. Los modelos de dominio no importan Settings.

## Datos y recursos

CSV y TSV usan DataSourceRouter y el lector delimitado estricto. SQL y TXT tienen
contratos de entrada, pero sus adaptadores siguen pendientes. Se validan encabezados,
anchura de filas y tipos antes de construir el perfil; no se omiten filas inválidas.

LoadedDataset y LocalTable contienen datos locales y no se serializan en el contexto,
el estado ni el reporte. Las clasificaciones inferidas son roles estructurales, no
significado de negocio confirmado.

Hay dos ciclos de vida independientes:

- EDA: RegisteringDataUnderstanding publica un RegisteredDataset en el almacén LRU
  InMemoryDatasetStore. Intake, herramientas EDA y gráficos comparten ese almacén.
- Análisis: build_use_case configura una fábrica por ejecución. DataUnderstandingAgent
  registra el LoadedDataset validado en un DatasetRegistry local; las seis herramientas
  estadísticas reciben ese registro. El workflow libera sus recursos en finally,
  incluso ante fallo, timeout o cancelación. Esa limpieza no borra datasets EDA.

## Contratos y flujo actual

El grafo ejecuta DataUnderstanding → Planner → Analysis → Critic → Insight. Cada nodo
recibe AgentContext validado y aplica únicamente los campos explícitos de AgentUpdate.
Planner construye un plan reproducible con metadatos y límites; Analysis valida IDs,
dependencias y presupuesto antes de ejecutar herramientas autorizadas secuencialmente.
Cada resultado conserva trazabilidad de paso e hipótesis.

Critic puede leer Pearson/Spearman exitosos de analysis_results si no hay una
asociación equivalente. Usa effect_size y valida controles en metadatos, incluido el
formato singular como fallback. Solo genera evaluaciones cuando existe evidencia;
Insight conserva los vínculos con esa evidencia y las limitaciones.

El grafo termina ante una etapa FAILED. El reporte global es FAILED ante errores o
etapas fallidas, SUCCESS si todas las etapas registradas son exitosas y SKIPPED si
quedan etapas pendientes. Analysis SUCCESS no implica éxito global. AnalysisResult
no admite estadísticas calculadas en estados no exitosos.

El timeout cubre toda la ejecución cooperativa; no garantiza interrumpir SciPy/Pandas
CPU-bound. Cancelaciones externas se propagan. Los errores fatales no conservan
checkpoints parciales. El ciclo Critic → Planner y el paralelismo real son futuros.

## Métricas y trazabilidad

ExperimentMetrics mantiene null para indicadores no medidos. Profiling, análisis,
duraciones por etapa, llamadas reales a herramientas y tiempo hasta el primer insight
se miden donde ocurren. El proveedor LLM predeterminado está deshabilitado; no hay
consumo de tokens simulado. La telemetría registra las fronteras instrumentadas y
la API añade X-Request-ID para correlación HTTP.

## Persistencia y reportes

SqlAlchemyAnalysisRepository implementa AnalysisRepository con la tabla analysis_reports,
guardado idempotente por run_id y validación del payload con AnalysisReport. El ciclo
de vida de FastAPI inicializa el repositorio y libera el engine al cerrar. No se
crean archivos de base de datos al importar el módulo.

SQLite en memoria es el valor predeterminado. Una URL persistente explícita permite
recuperar reportes tras reiniciar, por ejemplo
MDA_PERSISTENCE__DATABASE_URL=sqlite:///./analysis_reports.db. Las bases locales y
reportes descargados no se incluyen en Git.

La API conserva /intake, /tools y /datasets/{dataset_id}/tools/{tool_name}, junto con
/analysis, /analysis/upload, /reports/{run_id}, /metrics y /markdown. Las dos últimas
son rutas relativas al recurso de reporte. MarkdownReportRenderer y la pantalla de
reportes presentan evidencia, estados, errores y métricas sin inventar conclusiones.

## Extensión prevista

- Proveedor LLM inyectado con resúmenes acotados, sin filas crudas.
- Ciclo crítico acotado por max_critic_cycles y contratos de análisis adicional.
- Paralelismo con dependencias, concurrencia y cancelación definidos; la firma async
  por sí sola no hace paralelos los cálculos CPU-bound.
- Validación experimental de umbrales y calidad de detección, sin afirmar causalidad.
