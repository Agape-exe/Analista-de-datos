# Multiagent Data Analyst

Base inicial en Python 3.12+ para un sistema multiagente de análisis de datos.
El objetivo es comprender datasets, planificar análisis, ejecutar herramientas
determinísticas, criticar evidencias y producir insights y reportes trazables.

**Estado: esqueleto arquitectónico, no producto analítico terminado.**

## Principios

- El LLM razona e interpreta; Python calcula.
- Los datasets completos permanecen locales y no se incluyen en el contexto LLM.
- Monolito modular con arquitectura hexagonal y contratos Pydantic.
- Fuentes, proveedores y persistencia se sustituyen mediante puertos.
- Las técnicas estadísticas son tools, no agentes.

## Arquitectura y módulos

| Módulo | Responsabilidad |
|---|---|
| `app/domain` | Modelos, enums e invariantes, sin infraestructura |
| `app/application` | DTO, configuración efectiva y caso de uso |
| `app/ports` | Protocols para agentes, fuentes, tools, LLM y workflow |
| `app/adapters` | CSV local, LLM desactivado y factorías SQLAlchemy |
| `app/agents` | DataUnderstanding, Planner, Analysis, Critic e Insight |
| `app/analytics` | Registry y espacios para tools determinísticas |
| `app/orchestration` | Estado serializable y grafo LangGraph |
| `app/evaluation` | Contratos experimentales y registro monotónico de tiempos |
| `app/config` | Settings y defaults TOML |
| `app/observability` | Logging con identificadores de ejecución |
| `app/api` | FastAPI y adaptación HTTP |
| `app/bootstrap.py` | Inyección de dependencias |

Detalles y límites de dependencia: [docs/architecture.md](docs/architecture.md).

## Flujo conceptual

```text
Data Understanding → Planner → Analysis → Critic
                                  ↑         │
                                  └─────────┤ falta evidencia
                                            ↓ evidencia suficiente
                                         Insight → Report
```

El grafo inicial implementa el recorrido lineal
`START → DataUnderstanding → Planner → Analysis → Critic → Insight → END`.
El ciclo del crítico y los análisis paralelos son extensiones futuras.

## Instalación

Desde la raíz del proyecto, con [uv](https://docs.astral.sh/uv/) instalado:

```powershell
uv sync --locked
```

Esto crea `.venv` y usa `uv.lock`. Para configurar opciones locales:

```powershell
Copy-Item .env.example .env
```

Alternativamente, Python 3.12+ permite instalar el paquete con pip en un entorno
virtual: `python -m pip install -e .`. Las herramientas de desarrollo y versiones
reproducibles se gestionan con `uv sync --locked`.

## Tests y calidad

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Las pruebas usan fixtures de tres filas, SQLite en memoria y HTTP local.
No requieren proveedor LLM, red ni datasets grandes.

## Levantar FastAPI

```powershell
uv run python run.py
```

Para desarrollo con recarga:

```powershell
uv run uvicorn app.api.main:app --reload
```

- API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`
- `GET /health`: `200 {"status": "ok"}`; indica liveness.
- `POST /analysis`: valida la entrada y devuelve **501** con
  `ANALYSIS_WORKFLOW_NOT_ENABLED`. Entrada inválida: **422**.
- Cada respuesta incluye `X-Request-ID` para correlación HTTP.

Ejemplo de cuerpo válido para `/analysis`:

```json
{
  "source": {"kind": "csv", "path": "tests/fixtures/sample.csv"},
  "schema": null,
  "data_dictionary": {
    "entries": [
      {"column_name": "age", "description": "Edad", "source": "manual", "unit": "años"}
    ]
  },
  "user_question": "¿Qué relaciones merecen analizarse?",
  "configuration": {"analysis": {"max_tool_calls": 3}}
}
```

La API todavía no lee esa ruta ni ejecuta el grafo.

## Configuración

Precedencia: defaults empaquetados < TOML externo opcional < `.env` < variables
de entorno < argumentos explícitos de Settings. Ejemplo:

```powershell
$env:MDA_ANALYSIS__MAX_TOOL_CALLS = "4"
```

Para TOML externo, usar `load_settings(Path(...))` y pasar el resultado a
`create_app(settings)` o `build_use_case(settings)`.

Los overrides por análisis solo permiten opciones de `analysis` y `performance`.
Los defaults fast son: 3 hipótesis, 8 tools, 1 ciclo crítico, muestra mínima 20,
timeout 15 segundos y `parallel_tools=true`.

El timeout se aplica al workflow skeleton. Los presupuestos, tamaño mínimo,
reintentos LLM, repeticiones y flag de paralelismo quedan preparados para sus
implementaciones futuras; no implican capacidades ya habilitadas.

## Ejecutar el skeleton desde Python

```python
import asyncio

from app.application.dto.analysis_input import AnalysisInput
from app.bootstrap import build_use_case
from app.config.settings import Settings


async def main() -> None:
    use_case = build_use_case(Settings())
    report = await use_case.execute(
        AnalysisInput(source={"kind": "csv", "path": "tests/fixtures/sample.csv"})
    )
    print(report.model_dump_json(indent=2))


asyncio.run(main())
```

Obtendrás `SKIPPED`, etapas omitidas explícitamente y tiempos reales de ejecución.
Resultados analíticos e insights estarán vacíos. El intake CSV funciona por
separado mediante `CsvDataSource.read`; aún no está conectado al grafo.

## Estado actual

Implementado: contratos de dominio, entrada CSV/TSV/TXT/SQL, diccionario estándar,
registry, cinco agentes invocables, grafo lineal, tiempos, trazabilidad, API mínima,
factorías SQLAlchemy y contratos de evaluación.

Pendiente: profiling y EDA, algoritmos estadísticos, LLM real y prompts, ejecución
de planes, critic loop, paralelismo, detección espuria, generación de insights,
renderizadores, repositorios concretos y evaluación experimental completa.

El registry de producción comienza vacío. `DisabledLLMProvider` lanza un error
comprensible si se intenta usar. No hay respuestas analíticas simuladas.

## Contribuir

- `main`: entregas estables.
- `develop`: integración del equipo.
- `feature/*`: desarrollo de capacidades.
- Prefijos de commit: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`.
- Pull requests pequeños, con typing, tests rápidos y Ruff correcto.
- Cambios de contratos requieren revisión compartida y coordinación entre módulos.
- No crear agentes por algoritmo; registrar tools con `AnalyticsTool`.
- Leer [Definition of Done](docs/definition-of-done.md) y
  [responsabilidades del equipo](docs/team-ownership.md).

Estas convenciones documentan el flujo de trabajo; el scaffolding no crea ramas
ni commits automáticamente.
