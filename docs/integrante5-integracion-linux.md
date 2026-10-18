# I5: comparación reproducible de los fallos de integración

## Revisiones y condiciones

Comparación realizada el 18 de octubre de 2026 mediante Actions real:
[39133154044](https://github.com/Alexander20L/Analista-de-datos/actions/runs/39133154044).
Workflow `I5 integration comparison`, evento `pull_request`, Ubuntu 24.04.

- Base: `develop`, `986acbf96da48fa33f3648fc933dd456c0298ea4`.
- Cabecera: `a15090357b9ae02e8321dce8010794874811b850`.
- [Job base](https://github.com/Alexander20L/Analista-de-datos/actions/runs/39133154044/job/117692260632): **failure**.
- [Job head](https://github.com/Alexander20L/Analista-de-datos/actions/runs/39133154044/job/117692260804): **failure**.

Cada job hizo checkout del SHA exacto de aplicación. Se copiaron desde la
cabecera únicamente `frontend/playwright.config.ts`, los dos tests
`associations.spec.ts` y `report.spec.ts`, y el observador `api-diagnostics.ts`.
El artefacto incluye `harness.patch` con las diferencias aplicadas a la base.
No se modificó código de aplicación en ninguno de los dos checkouts.

Las diferencias de tests respecto de develop son los selectores españoles y
la comprobación explícita de los seis agentes ya integrados en I5. Se conserva
la expectativa de `additive_identity`. La configuración común añade informes,
trazas y arranque determinista en desarrollo, SQLite en memoria y LLM
desactivado. El límite de archivo es **2.097.152 bytes**. No se sobrescriben las
cuotas: dos operaciones concurrentes, 60 solicitudes de exploración por 60 s,
20 uploads por 60 s y 120 solicitudes de reportes por 60 s.

Ambos jobs usan uv 0.13.1, Python 3.12, Node 24.18.0, los mismos locks,
Chromium de Playwright y un worker. Cada archivo inicia servidores nuevos;
los tres casos de reportes comparten el proceso de ese archivo. No hay
reintentos, esperas añadidas, mocks, límites aumentados ni aserciones relajadas.
El workflow de comparación se conserva en el commit `a150903` para reproducirlo;
se retira del diff final una vez obtenida la evidencia. La CI ordinaria sigue
ejecutando todos los tests con sus nueve jobs obligatorios.

## Resultados y causas

| Caso | Base | Cabecera | Evidencia y responsabilidad |
| --- | --- | --- | --- |
| `associations computed by the real backend are ranked and drawn` | Falla en línea 17 | Falla en línea 17 | `relationship_ranking` devuelve 429 `ANALYSIS_CAPACITY_EXCEEDED`; falta el ranking esperado. Transporte de Asociaciones y guarda de capacidad, AUD-004. |
| `EDA and a complete report coexist with recovery and downloads` | Falla en línea 50 | Falla en línea 50 | Mismo 429 de ranking al entrar inicialmente a Asociaciones, antes de generar el reporte. Mismos módulos que el caso anterior. |
| `default dated payments produce critical evidence and traceable insights` | Falla en línea 125 | Falla en línea 125 | POST de análisis responde 200, reporte SUCCESS, sin `additive_identity`; falla el acceso a `identity.result`. Planner/Analysis. |
| `member 5 report reuses the intake dataset and retrieves report` (control adicional) | Falla en línea 18 | Pasa | La base muestra «No hay insights…» y el test espera «No hay hallazgos…». Diferencia de presentación de I5, sin 429 en ese caso; no es uno de los tres fallos investigados. |

Totales de esta comparación acotada: base **0/4 aprobados**, cabecera
**1/4 aprobado**. Se revisaron ambos JUnit por job, logs, contextos y trazas;
no hay casos omitidos. No equivale a ejecutar la suite completa de develop.
Sí demuestra los tres fallos investigados en Linux sobre ambas aplicaciones,
con las adaptaciones del harness descritas arriba.

### Secuencia de capacidad

`AssociationsPage` solicita ranking y heatmap; `ColumnExplorer` solicita
histograma, boxplot y estadísticas descriptivas. `useTool` inicia cada fetch
de forma independiente. En el servidor Vite de desarrollo, `StrictMode`
monta, cancela y vuelve a ejecutar esos efectos: se observan dos tandas de
cinco POST y cancelaciones de la primera. Cancelar la espera del navegador no
es una confirmación de que el trabajo admitido por el servidor haya terminado.

El endpoint de Exploration reserva capacidad durante `use_case.run`.
`OperationCapacity.acquire` rechaza inmediatamente si ya hay dos operaciones
activas. `useTool` presenta el error y no reintenta automáticamente. No es
agotamiento de la cuota temporal de solicitudes: las respuestas identifican
`ANALYSIS_CAPACITY_EXCEEDED`, con `Retry-After: 1`, y no `REQUEST_RATE_LIMITED`.

Tiempos observados en `api-timeline`, relativos al inicio de cada test:

| Recorrido | Diez POST iniciales | Respuestas 429 de la segunda tanda |
| --- | --- | --- |
| Base, Asociaciones | 824,6–829,7 ms | boxplot 865,3 ms; estadísticas 875,2 ms; ranking 878,6 ms |
| Head, Asociaciones | 1012,4–1017,5 ms | estadísticas 1096,2 ms; heatmap 1098,6 ms; ranking 1099,6 ms |
| Base, EDA/reporte | 733,8–735,9 ms | heatmap 767,7 ms; ranking 782,8 ms |
| Head, EDA/reporte | 986,5–990,7 ms | ranking 1040,7 ms; boxplot 1043,1 ms; heatmap 1045,0 ms |

La herramienta concreta rechazada depende del solapamiento; no se garantiza
que el primer selector que falla sea siempre el mismo. Los archivos de
Asociaciones, `api-client.ts`, `main.tsx`, el endpoint y la guarda son idénticos
a develop. Esta comparación acredita la preexistencia que antes no estaba
demostrada, sin afirmar que toda posible interacción de navegación esté cubierta.

Dependencia concreta: el responsable de Asociaciones/AUD-004 debe coordinar
las solicitudes de herramientas y la cancelación para respetar la admisión
real del servidor. Su solución debe cubrir montaje, cambio de columna/par,
navegación y reset, manteniendo las dos plazas y los errores reales de otros
clientes. I5 no cambia ese transporte ni desactiva StrictMode para ocultarlo.

### Ausencia de identidad aditiva

En ambos lados, la traza confirma que el POST de análisis devuelve 200 y la
prueba alcanza la comprobación de `additive_identity` después de verificar
SUCCESS, seis etapas, evidencia e insights. La ausencia pertenece al reporte
producido, no a Métricas/Traza ni a una transformación de la descarga JSON.

La reproducción backend conocida es
`tests/integration/test_critic_pipeline.py::test_default_csv_produces_measured_critic_and_insights_without_a_question`.
El Planner genera candidatos de identidad de tres variables, pero su filtro
por screening conserva candidatos cuyos conjuntos de variables coinciden con
pares significativos, o que tengan prioridad por la pregunta. Sin pregunta,
una identidad de tres variables no coincide con un par. El equipo de
Planner/Analysis debe revisar esa política con sus presupuestos y pruebas;
no se modifica aquí el algoritmo ni se elimina la expectativa E2E.

## Instrumentación permanente y evidencia

`frontend/e2e/api-diagnostics.ts` añade un fixture automático, usado solo por
los dos archivos afectados. Observa eventos del navegador y adjunta
`api-timeline` con método, path, parámetros de herramientas, tiempos relativos,
status, Retry-After, errores HTTP y cancelaciones. No intercepta solicitudes,
no registra cuerpos de uploads y no altera su ejecución. Las trazas fallidas
incluyen el JSON como attachment; también está disponible en el informe HTML.

Artefactos de comparación: `i5-comparison-base` **12139056081** y
`i5-comparison-head` **12138656707**, descargados y revisados. Retención: siete
días. La descripción de secuencias y SHA en este documento perdura cuando
expiren; los logs y copias locales están en `.pytest_cache/i5-delivery-review`.

Corrección de precisión respecto de explicaciones anteriores: en la ejecución
`39130359385` / `33e7a62`, Asociaciones falló en el **histograma** (línea 20),
y EDA/reporte en la **primera entrada** a Asociaciones (línea 50). No se debe
atribuir a ese SHA el fallo de matriz o regreso desde Hallazgos observado en
otra ejecución. La causa HTTP era también capacidad, pero cambia la petición
rechazada por la carrera.

## Validación y pendientes

En esta continuación: checker AST aprobado (172 archivos), arquitectura
**24 aprobadas**, Vitest **213 aprobadas / 16 archivos** (49,45 s), ESLint de
los tres archivos E2E aprobado, descubrimiento Playwright **20 casos / 12
archivos**, actionlint aprobado y build TypeScript/Vite aprobado (1643 módulos).
Los primeros intentos restringidos de uv y build no accedieron al intérprete
o a `main.tsx` (EPERM); las repeticiones con acceso al entorno instalado pasaron.
La prueba backend de pagos se repitió y falló por `additive_identity` ausente.

CI completa de `a150903`:
[39133153991](https://github.com/Alexander20L/Analista-de-datos/actions/runs/39133153991),
workflow `CI`, `pull_request`, **failure**. Pasan Vitest, ESLint, build,
checker, arquitectura y Ruff format. Fallan pytest, Ruff check y Chromium
Linux: pytest **598 aprobadas / 4 fallidas**, Ruff **F841/F401**, E2E
**17 aprobadas / 3 fallidas**, incluidos Métricas **2/2** y Traza **2/2**
aprobados. El estado de la cabecera posterior que documenta esta evidencia se
verifica y registra en el [PR #41](https://github.com/Alexander20L/Analista-de-datos/pull/41).

No se ha encontrado una nueva regresión funcional atribuible a I5 en los tres
fallos investigados. Permanecen dependencias de Asociaciones/AUD-004 y
Planner/Analysis, además de los cuatro pytest y dos errores Ruff documentados
en la entrega. AUD-007 no está aprobado mientras los jobs obligatorios fallen.
El PR permanece en borrador. No se hace merge ni despliegue; Render sigue
pendiente de mediciones del staging desplegado. El checkout original y sus
cambios locales de Render permanecen fuera del PR.

La verificación SHA-256 final de esta continuación conserva **48/48 archivos
locales originales**, sin cambios, y el índice original está vacío. El diff
final añade al inventario anterior solo `api-diagnostics.ts`, la activación
del observador en `associations.spec.ts` y este documento; `report.spec.ts` y
los tres documentos de I5 existentes se actualizan dentro del mismo alcance.
No hay diferencias backend, contratos, locks ni límites respecto de la base.

## Comparación posterior a AUD-039 y PR #49

La base vigente pasó a `896f5834c44628c79a53d06a53c4a86b82557d40`.
El merge local del PR #41 es `a54a6ab`; la punta funcional antes de actualizar
documentación es `89e62bc`. Ya están disponibles el catálogo y endpoint de
consultas fundamentadas, procedencia de screening y Relaciones.

En Windows, las 16 E2E seleccionadas de Resumen, Reporte, contexto, navegación,
Métricas, Traza, Asociaciones, Patrones, Anomalías, Relaciones y Chat iniciaron
Uvicorn/Vite, pero Chromium 1248 falló en cada caso con `spawn UNKNOWN` antes de
la primera aserción. Este resultado solo valida descubrimiento/configuración;
no sustituye Linux.

La comparación Linux definitiva se ejecutará mediante el workflow CI del PR,
que aísla cada archivo E2E en un proceso nuevo. Hasta registrar esa URL y sus
jobs, AUD-007 y AUD-046 permanecen pendientes. No hubo cambios de límites,
reintentos, locks, despliegue ni configuración de Render.
