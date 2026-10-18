# AUD-037 — Resumen

## Adaptación a develop del 18 de octubre de 2026

Se consultaron de nuevo las referencias reales de GitHub. `develop` avanzó a
`986acbf` (PR #39, AUD-018: posiciones originales de ejemplos IQR); `main` está
en `914065b` tras el PR #40. Los PR #34, #36 y #37 de preview/calidad ya forman
parte de esa base. La rama `feature/critic-relations-queries` tiene tres commits
propios (AUD-002, AUD-033, AUD-034), todavía fuera de develop: no se incorporó ni
se dan por cumplidas las dependencias de Hallazgos/Chat.

La rama local `feat/aud-037-develop-adaptation` parte de `origin/develop` en
`986acbf`. Se reaplicaron los cuatro commits propios mediante cherry-pick,
sin merge, y se conservaron las ramas originales:

| Avance | Commit original | Commit reaplicado |
| --- | --- | --- |
| AUD-003 | 1079701 | 532032c |
| AUD-042 | c5711f5 | aae4011 |
| AUD-045 | c14c2a3 | 6225d6d |
| AUD-037 | b5c994a | ed1c91e |

Resumen reutiliza ahora la tarjeta «Controles de calidad / Disponibles» del
componente remoto DatasetMetrics y ofrece «Ver calidad de datos». No inventa
un puntaje global ni consulta calidad automáticamente. Preview y calidad se
solicitan solo al visitar las pantallas que los poseen. Se actualizaron las
pruebas propias para distinguir esas solicitudes de las de análisis y para
verificar el recorrido Resumen → Calidad → Resumen sin perder contexto ni
producir solicitudes adicionales al regresar.
Se ajustó la tipografía móvil de sus tarjetas para que el nuevo texto
«Disponibles» de calidad se lea completo en la columna de indicadores.

El código backend y sus pruebas permanecen idénticos a origin/develop. No se
alteraron los algoritmos de calidad, IQR, planificación ni Critic. Las secciones
siguientes conservan la base y validación de la primera entrega como historial.

Validación de esta adaptación:

- 190 pruebas frontend aprobadas (14 archivos), sin excluir suites.
- ESLint y build TypeScript/Vite correctos.
- 10 E2E Edge aprobados: summary, navigation-context, report-context,
  dataset-preview, quality y outlier-row-references. El recorrido desde Resumen
  consulta calidad al entrar en su pantalla y no añade solicitudes al volver.
  Resumen conserva el diseño sin desbordamiento horizontal a 390 px.
- Checker de arquitectura correcto: 172 archivos Python.
- 154 pruebas aprobadas: tests/architecture, tests/unit/test_dataset_quality.py,
  tests/integration/test_dataset_quality_api.py,
  tests/unit/test_outlier_row_references.py y
  tests/integration/test_outlier_row_references_api.py.
- La primera ejecución tras reaplicar commits encontró tres incompatibilidades
  de pruebas propias: expectativa del puntaje de calidad retirado y mocks que
  contaban preview como ejecución de análisis. Se adaptaron a las rutas reales.
- Una ejecución simultánea con pytest agotó dos esperas de navegación en
  App.test.tsx y AssociationsPage.test.tsx. La suite completa repetida sola pasó
  las 190 pruebas, sin cambiar plazos, aserciones ni el código de esas suites.
- Los fallos integrales previamente documentados no se consideran resueltos por
  estos checks; no se ejecutó la suite backend completa ni se incorporó Critic
  desde su rama pendiente.

## Base local y GitHub

Se revisaron AGENTS.md, docs/architecture.md, el árbol de trabajo y las referencias
remotas antes de editar. El árbol estaba limpio en
`feat/aud-045-context-navigation`, commit `c14c2a3`, sobre los avances locales
`1079701` y `c5711f5`. Se creó `feat/aud-037-summary` desde ese commit.

La consulta real a GitHub encontró `develop` en
`29d5ae78895da52c328714291a3bb4e3404eb2ec`, posterior a `0fd1dfd`:
PR #34 (preview del dataset), #36 (calidad backend) y #37 (pantalla de calidad).
Se actualizó origin/develop mediante fetch para compararlos. No se mezclaron
estos cambios con la rama local ni se publicó ningún cambio.

## Comportamiento

- `/summary` habilita Resumen en Sidebar. `/` sigue siendo Nuevo análisis.
- IntakeProvider es la fuente del dataset activo. DatasetMetrics reutiliza los
  indicadores de ingesta, incluida la calidad no evaluada.
- ReportProvider decide compatibilidad e identidad. Solo un compatibleReport con
  estado SUCCESS aporta indicadores de análisis: cantidad de hallazgos y
  evidencias presentes, tiempo total y llamadas a herramientas ya registrados.
- Las cantidades de colecciones ausentes y las métricas null/ausentes se muestran
  como «— / Sin medición disponible». Un cero presente se conserva como cero.
- FAILED y SKIPPED muestran su estado y el acceso a Hallazgos sin presentar sus
  indicadores como un análisis completado.
- Reportes de otro dataset, sin identidad, históricos sin dataset activo y
  reportes anteriores permanecen en un bloque de procedencia separado. Sus
  indicadores no se atribuyen al dataset activo.
- Se muestran carga/consulta pendiente, error, expiración y cancelación según los
  proveedores. Cancelar la espera no afirma detener el cálculo en el servidor.
- Navegar conserva contexto; Nuevo análisis usa el reset existente y vuelve a `/`.
- No se añadieron endpoints, contratos, estadísticas en React ni solicitudes para
  renderizar Resumen. Los accesos llevan a las pantallas disponibles en esta base.

## Validación

- 67 pruebas frontend aprobadas, incluidas 11 nuevas con proveedores reales y
  transporte simulado: sin dataset, ingesta, compatibilidad, históricos,
  FAILED/SKIPPED, solicitudes pendientes, error, cancelación, navegación y reset.
- ESLint y build TypeScript/Vite correctos.
- Checker: 167 archivos Python, límites modulares respetados.
- Arquitectura: 24 pruebas aprobadas.
- Edge: 4 E2E aprobados (summary.spec.ts, los dos navigation-context.spec.ts
  y report-context.spec.ts). Ingesta y generación SKIPPED usan el backend real;
  el histórico de otro dataset usa una respuesta simulada explícita.
  Resumen no produjo solicitudes adicionales al entrar desde Dataset.
  Se verificó ausencia de desbordamiento horizontal a 390 px y se capturaron
  vistas completas de escritorio y móvil para revisión visual.
- Los primeros intentos restringidos no ejecutaron las pruebas por EPERM en
  setup.ts y acceso denegado al intérprete Python. Se repitieron con ejecución
  elevada. Durante el desarrollo se corrigió el arnés de pruebas para seleccionar
  un archivo antes de invocar ingesta y una opción de selector incompatible con
  Testing Library; no se rebajaron comprobaciones.

No se modificaron algoritmos backend. Los fallos ajenos documentados en el
traspaso (AUD-001, AUD-002, AUD-004 y AUD-006) no se declaran resueltos; esta
validación no sustituye la suite integral pendiente del equipo.

## Preparación de AUD-007

Siguiente bloque: preparar integración continua en una rama propia, considerando
también el avance remoto de develop antes de publicar. Debe ejecutar instalación
con locks, checker y pruebas de arquitectura, suite backend completa y Ruff,
además de npm ci, Vitest, ESLint, build y Playwright. En Linux, instalar Chromium
y sus dependencias en lugar de exigir Edge. Ejecutar ESLint antes de Playwright
para evitar la recreación concurrente de test-results.

Los fallos existentes deben quedar visibles: no usar exclusiones, xfail ni
continue-on-error para declarar verde el flujo. Guardar resultados y trazas de
fallos E2E y separar jobs para identificar backend, arquitectura y frontend.
No activar despliegue ni publicar secretos/datasets/bases locales. Un workflow
preparado localmente requiere ejecución real en GitHub antes de afirmar que CI
está validada. No hay autorización para push, PR ni merge; las futuras
publicaciones solicitadas deben dirigirse a develop.
