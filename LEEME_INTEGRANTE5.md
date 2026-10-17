# Implementación del integrante 5

Esta entrega implementa Insight Agent, reporting, persistencia, métricas e instrumentos
experimentales, API y una vista de reportes sobre el repositorio recibido.

## Comenzar en Windows

Descomprime el proyecto y abre una terminal en la carpeta que contiene `pyproject.toml`.
Necesitas Python 3.12 o superior y uv. Para la interfaz, Node 20.19 o superior.

```powershell
uv sync --locked
uv run pytest
uv run python scripts/demo_integrante5.py
```

La demo utiliza coeficientes y clasificaciones predefinidos, identificados como fixtures.
Sirve para probar tu módulo; no representa resultados estadísticos de una investigación.
Genera `report.json`, `report.md`, una rúbrica y un ejemplo de puntuación en
`experiments/integrante5-demo/`, además de una base local de demostración.

## Ejecutar API y conservar reportes

En una terminal desde la raíz:

```powershell
$env:MDA_PERSISTENCE__DATABASE_URL = "sqlite:///./analysis_reports.db"
uv run python run.py
```

Abre http://127.0.0.1:8000/docs y prueba `POST /analysis/upload` con tu CSV o TSV.
El archivo permanece disponible durante el flujo y se elimina al finalizar.
El reporte y su evidencia sí se guardan en SQLite. Copia el `run_id` para recuperarlo.
Sin la variable anterior, el valor original del repositorio usa SQLite en memoria;
los reportes de la API se perderán al reiniciar el proceso.

En otra terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Abre http://localhost:5173/report o pulsa Insights en el menú. Puedes generar un
reporte a partir de un archivo, recuperar otro por ID y descargar JSON o Markdown.
El encoding, separador y diccionario se seleccionan en New Analysis.

## Resultado esperado hoy

El flujo completo sigue devolviendo `SKIPPED` cuando las etapas de los compañeros
están pendientes. No se fabrican correlaciones, clasificaciones ni insights.
`FinalizeAnalysis` permite probar tu parte de forma independiente con resultados
precalculados suministrados por otros módulos. Su estado describe solamente la
finalización, identificado en `configuration.execution_scope`.

El agente usa explicaciones determinísticas con evidencia. Existe una extensión
opcional para que un LLM priorice insights existentes; no está conectado a un proveedor
real ni genera texto libre. No necesitas credenciales para probar esta entrega.

## Qué mostrar como avance

1. Ejecutar los tests y explicar las verificaciones de referencias y estados.
2. Ejecutar la demo y mostrar los vínculos Insight → Evidence → AnalysisResult.
3. Recuperar el reporte guardado y revisar el Markdown.
4. Subir un CSV real y mostrar las etapas implementadas y pendientes.
5. Presentar el protocolo de evaluación y la rúbrica; distinguir pruebas de software
   de validación experimental del sistema completo.

## Integrar con tu repositorio Git

Esta copia contiene la base completa para poder probarla. El archivo
`integrante5.patch` incluye solamente los cambios respecto del ZIP recibido.
En tu checkout original, crea una rama y copia ese patch a la raíz:

```powershell
git switch -c feature/integrante5
git apply --check integrante5.patch
git apply integrante5.patch
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

El comando `--check` verifica compatibilidad antes de aplicar. Si tus compañeros
ya cambiaron esos archivos, conserva sus avances y adapta los cambios usando la guía
`docs/integrante5-integracion.md`. No reemplaces el repositorio compartido entero.

La implementación no añade algoritmos de los integrantes 2, 3 o 4 ni modifica
el intake del integrante 1. Incluye conexiones pequeñas en contratos, API y el
ensamblado del reporte del workflow, necesarias para integrar tu módulo.

## Documentación incluida

- `docs/integrante5-integracion.md`: contratos y puntos de ajuste al recibir avances.
- `docs/integrante5-evaluacion.md`: métricas, ground truth, repetibilidad y rúbrica.
- `docs/integrante5-validacion.md`: pruebas ejecutadas y límites de verificación.
- `docs/integrante5-cambios.json`: inventario de archivos nuevos y modificados.
