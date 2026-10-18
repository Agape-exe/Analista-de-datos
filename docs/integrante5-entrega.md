# Revisión de entrega I5 — AUD-007, Métricas y Traza

Revisión del 18 de octubre de 2026. **Preparada para revisión; no aprobada**.
Actions y Playwright Linux requieren evidencia remota del SHA del PR; los fallos
obligatorios no se excluyen. Render continúa pendiente de medición del staging
desplegado. No se ejecuta ningún despliegue.

## Base y atribución

- Base remota verificada mediante fetch y ls-remote: `develop`,
  `986acbf96da48fa33f3648fc933dd456c0298ea4`. La rama local `develop`, más
  antigua, se conserva sin moverla. `main` es la rama predeterminada del remoto,
  pero no es la base solicitada del PR.
- Árbol original: `codex/aud-007-ci`,
  `adcd0ec4e7e96dc1e4b84cf792e3612a91ca23ea`, con índice vacío y cambios locales.
- Rama de entrega: `codex/i5-aud007-metricas-traza`, en el worktree
  `.pytest_cache/i5-delivery`. El checkout original permanece intacto.

Los cinco commits anteriores sobre develop son de Diego y se corresponden con
la documentación I5 y sus pruebas. Se incluyen como dependencias integradas del
contexto y navegación que consumen Métricas/Traza, incluido el Resumen existente:

| Commit | Contenido revisado |
| --- | --- |
| `532032c` | AUD-003: regresiones públicas de Hallazgos, español y seis agentes. |
| `aae4011` | AUD-042: identidad independiente del dataset y reporte histórico. |
| `6225d6d` | AUD-045: navegación, cancelación y reset del contexto. |
| `ed1c91e` | AUD-037: Resumen que consume ese mismo contexto. |
| `adcd0ec` | Adaptación de Resumen/contexto a los contratos actuales de develop. |

Los cambios sin commit de AUD-007 se atribuyen por su inventario en
`aud-007-ci.md`: workflow, configuración Playwright, documento y enlace desde
AUD-037. El inventario de `integrante5-metricas.md`, los fixtures y el contenido
de App/Sidebar/ReportPage atribuyen Métricas y Traza. No se incorporan ramas de
otros autores ni los cambios de capacidad/Render. No se certifica la autoría
personal de los cambios locales de Render: su contenido y sus documentos
permiten separarlos funcionalmente, y todos se conservan fuera del PR.

## Revisión de implementación

Ambas pantallas leen el ReportProvider existente; reutilizan el objeto completo
de GET /reports/{run_id} o POST /analysis/datasets/{dataset_id}. No hay nuevas
peticiones de métricas, persistencia, algoritmos ni contratos. La identidad del
dataset activo se presenta separada de la del reporte. Reset usa la revisión de
contexto y la identidad de solicitud, incluso si una respuesta ignora abort.

Se revisaron SUCCESS/SKIPPED/FAILED, ausencias, ceros, estados parciales,
históricos sin perfil, sustitución, espera y fallos de red. Las llamadas de Traza
conservan el orden recibido y sus detalles JSON; no se inventan transiciones,
timestamps, vínculo con etapas ni un tiempo total. Los mapas de etapas son
independientes y se presenta su unión, con unidades en segundos.

Corrección atribuible a I5: Métricas ocultaba duraciones sin estado. Una prueba
reprodujo la omisión antes del cambio (10 aprobadas, 1 fallida); la unión de
claves ahora conserva esos datos y representa el estado ausente explícitamente.
Se habilitan únicamente las rutas de las pantallas ya integradas.

Se detectó además una dependencia accidental de AUD-007 con los cambios locales
de Render: Playwright establecía `MDA_DEPLOYMENT__RESOURCE_PROFILE=standard`,
propiedad que develop no admite. La primera E2E aislada falló al arrancar Uvicorn
por `deployment.resource_profile: extra_forbidden`. Se retiró únicamente ese
override de la configuración E2E. No se incorporó la configuración Render al PR.

`git diff develop -- app tests pyproject.toml uv.lock scripts/check_architecture.py`
no presenta diferencias. Se preservan la arquitectura modular, los reportes
públicos y el límite de archivo **2 MiB (2.097.152 bytes)**. El backend E2E fija
ese mismo límite. No se restauran capas globales ni se modifican algoritmos.

## Comprobaciones locales de esta revisión

En el worktree aislado, con los locks existentes y sin artefactos ajenos:

