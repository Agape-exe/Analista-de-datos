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
