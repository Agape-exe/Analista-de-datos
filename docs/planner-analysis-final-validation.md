# Validación final de Planner & Analysis en `main`

La integración se basa en `origin/main` y adapta selectivamente el módulo proveniente de `origin/develop`; no fusiona ambas ramas ni reemplaza los componentes EDA.

Capacidades verificadas:

- planificación determinista y acotada por FAST MODE;
- seis cálculos estadísticos locales autorizados por `ToolRegistry`;
- validación de planes, dependencias, presupuestos y trazabilidad por paso;
- registros de datasets y herramientas aislados por ejecución, liberados al terminar;
- métricas de `tool_calls`, `analytics_time`, `profiling_time`, estados y duraciones de etapas;
- coexistencia con las rutas existentes de intake y exploración EDA.

Limitaciones conocidas: no existe proveedor LLM productivo, paralelismo real de herramientas, cancelación fuerte de operaciones CPU-bound, integración HTTP completa del análisis ni un ciclo Critic → Planner. Critic conserva sus contratos actuales y requiere coordinación separada para consumir directamente los nuevos resultados estadísticos.

## Medición reproducible

El 17 de octubre de 2026 se ejecutó `uv run python scripts/benchmark_planner_analysis.py` con Python 3.12.10 sobre Windows 11. Cada escenario usó cinco columnas, tres repeticiones y cinco herramientas invocadas. Las medianas observadas fueron: 50 filas, 0.0158323 s total y 0.0028720 s analítico; 500 filas, 0.0379682 s y 0.0072626 s; 5,000 filas, 0.2377681 s y 0.0503129 s. Son mediciones locales orientativas, no una extrapolación a cargas mayores ni una garantía de rendimiento.
