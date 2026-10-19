# AUD-045 — Contexto, navegación y cancelación

Rama local feat/aud-045-context-navigation, construida sobre AUD-042 (c5711f5) y AUD-003. Sin cambios de backend, algoritmos, dependencias, contratos HTTP o despliegue.

## Navegación y conservación

El logo usa navegación interna de React Router: volver al inicio no recarga la aplicación ni descarta el dataset, el reporte o los borradores. El archivo/diccionario y sus opciones continúan en IntakeProvider. La pregunta y el ID escrito para recuperar un reporte pasan a ReportProvider, asociados al contexto de AUD-042; sobreviven al cambio de pantalla y se limpian al cambiar dataset o reiniciar.

Completar una ingesta iniciada en otra pantalla actualiza el contexto compartido, pero no redirige al usuario desde la pantalla que eligió después. No se incorpora almacenamiento persistente en el navegador; recargar la aplicación sigue iniciando una sesión vacía, con recuperación por run_id disponible.

Nuevo análisis permanece disponible durante solicitudes pendientes. Reinicia el contexto, aborta la espera, limpia datos/formularios/errores/reportes y remonta el formulario para vaciar también los inputs nativos de archivos. Ninguna respuesta tardía puede restaurar el contexto descartado o terminar el indicador de carga de un reintento nuevo.

## Cancelación

La carga ofrece Cancelar espera de carga y conserva los archivos y opciones para reintentar. El reporte ofrece Cancelar espera del reporte durante generación y recuperación. La pregunta y la consulta se conservan; un reporte anterior queda identificado como anterior y no vuelve a ser compatibleReport. Si no hay reporte previo se muestra un aviso de cancelación.

Cancelar detiene la espera del navegador; no se afirma que detenga un cálculo ya iniciado en el servidor. No existe un endpoint de cancelación de trabajo remoto en esta entrega. No se aumentan límites ni se añaden reintentos automáticos que puedan provocar trabajo duplicado.

## Alcance entre integrantes

Se mantienen las rutas disponibles: Nuevo análisis, Dataset, Diccionario, Asociaciones y Hallazgos. Las pantallas aún pendientes de los compañeros siguen deshabilitadas; se registrarán al recibir implementaciones utilizables. No se modifican Asociaciones, sus cálculos ni su transporte (AUD-004/005), ni se implementan Resumen, Métricas o Chat dentro de AUD-045.

## Validación local

- 56 pruebas frontend aprobadas (7 nuevas de navegación/contexto), incluidas las de identidad AUD-042.
- ESLint y build TypeScript/Vite correctos.
- 5 E2E seleccionados con Edge: diccionario, intake, identidad del reporte y 2 nuevos de AUD-045. Todos aprobados.
- Los E2E nuevos usan backend real para carga, análisis de muestra insuficiente y recuperación del contexto. La cancelación de la carga se prueba reteniendo esa petición y luego reintentando contra el backend real.
- Las pruebas unitarias cubren cancelación, borradores, reinicio en vuelo, respuestas tardías y ausencia de redirección al completar una carga fuera de su pantalla.
- Checker de arquitectura: correcto, 167 archivos. Pruebas de arquitectura: 24 aprobadas.
- git diff --check correcto.

Durante una ejecución simultánea con Playwright hubo un timeout de 5 segundos en una prueba unitaria de Asociaciones. La suite completa se repitió sola y aprobó las 56 pruebas, sin modificar esa prueba ni sus tiempos. No se repitió la suite E2E global: los fallos de saturación de Asociaciones y selección de identidad aditiva documentados en AUD-003/042 siguen fuera de este alcance; esta entrega no los declara resueltos.

Comandos: npm.cmd test; npm.cmd run lint; npm.cmd run build. Con PLAYWRIGHT_CHANNEL=msedge: npm.cmd run test:e2e -- e2e/navigation-context.spec.ts e2e/report-context.spec.ts e2e/dictionary.spec.ts e2e/intake.spec.ts. Desde la raíz: uv run python scripts/check_architecture.py y uv run python -m pytest tests/architecture -q.
