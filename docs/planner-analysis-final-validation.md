# Validación final de Planner & Analysis

## Estado y arquitectura

El módulo transforma metadatos locales en un `AnalysisPlan` determinístico y
ejecuta las solicitudes autorizadas sobre datasets en memoria. El flujo operativo
probado es `DataUnderstanding → Planner → Analysis → Critic → Insight`.

Cada llamada a `LangGraphWorkflow.run()` crea su propio `DatasetRegistry`,
`ToolRegistry` y agentes. Data Understanding registra el `LoadedDataset` ya leído;
el estado serializable conserva sólo identificador, perfil, diccionario, plan y
resultados. El workflow libera el registry en `finally` ante éxito, fallo, timeout
o cancelación.

## Capacidades implementadas y probadas

- Planner determinístico: prioriza menciones exactas, evita identificadores/texto,
  mantiene pools acotados y aplica FAST MODE, presupuesto y tamaño mínimo.
- Analysis Agent: valida IDs de paso e hipótesis, referencias, dataset, dependencias
  y ciclos; ejecuta secuencialmente las tools registradas y conserva éxitos
  independientes ante fallos posteriores.
- Tools: Pearson, Spearman, correlación parcial, Chi-cuadrado, V de Cramér y ANOVA
  de un factor. Las pruebas integrales validan coeficientes/estadísticos, valores p,
  tamaños muestrales y tamaños de efecto con escenarios sintéticos conocidos.
- Resultados y métricas: `step_id`/`hypothesis_id`, `tool_calls` reales,
  `analytics_time`, `profiling_time`, duración total, estados y duraciones de etapa.
  `iterations=1` significa una sola ejecución lineal del workflow, no un ciclo
  Critic → Planner.

Los resultados estadísticos expresan asociación o diferencias de grupos; no
establecen causalidad.

## FAST MODE, errores y recursos

FAST MODE limita hipótesis, pool de columnas y llamadas. Con presupuesto cero no
planifica/ejecuta tools; con presupuesto limitado Analysis marca los pasos restantes
como `SKIPPED`. Errores de estructura invalidan el plan; una tool desconocida o un
error estadístico generan `FAILED` sin valores calculados ficticios.

Las pruebas cubren faltantes, columnas constantes, dataset desconocido, muestras
insuficientes, presupuesto cero, duplicación de IDs de hipótesis, dependencias y
cancelación externa tras registrar el dataset. La cancelación se propaga y el
registry queda vacío; esto no demuestra interrupción fuerte de cálculos CPU-bound.

La revisión detectó y corrigió una validación ausente: un plan podía contener IDs de
hipótesis duplicados. `AnalysisAgent` ahora rechaza el plan completo antes de invocar
tools, con una prueba de regresión específica.

## Reproducibilidad y rendimiento

La misma entrada ejecutada dos veces mantiene métodos, variables, orden lógico y
resultados equivalentes; se excluyen IDs y duraciones de esa comparación.

Medición local el 2026-10-16 con Python 3.12.10, Windows 11, semilla `20261016`,
cinco columnas, tres repeticiones y workflow real:

| Filas | Mediana total (s) | Mediana análisis (s) | Tools | Estado |
| ---: | ---: | ---: | ---: | --- |
| 50 | 0.0177303 | 0.0032163 | 5 por corrida | SUCCESS |
| 500 | 0.0404850 | 0.0089254 | 5 por corrida | SUCCESS |
| 5,000 | 0.2573867 | 0.0643573 | 5 por corrida | SUCCESS |

El script reproducible es `scripts/benchmark_planner_analysis.py`. Estas cifras son
orientativas de ese ambiente; no se extrapolan a datasets masivos ni procesamiento
distribuido.

## Limitaciones y coordinación

- `parallel_tools` no habilita paralelismo real; la ejecución es secuencial.
- El timeout global sólo cancela etapas cooperativas, no garantiza detener SciPy o
  Pandas mientras bloquean el hilo.
- No hay proveedor LLM, inferencia causal, ciclo Critic → Planner ni integración
  HTTP completa de cargas temporales.
- Critic, Insight, persistencia/reporting y API siguen siendo responsabilidades de
  sus módulos.
- El PR #7 del Integrante 5 continúa abierto contra `main` y modifica bootstrap,
  graph, estado, métricas/reporting y documentación. Cualquier integración deberá
  resolver ese solapamiento conservando los recursos aislados por corrida.

La validación no demuestra ausencia total de defectos: confirma los escenarios
automatizados ejecutados para el cierre del módulo.
