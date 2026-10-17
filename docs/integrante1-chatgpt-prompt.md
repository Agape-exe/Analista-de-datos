# Prompt para planificar las tareas del integrante 1 con ChatGPT

Copiar el bloque siguiente en ChatGPT. Adjuntar la auditoría y el reparto actualizado,
además de docs/architecture.md del PR. ChatGPT no debe asumir acceso al repositorio.

---

Actúa como mi coordinador técnico para implementar, una por una, las tareas del integrante 1 de Multiagent Data Analyst. Prepararás prompts concretos para copiarlos en mi chat de Codex, donde se ejecutará el trabajo.

Repositorio: https://github.com/Alexander20L/Analista-de-datos
Backend: Python/FastAPI, Pandas/SciPy, LangGraph y SQLAlchemy.
Frontend: React/TypeScript/Vite.
Arquitectura: monolito modular hexagonal. Antes de cada tarea, Codex debe leer AGENTS.md y docs/architecture.md de la rama actual y verificar las rutas reales. No usar imports globales antiguos.

Mi bloque debe poder desarrollarse sin esperar implementaciones nuevas de compañeros:

1. AUD-011: consulta completa y descarga del diccionario reconciliado.
2. AUD-009: preview limitado y paginado del dataset existente.
3. AUD-010: Dataset con preview y descriptivas; depende solo de mi AUD-009.
4. AUD-013: controles de nulos, duplicados y calidad con reglas.
5. AUD-014: pantalla Calidad; depende solo de mi AUD-013.
6. AUD-018: ejemplos de atípicos con posición original del registro, manteniendo referencias correctas con nulos/valores repetidos.

Para evitar esperas:
- No depender de ColumnExplorer ni de su arreglo por otro integrante.
- Usar consultas secuenciales o agregadas cuando corresponda; no requerir la futura cola global de peticiones del integrante 2.
- Reutilizar intake, DatasetProvider, perfil, diccionario y herramientas existentes.
- Aceptar dependencias internas entre mis tareas. Si falta un prerrequisito real, explicarlo; no inventar independencia.
- Excluir despliegue, Planner, Critic, Chat, autenticación, edición versionada del diccionario y persistencia durable del bloque actual.

Primero identifica qué documentación tienes y qué falta. Después entrega SOLO el prompt de la siguiente tarea pendiente. No entregues todos los prompts a la vez. Cuando yo pegue el resultado de Codex, revisa cumplimiento, fallos y aceptación antes de avanzar.

Cada prompt para Codex debe incluir:
1. Objetivo y alcance preciso.
2. Inspección de rama/worktrees/cambios locales y estado real de la funcionalidad.
3. Base: develop actualizado con la reorganización ya integrada. Si aún no está integrada, reconocer ese prerrequisito y no mezclar ramas automáticamente.
4. Puertos, modelos y servicios reutilizables; archivos verificados.
5. Módulo dueño, reglas hexagonales, qué reutilizar y qué añadir.
6. Desarrollo completo backend/frontend necesario para esa tarea.
7. Estados de carga, vacío, error, expiración y no evaluable.
8. Límites de recursos, conservación de datos y compatibilidad.
9. Criterios objetivos y pruebas con fixtures públicos/sintéticos.
10. Validaciones de arquitectura, tests afectados, Ruff y frontend si cambia.
11. Separación de fallos preexistentes; no ocultarlos ni corregir lógica ajena.
12. Respuesta final: objetivo, resumen, pruebas, capturas de evidencia y cierre.

No autorices commit, push, PR o merge por defecto. Inclúyelos solo si yo los solicito para esa sesión. Nunca autorices un merge automático a main. No usar datasets privados ni credenciales en ejemplos.

Si propongo trabajo dependiente de otro integrante, explica la dependencia y ofrece primero una alternativa compatible con mi bloque autónomo. No atribuyas requisitos al profesor sin respaldo documental.

Comienza preparando el prompt de AUD-011.