| Comando | Resultado real |
| --- | --- |
| `uv sync --locked --group dev --python 3.12` | Correcto, Python 3.12.15; entorno nuevo. |
| `npm ci` (frontend) | Correcto, 303 paquetes, sin cambios al lock. |
| `uv run --locked python scripts/check_architecture.py` | Correcto, 172 archivos Python; se excluye del PR el upload_guard local de Render. |
| `uv run --locked pytest tests/architecture -q` | 24 aprobadas, 2,66 s. |
| `uv run --locked pytest -q` | 598 aprobadas, 4 fallidas, 39,93 s. |
| `uv run --locked pytest tests/unit/test_telemetry.py tests/integration/test_graph.py tests/integration/test_insight_workflow.py tests/integration/test_reporting_api.py tests/integration/test_member5_finalization.py -q` | 15 aprobadas, 1,73 s. |
| `uv run --locked ruff check .` | 2 errores: F841 analysis_planning.py:273 y F401 test_planner_agent.py:10. |
| `uv run --locked ruff format --check .` | Correcto, 272 archivos. |
| `npm test -- --maxWorkers=2 --reporter=default --reporter=junit --outputFile=../.pytest_cache/review/vitest.xml` | 213 aprobadas, 16 archivos, 60,69 s. |
| `npm run lint` | Correcto sobre el árbol de entrega completo; sin nuevas exclusiones. |
| `npm run build` | Correcto, TypeScript/Vite, 1643 módulos. |
| `actionlint 1.7.12 .github/workflows/ci.yml` | Correcto; binario oficial verificado por SHA-256. |
| `npm exec --no -- playwright install chromium` | Correcto; no demuestra ejecución del navegador. |
| `CI=true PLAYWRIGHT_CHANNEL=chromium npm run test:e2e -- --reporter=list,html,junit --output=../.pytest_cache/review/e2e-repeat-results` | 20 fallidas antes de aserciones por `browserType.launch: spawn UNKNOWN` en Windows. Tras corregir el override, Uvicorn/Vite arrancan. No valida recorridos. |
| `git diff --cached --check` | Correcto. |

Los cuatro fallos son los siguientes. Se ejecutaron también, sin modificar,
contra el checkout `986acbf` en `.pytest_cache/i5-base`: **4 fallidas**, 4,54 s,
con los mismos motivos. Se comprobó que `app.__file__` resolvía ese checkout.
Ruff en esa base reprodujo exactamente los mismos dos errores. La ausencia de
diff backend confirma además que no se cambiaron sus productores ni pruebas.

- `test_anova_planning.py::test_fast_mode_uses_next_valid_anova_after_omitting_sparse_pair`.
- `test_critic_pipeline.py::test_default_csv_produces_measured_critic_and_insights_without_a_question`.
- `test_critic.py::test_critic_reports_significant_results_without_robustness_as_preliminary`.
- `test_critic.py::test_critic_skips_when_no_result_is_significant`.

No se corrigen algoritmos de otros integrantes para ocultar esos fallos. Las
nueve comprobaciones de CI permanecen obligatorias, sin omisiones, exclusiones,
reintentos ni continue-on-error. Los informes nuevos se guardan en
`.pytest_cache/i5-delivery/.pytest_cache/review/`; no se sobrescriben los informes
originales de AUD-007, Métricas o Traza. La primera E2E se conserva en `e2e.log`
(fallo de configuración); la repetición en `e2e-repeat.log`, JUnit, HTML y veinte
trazas en `e2e-repeat-results`. No se atribuye el fallo de lanzamiento Windows a
un fallo funcional, ni se sustituye Chromium por otro navegador.

## Conservación del espacio de trabajo

Antes de crear los worktrees se guardaron el diff binario, estado del índice y
SHA-256 de los 48 archivos modificados/no seguidos del árbol original en
`.pytest_cache/i5-delivery-review/original*`. Los archivos de I5 se copiaron
explícitamente al worktree; las correcciones y documentación nuevas pertenecen
solo a la rama de entrega. El diff original y los archivos locales siguen
disponibles en `codex/aud-007-ci`.

Fuera del PR permanecen `.env.example`, `.gitignore`, `app/api/main.py`,
`app/shared/config/settings.py`, `app/shared/adapters/http/upload_guard.py`,
`tests/integration/test_production_api_guards.py`,
`tests/unit/test_deployment_settings.py`,
`tests/integration/test_staging_fixture_contract.py`,
`tests/unit/test_staging_capacity.py`, `tests/unit/test_upload_admission.py`,
todo `docs/benchmarks/` y `scripts/diagnostics/`,
`docs/large-dataset-diagnosis.md`, `docs/render-free-staging-validation.md` y
`docs/render-free-upload-protection.md`. No se alteran ni se borran estos paths.
Tampoco se incorporan las ramas ajenas, incluida la actualización remota de
`feature/critic-relations-queries` observada durante fetch.

## Diff revisado archivo por archivo

37 archivos sobre la base remota; se incluyen los prerequisitos I5 indicados
arriba. Los documentos conservan las validaciones anteriores como historial,
sin presentarlas como evidencia de esta revisión.

