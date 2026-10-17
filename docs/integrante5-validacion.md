# Validación de la entrega del integrante 5

## Verificaciones ejecutadas

- uv sync --locked: dependencias instaladas sin cambiar uv.lock.
- uv run pytest -q: 95 pruebas aprobadas, incluidas las 76 de la base y las nuevas.
- uv run ruff check . y uv run ruff format --check .: aprobados.
- uv run python scripts/demo_integrante5.py: reporte finalizado y recuperado de SQLite.
- npm run generate:api: contratos TypeScript actualizados desde OpenAPI.
- npm run build: TypeScript y build de producción aprobados.
- npm test: 10 pruebas aprobadas en 3 archivos.
- npm run lint: aprobado.

## Cobertura relevante

Se verificó conservación de referencias, rechazo de evidencia inválida, estados
indeterminados, LLM limitado a priorizar IDs conocidos, aislamiento de métricas entre
corridas concurrentes, registro de fallos, reporte dentro del workflow, persistencia
entre reinicios, recuperación y descarga por API, límites de uploads, eliminación de
archivos temporales, matriz de detección, cobertura y abstenciones, consistencia,
evaluación humana y ejecución repetida con registros experimentales.

## Límite de verificación

Las pruebas Playwright de navegador no se completaron. Chromium no estaba disponible;
el intento de descarga produjo un archivo inválido. Se incluye una prueba e2e nueva
para upload, recuperación, descarga y ancho móvil, que deberá ejecutarse en un entorno
con Chromium instalado. No se afirma haber verificado visualmente esa prueba.

Para ejecutarla posteriormente desde frontend:

```powershell
npx playwright install chromium
npm run test:e2e
```

La compilación y las pruebas de interfaz con DOM simulado sí pasaron. La demo usa
fixtures explícitos y no constituye un benchmark estadístico real del sistema completo.

## Validación de la presentación de evidencia — 16/10/2026

Se mejoró la presentación de los resultados estadísticos en los insights,
conservando los valores recibidos y la clasificación del módulo crítico.

Verificaciones realizadas:
- Ruff: sin errores.
- Suite de backend: 149 pruebas aprobadas.
- Compatibilidad con los campos correlation y coefficient.
- Presentación de la variable de control en correlación parcial.
- Conservación de una correlación igual a cero.
- Conservación de la advertencia sobre ausencia de evidencia causal.

Estas pruebas verifican el comportamiento del software. No constituyen
una validación experimental del sistema multiagente completo.

Se cargó un CSV de prueba con 20 filas y 3 columnas.

- DataUnderstanding y Planner finalizaron con estado SUCCESS.
- Analysis y Critic quedaron en SKIPPED por estar pendientes
  de implementación en la versión probada.
- Insight quedó en SKIPPED por no recibir evidencia evaluada.
- Se recuperó el reporte mediante su run_id.
- Se descargó correctamente el informe en formato Markdown.
- El informe conservó las advertencias y no generó conclusiones
  sin evidencia ni métricas no calculadas.

Esta prueba verifica la consulta y exportación del reporte.
No valida el funcionamiento completo del sistema multiagente.

## Validación de integración con develop

- Backend: 189 pruebas aprobadas y Ruff sin errores.
- Prueba desde el frontend con prueba_correlacion.csv:
  DataUnderstanding, Planner y Analysis finalizaron en SUCCESS.
- Critic e Insight permanecieron en SKIPPED.
- El flujo completo todavía no está validado.

Incidencia detectada con prueba_api.csv:
Pearson y Spearman finalizaron correctamente, pero el ANOVA
falló porque cada producto tenía una sola observación.
Queda pendiente coordinar la validación del tamaño de los
grupos antes de planificar ANOVA.

## Integración de Critic con Analysis e Insight

- Backend: 210 pruebas aprobadas y Ruff sin errores.
- Se adaptó Critic para utilizar correlaciones exitosas
  recibidas en analysis_results.
- Se añadió compatibilidad con control_variable,
  conservando el soporte de control_variables.
- La prueba manual con prueba_critic.csv finalizó con
  las cinco etapas en SUCCESS.
- Pearson fue aproximadamente 0.9973, Spearman 0.9808
  y la correlación parcial fue -1.
- Critic registró un cambio de signo relevante.
- No se mostraron advertencias ni errores globales.

La prueba utiliza datos sintéticos. No valida los umbrales
del crítico ni demuestra causalidad o rendimiento general.