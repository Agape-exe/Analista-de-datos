# AUD-042 — Identidad de dataset y reporte

Rama local: feat/aud-042-report-context. Parte de AUD-003 (1079701), sobre develop 0fd1dfd. No modifica backend, contratos HTTP, tipos generados, algoritmos ni almacenamiento de reportes.

## Comportamiento

El dataset activo procede exclusivamente de IntakeProvider. Recuperar un reporte no cambia el dataset ni atribuye al dataset activo las cifras del reporte recuperado.

ReportProvider expone:

- report: reporte visible, que puede ser generado, recuperado, histórico o anterior.
- reportIdentity.origin: generated o recovered.
- reportIdentity.datasetId: ID del perfil del reporte. Para una generación sin perfil se conserva el ID de la solicitud; en recuperaciones históricas sin perfil queda null.
- reportIdentity.matchesActiveDataset: true o false cuando ambos IDs están disponibles; null cuando no se puede verificar la relación.
- reportIdentity.previous y previousReason: identifica un resultado conservado durante una solicitud o después de un error de generación/consulta.
- compatibleReport: reporte con identidad coincidente con el dataset activo y sin solicitud posterior pendiente o fallida. Su status se conserva; cada consumidor debe distinguir SUCCESS, SKIPPED y FAILED antes de presentar hallazgos o indicadores.

No se comparan nombres de archivo, tamaños, cantidad de filas o nombres de columnas para deducir identidad. No se recupera el dataset en memoria a partir de un reporte guardado. Consultar reportes antiguos sigue disponible sin dataset activo.

## Errores y concurrencia

Mientras se regenera o recupera, un reporte anterior puede seguir visible, pero queda señalado y no se expone como compatibleReport. Si falla la solicitud HTTP, el aviso indica que se conserva un reporte anterior. Si el backend devuelve un nuevo reporte FAILED con HTTP 200, se muestra esa nueva ejecución fallida; no se conserva el éxito anterior como si fuera el resultado nuevo.

Una respuesta de generación que declara otro dataset, o una recuperación con otro run_id, se rechaza. Cambiar dataset o reiniciar aborta las solicitudes; se verifica además que la respuesta pertenezca a la solicitud vigente. El filtrado por contexto evita mostrar resultados anteriores antes de que se ejecute el efecto de cancelación.

IntakeProvider añade contextRevision, incrementada por reset. Permite limpiar un reporte histórico aunque el dataset activo ya fuera inexistente. No cambia el significado de dataset_id ni el DTO de intake.

La identidad y las marcas de vigencia pertenecen a la sesión; no alteran el objeto del reporte ni sus descargas JSON/Markdown. La navegación conserva tanto el reporte como su aviso de resultado anterior.

## Pruebas

- 10 pruebas de ReportProvider: identidad coincidente/distinta, reporte legado, reset sin dataset, regeneración fallida, recuperación fallida, IDs inesperados, respuestas tardías entre A/B, recuperación posterior al reset y reporte FAILED recibido con HTTP 200.
- 3 pruebas nuevas de pantalla: procedencia distinta, aviso de regeneración fallida e identidad histórica desconocida.
- E2E AUD-042 con backend real y Edge: carga A, genera reporte, carga B, recupera A, genera B, simula fallo HTTP de regeneración, navega, recupera sin dataset y reinicia. La muestra pequeña permite probar el contexto sin depender de una política estadística aún pendiente.

Validación local: 49 pruebas frontend aprobadas; ESLint y TypeScript/Vite build correctos; 24 pruebas de arquitectura aprobadas y checker correcto (167 archivos). La prueba E2E específica AUD-042 pasa. La suite E2E completa obtuvo 5 aprobadas y 2 fallidas: saturación de Asociaciones (AUD-004) e identidad aditiva ausente en Planner (AUD-001). El caso EDA/reporte que antes se detenía por saturación pasó en esta ejecución; eso no demuestra que AUD-004 esté resuelto. No se modifican ni se ocultan esas pruebas. El antecedente de AUD-003 está en aud-003-frontend-regressions.md.

Comandos: en frontend, npm.cmd test, npm.cmd run lint y npm.cmd run build. Para E2E, establecer PLAYWRIGHT_CHANNEL=msedge y ejecutar npm.cmd run test:e2e -- e2e/report-context.spec.ts. En la raíz, uv run python scripts/check_architecture.py y uv run python -m pytest tests/architecture -q.