| Archivo | Revisión y pertenencia a I5 |
| --- | --- |
| `.github/workflows/ci.yml` | Nueve comprobaciones independientes; Ubuntu/Chromium, locks y artefactos; sin despliegue ni tolerancia a fallos. |
| `docs/aud-003-frontend-regressions.md` | Evidencia histórica de adaptación de los consumidores de reportes. |
| `docs/aud-007-ci.md` | Configuración, resultados iniciales y enlace al estado actual. |
| `docs/aud-037-summary.md` | Resumen integrado y enlace AUD-007; no incluye evidencias Render. |
| `docs/aud-042-report-context.md` | Contrato de identidad y contexto compartido requerido por ambas vistas. |
| `docs/aud-045-context-navigation.md` | Persistencia en navegación, cancelación y reset. |
| `docs/integrante5-entrega.md` | Alcance, atribución, inventario y resultados de esta revisión. |
| `docs/integrante5-metricas.md` | Semántica de métricas/traza, contratos y corrección de mapas parciales. |
| `frontend/e2e/metrics.spec.ts` | Mediciones HTTP reales, identidad, navegación, móvil y respuesta tardía. |
| `frontend/e2e/navigation-context.spec.ts` | Formularios conservados, cancelación de intake y reset; sin rebajar expectativas. |
| `frontend/e2e/report-context.spec.ts` | Reporte de otro dataset, recuperación, regeneración fallida y reset. |
| `frontend/e2e/report.spec.ts` | Selectores españoles y seis etapas exactas del contrato real. |
| `frontend/e2e/summary.spec.ts` | Resumen sin consultas adicionales, histórico separado y anchos 1440/390. |
| `frontend/e2e/trace.spec.ts` | Llamadas y mapas contrastados con HTTP, navegación y reset tardío. |
| `frontend/playwright.config.ts` | Servicios locales aislados, límite 2097152; retirado override propio de Render no disponible en develop. |
| `frontend/src/app/App.tsx` | Providers compartidos y rutas de Resumen/Métricas/Traza integradas. |
| `frontend/src/app/NavigationContext.test.tsx` | Carreras, cancelación, borradores y reset con rutas/providers reales. |
| `frontend/src/components/layout/DatasetHeader.tsx` | Permite reset durante intake pendiente. |
| `frontend/src/components/layout/Sidebar.tsx` | Menú de pantallas integradas, navegación accesible y reset explícito. |
| `frontend/src/features/data-intake/IntakeProvider.tsx` | Revisión de contexto, cancelación y guardas contra respuestas anteriores. |
| `frontend/src/features/data-intake/NewAnalysisPage.tsx` | Cancelar espera, limpiar inputs nativos y evitar redirección tras salir. |
| `frontend/src/features/metrics/MetricsPage.test.tsx` | Once casos, incluido tiempo de etapa sin estado. |
| `frontend/src/features/metrics/MetricsPage.tsx` | 23 mediciones recibidas, procedencia, errores y unión de mapas parciales. |
| `frontend/src/features/metrics/metric-fields.ts` | Campos exhaustivos respecto al tipo HTTP generado y unidades originales. |
| `frontend/src/features/reports/ReportContextCard.tsx` | Extracción fiel de la procedencia existente, compartida por las tres vistas. |
| `frontend/src/features/reports/ReportPage.test.tsx` | Compatibilidad de Hallazgos, seis agentes y reportes históricos/anteriores. |
| `frontend/src/features/reports/ReportPage.tsx` | Usa la tarjeta compartida y el contexto; no cambia cálculos ni formato de descarga. |
| `frontend/src/features/reports/ReportProvider.test.tsx` | Diez casos de identidad, recuperación, fallo, reemplazo y respuesta tardía. |
| `frontend/src/features/reports/ReportProvider.tsx` | Una fuente de verdad; valida run/dataset y conserva origen explícito. |
| `frontend/src/features/summary/SummaryPage.test.tsx` | Indicadores compatibles, ausencia, navegación y reset. |
| `frontend/src/features/summary/SummaryPage.tsx` | Consumidor previo integrado del mismo contexto; no calcula estadísticas. |
| `frontend/src/features/trace/TracePage.test.tsx` | Doce casos de contrato abierto, parciales, carga/error, sustitución y reset. |
| `frontend/src/features/trace/TracePage.tsx` | Conserva llamadas y mapas independientes; no reconstruye eventos. |
| `frontend/src/features/trace/trace.css` | Desplazamiento accesible y detalles JSON adaptables. |
| `frontend/src/styles/globals.css` | Estilos acotados a Resumen, prerequisito I5 existente. |
| `frontend/src/test/report-fixture.ts` | Fixture tipado con cero y ausencias explícitas. |
| `frontend/src/test/trace-fixture.ts` | Formas reales de telemetría; sin timestamps o enlaces inventados. |

## Publicación y evidencia remota

Pendiente de registrar el PR y la consulta real de Actions para su SHA. Ningún
resultado local de esta tabla acredita GitHub Actions o Chromium Linux.
Render permanece **pendiente**: no hay medición nueva del staging desplegado
y no se realizó despliegue.
