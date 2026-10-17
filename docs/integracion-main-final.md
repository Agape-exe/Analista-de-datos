# Integración final de main y develop

## Base y resultado

El 17 de octubre de 2026 se verificó el repositorio local y se ejecutó
`git fetch origin --prune`. Las referencias eran:

- main: `5482b7d79d4e355377a5bd058c42dc1b0d5b5cb2`.
- develop: `ab7330b782b968aca2577a602bcbc2c3d08f4e60`.

El árbol de trabajo estaba limpio en develop. No existían la rama
`integration/main-final`, un merge en curso ni
`C:\Users\diego\Downloads\integracion-main.patch`. La combinación se reconstruyó
como merge real en `integration/main-final`, partiendo de main y fusionando develop.
Se conserva la historia de ambas ramas; main no se modifica directamente.

## Resolución y capacidades conservadas

Se revisaron los diez archivos con conflictos y los archivos combinados
automáticamente. La composición de la API conserva los endpoints de intake y
exploración junto con análisis por archivo, reportes por run_id y descargas.
El frontend mantiene las rutas `/associations` y `/report`.

- Bootstrap mantiene las herramientas EDA, su almacén independiente y los registros
  de datasets/herramientas aislados por ejecución del workflow.
- El workflow conserva liberación de recursos en finally, telemetría, evidencia,
  evaluaciones, insights y configuración serializable.
- Critic consume Pearson/Spearman exitosos desde analysis_results si no existe una
  asociación equivalente, usa effect_size y admite el control singular sin quitar
  la validación del formato plural.
- El reporte es FAILED ante errores/etapas fallidas, SUCCESS cuando todas las etapas
  registradas finalizan correctamente y SKIPPED cuando hay etapas pendientes.
- Se mantiene scikit-learn para EDA y se conserva el lockfile. El entorno de develop
  no lo tenía instalado; `uv sync --locked` incorporó las dependencias faltantes.
- El benchmark conserva el generador determinista con semilla de develop; las
  mediciones anteriores de ambas ramas se identifican como históricas.

Tres pruebas de main suponían SUCCESS global al completar Analysis sin evidencia
suficiente para Critic/Insight. Se actualizaron para exigir Analysis SUCCESS y
reporte/Critic/Insight SKIPPED por separado, sin cambiar datos ni omitir pruebas.

## Validación local de la combinación

Entorno: Windows, Python 3.12.15 del proyecto y comandos npm.cmd.

- `python -m pytest tests -q`: **272 passed**.
- `python -m ruff check .`: sin errores.
- `python -m ruff format --check .`: 184 archivos con formato correcto.
- `npm.cmd test`: **16 pruebas aprobadas**, cinco archivos.
- `npm.cmd run generate:api`: tipos regenerados desde la API combinada.
- `npm.cmd run lint`: sin errores.
- `npm.cmd run build`: TypeScript y build de producción aprobados.
- `git diff --cached --check`: sin errores.

La regresión `test_main_develop_integration.py` carga un dataset para EDA, ejecuta
un análisis con control, exige las cinco etapas SUCCESS y evidencia/insights reales,
comprueba que el dataset EDA sigue disponible y recupera el mismo reporte tras
recrear la aplicación con SQLite persistente. También comprueba limpieza de cargas,
descarga Markdown y tokens no medidos en null.

Se verificó en modo SQLite de solo lectura que el reporte local
`bd97f271-f5a3-4897-9dcd-366713baba5c` continúa en SUCCESS con un insight y se puede
validar con el modelo actual. No se borraron bases existentes. Las pruebas de
reinicio usan bases temporales y una URL persistente explícita. Para el uso local:

`MDA_PERSISTENCE__DATABASE_URL=sqlite:///./analysis_reports.db`

La configuración predeterminada sigue siendo SQLite en memoria.

## Limitaciones conservadas

- En la integración original, Planner podía proponer ANOVA con una sola observación
  por grupo. La corrección posterior se documenta en
  [validación de grupos](anova-group-validation.md).
- El lector estricto rechaza CSV con comillas internas mal escapadas; no se omiten
  filas silenciosamente.
- Los umbrales de Critic son provisionales y no demuestran causalidad.
- No hay proveedor LLM productivo, paralelismo real de herramientas ni ciclo
  Critic → Planner operativo; el timeout cooperativo no interrumpe cálculos CPU-bound.
- Las métricas sin medición permanecen null. Ningún benchmark anterior sustituye
  los resultados de validación de esta carpeta.

## Revisión adicional previa a la fusión

Se revisaron composición, estados, persistencia y liberación de recursos. Las pruebas
de navegador detectaron que se reutilizaba un backend de desarrollo antiguo y que
las tablas de reportes heredaban un ancho mínimo global de 940 px. Se aislaron los
servidores E2E en 8016/5186 con proxy explícito y se quitó ese mínimo solo en reportes,
permitiendo el ajuste de texto en celdas.

Validación adicional en Microsoft Edge instalado: **4 pruebas E2E aprobadas**,
incluyendo reporte completo con cinco etapas SUCCESS, evidencia/insights, descargas
JSON/Markdown, recuperación por run_id y navegación de vuelta a EDA. Se verificaron
capturas del reporte a 390 px. También pasaron nuevamente las 16 pruebas unitarias
de frontend, ESLint y el build de producción.
