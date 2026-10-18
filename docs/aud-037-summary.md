# AUD-037 — Resumen

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
