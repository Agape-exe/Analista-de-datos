# Planner & Analysis integrado en `main`

## Alcance implementado

El flujo analítico determinista se incorporó sin sustituir el motor EDA existente. Para cada llamada a `build_use_case(settings).execute(...)`, el workflow crea un `DatasetRegistry` y un `ToolRegistry` nuevos. Data Understanding registra el `LoadedDataset` validado, Planner construye un `AnalysisPlan` a partir de metadatos y Analysis ejecuta solo las herramientas autorizadas. Al finalizar, incluso ante fallo o cancelación, el workflow libera las referencias del registro local.

Los objetos con filas locales (`LoadedDataset`, `LocalTable` y DataFrames) no forman parte de `AgentContext`, `AgentState` ni de `AnalysisReport`.

## Herramientas autorizadas

`build_statistical_tool_registry()` registra explícitamente:

- `pearson` y `spearman` para dos variables numéricas;
- `partial_correlation`, con `parameters={"control_variable": "..."}`;
- `chi_square` y `cramers_v` para dos variables categóricas;
- `anova_one_way`, con grupo categórico primero y resultado numérico segundo.

Las herramientas validan dataset, columnas, tipos locales, muestras completas, valores no finitos, columnas constantes y casos degenerados. Los fallos devuelven `AnalysisResult` con estado `FAILED` y sin estadísticas inventadas. Todas las asociaciones incluyen una advertencia de no causalidad.

## Planner y FAST MODE

El planificador es determinista y no llama al proveedor LLM. Usa los tipos semánticos del perfil y, cuando existe, el diccionario de datos. En modo `fast` limita cada familia de análisis y toma un conjunto acotado de cuatro columnas por tipo; las columnas mencionadas de forma completa en la pregunta se priorizan antes que las alfabéticas. El plan respeta `max_hypotheses`, `max_tool_calls` y `minimum_sample_size`.

La correlación parcial solo se propone cuando la pregunta expresa una operación de control o ajuste y menciona exactamente una columna numérica admisible. Coincidencias dentro de otras palabras o controles ambiguos no generan ese método.

## Compatibilidad con EDA y etapas posteriores

`InMemoryDatasetStore`, `RegisteredDataset`, `build_tool_registry`, `build_exploration_use_case` y `build_intake_use_case` continúan siendo el camino de EDA y exploración. El registro de Planner & Analysis es independiente por ejecución, por lo que no comparte referencias con el almacén EDA.

El workflow conserva el orden Data Understanding → Planner → Analysis → Critic → Insight y conserva métricas reales de perfilado, análisis y llamadas a herramientas. Critic permanece sin cambios: su entrada histórica son `associations`; esta integración entrega resultados en `analysis_results` y no modifica ni presume una reinterpretación automática por Critic. Esa adaptación, si el equipo la requiere, debe coordinarse con su responsable.

La ejecución de herramientas es secuencial. `parallel_tools` no habilita paralelismo real; los cálculos SciPy/Pandas son CPU-bound y un timeout cooperativo no equivale a interrupción fuerte de esos cálculos.

## Validación

Las pruebas de la integración cubren planificación, validación estructural, seis herramientas reales, presupuestos FAST, aislamiento concurrente y serialización del reporte. El benchmark opcional `scripts/benchmark_planner_analysis.py` ejecuta el caso de uso real con CSV temporal y no forma parte de la suite habitual.
