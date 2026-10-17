# Validación de grupos antes de planificar ANOVA

Planner omite las parejas de ANOVA que no tienen al menos dos grupos con dos
observaciones completas por grupo. Informa el motivo mediante una advertencia;
no crea un resultado estadístico ficticio ni consume llamadas de herramientas.
El filtrado ocurre antes de aplicar el presupuesto FAST, por lo que otra pareja
válida puede ocupar el lugar de una candidata descartada.

## Implementación

El bootstrap inyecta AnovaGroupProfiler en PlannerAgent usando el DatasetRegistry
local de cada ejecución. El planificador enumera solo las parejas de su pool
acotado (cuatro columnas por tipo en FAST, hasta doce en otros modos). El profiler
usa el mismo tratamiento de categorías, valores numéricos y filas completas que
la herramienta ANOVA, y devuelve únicamente número de grupos y tamaño mínimo.
No se añaden filas, nombres de categorías ni tablas a AgentContext, AgentState,
AnalysisReport o solicitudes LLM. El planificador determinista sigue usando metadatos.

Los contadores se calculan por pareja: los faltantes del resultado numérico pueden
reducir un grupo a una observación aunque la categoría tenga muchas filas. Grupos
sin observaciones completas quedan fuera, igual que en la herramienta existente.
Los datos inválidos conservan su validación y errores en la frontera estadística.

Los consumidores que construyen PlannerAgent sin el proveedor local mantienen el
contrato anterior. Solo se descartan los casos demostrablemente insuficientes por
cardinalidad; para validar distribuciones exactas deben inyectar el summarizer,
como hace build_use_case. No cambia ningún modelo público de API ni de persistencia.

## Validación

- 282 pruebas de backend aprobadas, incluidas diez regresiones nuevas.
- Ruff y formato sin errores (187 archivos Python).
- 4 pruebas E2E aprobadas con Microsoft Edge y backend real.

Las regresiones cubren todos los grupos singleton, un único grupo singleton,
insuficiencia creada por faltantes, menos de dos grupos completos, grupos válidos
con dos observaciones y elección de otra pareja válida en FAST. También verifican
que no se consume presupuesto al descartar ANOVA y que el pool permanece acotado.

La herramienta sigue validando tipos, no finitud, varianza y supuestos estadísticos.
Superar el control de tamaño no garantiza que ANOVA sea aplicable por cualquier otra
razón y no demuestra causalidad.
