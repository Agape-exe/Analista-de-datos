# AUD-007 — Integración continua

La [investigación Linux de integración](integrante5-integracion-linux.md)
documenta la comparación real PR/develop, los rechazos de capacidad y las
dependencias pendientes. No se han relajado pruebas ni límites; AUD-007 sigue
pendiente de una ejecución completa aprobada.

Estado de la preparación inicial: **CI configurada; pendiente de validación en
GitHub y de resolver los fallos obligatorios existentes**. Los resultados de
esa preparación se conservan abajo como historial. La revisión de entrega,
su base, pruebas repetidas y evidencia remota se registran en
[Entrega de I5](integrante5-entrega.md). AUD-007 requiere todos sus jobs reales
aprobados en el SHA correspondiente; preparar el workflow no la aprueba.

Revisión de entrega: el [PR #41](https://github.com/Alexander20L/Analista-de-datos/pull/41)
ya tiene Actions real. Las ejecuciones `39107327083` (`87604e3`) y `39130025022`
(`d6acf37`) terminan en **failure**: pytest y Ruff reproducen fallos de base;
la segunda ejecución Chromium Linux da 17 aprobadas y tres fallidas, sin
omitidas. Métricas/Traza pasan sus cuatro E2E. Los nueve jobs y sus URLs están
en [Entrega de I5](integrante5-entrega.md); no se declara AUD-007 aprobada.

## Base y alcance

Se leyeron `AGENTS.md`, `docs/architecture.md`, `docs/aud-037-summary.md` y las
configuraciones reales antes de editar. No existen instrucciones AGENTS anidadas
ni workflows anteriores. Los criterios disponibles de AUD-007 están en
[Preparación de AUD-007](aud-037-summary.md#preparación-de-aud-007) y en la
solicitud de esta implementación.

Base local: `adcd0ec4e7e96dc1e4b84cf792e3612a91ca23ea`, inicialmente en
`feat/aud-037-develop-adaptation`; trabajo conservado en `codex/aud-007-ci`.
`git symbolic-ref refs/remotes/origin/HEAD` indicó `origin/main`. La consulta
real `git ls-remote --symref origin HEAD` confirmó `refs/heads/main` en
`914065b15987b6a092e702acf3b8222a423ab123`. No se incorporaron otras ramas.

Los cambios propios son `.github/workflows/ci.yml`,
`frontend/playwright.config.ts`, este documento y el enlace desde AUD-037.
No se cambian algoritmos, configuración de producción, contratos ni lockfiles.
El servidor E2E fija el límite de dataset en **2.097.152 bytes**, sin aumentarlo.

## Workflow

`.github/workflows/ci.yml` se activa en todos los pull requests, pushes a `main`
y `develop`, y manualmente. Usa Ubuntu 24.04, `contents: read`, checkout sin
credenciales persistentes y acciones fijadas por SHA. Cancela ejecuciones
anteriores del mismo PR/ref. No contiene despliegues ni consume secretos.

Nueve comprobaciones independientes, sin dependencias `needs`, con matrices
`fail-fast: false` y sin `continue-on-error`:

| Grupo | Comprobaciones | Tiempo máximo por job |
| --- | --- | --- |
| Backend | checker AST, pytest arquitectura, pytest completo, Ruff lint, Ruff formato | 20 minutos |
| Frontend | Vitest completo no interactivo, ESLint, TypeScript/Vite build | 15 minutos |
| E2E | suite Playwright completa con Chromium Linux | 25 minutos |

Cada comprobación conserva su código de salida. Un fallo de lint/arquitectura
no impide conocer los resultados de las demás. ESLint y Playwright usan jobs
y checkouts distintos, por lo que no compiten sobre `test-results`; en la
validación local se ejecutó ESLint antes de iniciar E2E.

### Instalación y versiones

- Python **3.12** (compatible con `requires-python >=3.12` y Ruff `py312`),
  instalado mediante setup-uv. Localmente: **3.12.15**.
- uv **0.13.1**, fijado explícitamente. `uv sync --locked --group dev` valida
  `uv.lock` contra el manifiesto, incluye pytest/httpx/Ruff y falla ante un
  lock desactualizado. `UV_LOCKED=true` conserva esta condición en `uv run`,
  incluido el proceso uvicorn iniciado por Playwright.
- Node **24.18.0**, compatible con `engines.node >=20.19.0`; npm local **11.16.0**.
  `npm ci` instala `frontend/package-lock.json` sin regenerarlo.
- Las herramientas se toman de los locks: Ruff **0.17.0**, Vitest **4.1.11**,
  Playwright **1.64.0**. No se instala Playwright global ni una versión flotante.
- Caché uv asociada a `uv.lock`; caché npm asociada a
  `frontend/package-lock.json`. Los entornos instalados se validan de nuevo en
  cada job. No se cachean navegadores ni datasets.

La instalación Linux de navegador y bibliotecas del sistema es
`npm exec --no -- playwright install --with-deps chromium`, tras `npm ci`.
Se sigue el [procedimiento oficial de Playwright](https://playwright.dev/docs/ci-intro)
y la [configuración de setup-uv](https://github.com/astral-sh/setup-uv).

### Servicios y artefactos

Playwright levanta uvicorn en `127.0.0.1:8016` desde la raíz y espera `/health`;
levanta Vite en `127.0.0.1:5186` y espera su URL. Ambos tienen 120 segundos
para arrancar, sin reutilizar servidores externos. Se conservan los overrides
de puertos `E2E_BACKEND_PORT` y `E2E_FRONTEND_PORT`; el proxy `/api` apunta al
backend local. Se mantiene un worker y se prohíbe `.only` en CI.

El backend E2E usa explícitamente desarrollo, SQLite en memoria,
LLM desactivado y el límite de 2 MiB. No requiere PostgreSQL, producción,
credenciales, APIs LLM ni despliegues. La suite usa sus fixtures del repositorio.

La revisión de entrega añade `frontend/scripts/run-e2e-ci.mjs`: descubre todos
los archivos con el listado JSON de Playwright y ejecuta cada uno con procesos
nuevos de Playwright/Uvicorn/Vite. Evita compartir cuotas entre escenarios de
archivos distintos, sin aumentar límites ni reintentar. Guarda los informes por
archivo, ejecuta todos y devuelve fallo si cualquiera falla. Las nueve
comprobaciones siguen siendo obligatorias. Los resultados reales y el diagnóstico
del primer Linux están en [Entrega de I5](integrante5-entrega.md).

Con `always()` se suben JUnit de pytest/arquitectura/Vitest y el informe HTML,
JUnit, capturas y trazas de Playwright cuando existan. Las capturas y trazas se
conservan ante fallos, con retención de artefactos de siete días. Las rutas de
subida están acotadas a informes/resultados, sin `.env`, bases ni directorios
de datos. Si no se pudo crear un informe, se advierte su ausencia; el paso
obligatorio fallido sigue fallando.

## Validación local (Windows)

Los siguientes resultados pertenecen al árbol real, incluidos los cambios locales
anteriores. Los comandos se ejecutaron desde la raíz salvo los de npm, que se
ejecutaron en `frontend`. Los informes y logs locales están en
`.pytest_cache/aud007-*`, ignorados por Git.

| Comando | Resultado observado |
| --- | --- |
| `git ls-remote --symref origin HEAD` | main confirmada, revisión indicada arriba |
| `uv sync --locked --group dev --python 3.12` | Correcto, 74 paquetes resueltos y 73 comprobados |
| `uv run --locked python scripts/check_architecture.py` | Correcto, 173 archivos Python |
| `uv run --locked pytest tests/architecture -q` | 24 aprobadas |
| `uv run --locked pytest --junitxml=.../aud007-backend.xml` | **636 aprobadas, 4 fallidas**, 83,46 s |
| `uv run --locked ruff check . --output-format concise` | **2 errores**, detallados abajo |
| `uv run --locked ruff format --check .` | Correcto, 282 archivos ya formateados |
| `npm ci` | Correcto, 303 paquetes instalados, 0 vulnerabilidades notificadas |
| `npm test -- --reporter=default --reporter=junit --outputFile=../.pytest_cache/aud007-vitest.xml` | Primera ejecución: **189 aprobadas, 1 fallida** por timeout |
| Mismo comando Vitest, con salidas `aud007-vitest-repeat.*` | Segunda ejecución aislada: **189 aprobadas, 1 fallida**, timeout en otra prueba |
| `npm test -- --maxWorkers=2 --reporter=default --reporter=junit --outputFile=../.pytest_cache/aud007-vitest-ci.xml` | **190 aprobadas**, 14 archivos, 51,64 s; configuración de concurrencia usada en CI |
| `npm run lint` | Correcto |
| `npm run build` | Correcto, TypeScript y Vite |
| `npm exec --no -- playwright install chromium` | Correcto, Chromium 156.0.8078.4 (build Playwright 1248), FFmpeg y headless shell para Windows |
| `$env:CI='true'; $env:PLAYWRIGHT_CHANNEL='chromium'; npm run test:e2e` | **16 fallidas antes de ejecutar aserciones**: Chromium no pudo iniciarse, `browserType.launch: spawn UNKNOWN` |
| `actionlint.exe -color .github/workflows/ci.yml` | Correcto, actionlint 1.7.12 descargado con SHA-256 verificado contra los checksums de su release |
| `git diff --check` | Correcto |

### Fallos previos y resultados intermitentes

Ruff se ejecutó antes de editar y encontró:

- `app/modules/analysis/application/services/analysis_planning.py:273`: F841,
  variable `unranked` sin uso.
- `tests/unit/test_planner_agent.py:10`: F401, import `AssociationResult` sin uso.

La suite backend se inició antes de editar y reprodujo los cuatro casos de
[la validación previa](hexagonal-architecture-validation.md#3-comprobaciones-realizadas):

| Prueba | Causa observada |
| --- | --- |
| `test_fast_mode_uses_next_valid_anova_after_omitting_sparse_pair` | Falta advertencia ANOVA para `a_sparse` |
| `test_default_csv_produces_measured_critic_and_insights_without_a_question` | Falta resultado `additive_identity` |
| `test_critic_reports_significant_results_without_robustness_as_preliminary` | Más evaluaciones que la única esperada |
| `test_critic_skips_when_no_result_is_significant` | Se devuelve SUCCESS en lugar de SKIPPED |

Los archivos de estas pruebas y los dos archivos señalados por Ruff no presentan
diff respecto de HEAD. Estos fallos no se corrigen ni se excluyen en AUD-007;
mantendrán rojas sus comprobaciones obligatorias.

La primera ejecución Vitest, concurrente con lint/build y la instalación del
navegador, agotó la espera de `Resumen del dataset` en
`DataDictionaryPage.test.tsx:61`, caso «muestra columnas del intake existente sin
nuevas consultas ni edición». No se modificaron código UI, pruebas, expectativas
ni timeouts. Ese resultado por sí solo no prueba un defecto de la línea base ni
una regresión de CI; se conserva como ejecución fallida. La segunda ejecución
completa, ya aislada, falló esperando «Explorar asociaciones» en
`AssociationsPage.test.tsx:29`, caso «ranks candidates, draws the matrix and
inspects a selected pair» (189 aprobadas, 1 fallida).

Se limitó el paralelismo del comando Vitest en CI a `--maxWorkers=2`, sin
modificar sus 190 pruebas ni sus tiempos de espera. La suite completa con ese
comando pasó las 190 pruebas. Es una medida de control de recursos para el
runner, no una demostración causal del origen de los timeouts anteriores;
ambos fallos se mantienen registrados. No se configuraron reintentos automáticos.

### Bloqueo local de Chromium

La instalación del navegador terminó correctamente. Playwright inició uvicorn y
Vite, superó las esperas de disponibilidad y enumeró los 16 casos con un worker.
Los 16 fallaron al crear el navegador con `browserType.launch: spawn UNKNOWN`,
intentando ejecutar
`C:\Users\diego\AppData\Local\ms-playwright\chromium-1248\chrome-win64\chrome.exe`.
La ejecución tuvo permisos ampliados para procesos/red; no se conoce una causa
más específica del rechazo de lanzamiento en este Windows. No se atribuye a un
fallo funcional de los 16 casos, ni se declaran aprobados.

Se comprobó la generación de `frontend/playwright-report/index.html`,
`frontend/test-results/e2e.xml` y 16 trazas `trace.zip`. No hay capturas de página
porque el navegador no llegó a abrirse. El log está en
`.pytest_cache/aud007-e2e.log`. Esta ejecución verifica la configuración y los
diagnósticos del fallo, pero no el recorrido funcional E2E. No se sustituyó
Chromium por Edge ni se omitieron casos para obtener un resultado verde.

## Conservación del árbol local

La revisión final de `git diff`, `git diff --check` y `git status --short`
conserva las seis modificaciones previas: `.env.example`, `.gitignore`,
`app/api/main.py`, `app/shared/config/settings.py`,
`tests/integration/test_production_api_guards.py` y
`tests/unit/test_deployment_settings.py`. AUD-007 no editó esos archivos.
También permanecen los nueve paths inicialmente no seguidos (incluidos los
directorios `docs/benchmarks` y `scripts/diagnostics`, con sus contenidos).
No se usó reset, restauración ni limpieza destructiva; tampoco se modificaron
`pyproject.toml`, `uv.lock`, `frontend/package.json` o `frontend/package-lock.json`.

## Entorno y validación pendiente

Los primeros intentos restringidos encontraron DNS inaccesible para GitHub y
acceso denegado al caché de intérpretes de uv. La instalación y las comprobaciones
se repitieron fuera de ese aislamiento y pudieron ejecutarse. No se relajaron
reglas ni se modificaron dependencias para evitarlos.

Windows no demuestra la instalación de bibliotecas de Chromium en Ubuntu, las
cachés/artefactos de GitHub ni la ejecución de sus acciones. No hay Linux local
validado en esta sesión: no se encontró Docker y `wsl --list --quiet` falló con
«El sistema no tiene acceso al archivo». Actionlint verifica el workflow estáticamente, sin
ejecutar sus jobs. No se afirma que Actions esté aprobada.

Pasos pendientes para cerrar AUD-007:

1. Revisar los cambios y, cuando se autorice publicar, incorporarlos mediante PR
   a `develop`, sin incluir accidentalmente los cambios locales ajenos.
2. Verificar una ejecución real de todos los jobs en Ubuntu 24.04; registrar
   URL, SHA de la revisión y resultados de cada comprobación.
3. Revisar JUnit y diagnósticos de Playwright, incluidos los artefactos cuando
   falle una prueba; confirmar arranque local, Chromium Linux y cachés con locks.
   Si se repite localmente, resolver primero el error Windows de lanzamiento de
   Chromium; la instalación del navegador por sí sola no resolvió ese bloqueo.
4. Resolver los fallos backend/Ruff en sus tareas correspondientes y observar
   estabilidad de Vitest/E2E, conservando todas las comprobaciones obligatorias.
5. Declarar AUD-007 validada solo con evidencia remota de los criterios completos.
