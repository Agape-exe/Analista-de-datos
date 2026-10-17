# Responsabilidades iniciales del equipo

Todos trabajan sobre el mismo monolito modular y los mismos contratos.

## Integrante 1 — Data Intake & Understanding

- Datasource y adaptadores de entrada.
- Validación y esquema.
- Data dictionary.
- DataUnderstandingAgent.

## Integrante 2 — EDA & Association

- Profiling.
- Correlation y association.
- Tools estadísticas iniciales, coordinadas con integrante 3.
- Visualization.

## Integrante 3 — Planner & Analysis

- PlannerAgent y AnalysisAgent.
- Tool registry.
- Analytics execution.
- Orchestration y critic loop en coordinación con integrante 4.

## Integrante 4 — Critic & Spurious Detection

- CriticAgent.
- Evidence.
- Relationship assessment.
- Robustness analysis.

## Integrante 5 — Insight, Evaluation & API

- InsightAgent.
- Reporting.
- Metrics y evaluation.
- Experiment logger.
- API.
- Integration support.

## Responsabilidad compartida

`domain/models`, enums, DTO y contratos de `ports` son responsabilidad compartida.
Cambios incompatibles requieren coordinación con los módulos consumidores y
revisión cruzada. Cada integrante entrega capacidades conectables al flujo común,
con tests y documentación; ownership no implica sistemas o repositorios separados.

Antes de integrar: seguir [Definition of Done](definition-of-done.md). Usar PR
pequeños hacia `develop` y promover entregas verificadas a `main`.

## Ubicación después de la reorganización hexagonal

- Integrante 1: app/modules/data_intake; las tools de calidad reutilizan exploration.
- Integrante 2: app/modules/exploration.
- Integrante 3: app/modules/analysis.
- Integrante 4: app/modules/critical_review.
- Integrante 5: app/modules/reporting; integración HTTP y bootstrap compartidos.
- app/shared/domain y app/shared/contracts son contratos comunes.

Consultar architecture.md y architecture-path-map.json antes de adaptar ramas.
El bloque autónomo del integrante 1 está descrito en integrante1-chatgpt-prompt.md.
