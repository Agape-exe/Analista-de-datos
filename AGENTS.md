# Reglas de trabajo del repositorio

- Leer docs/architecture.md antes de añadir o trasladar capacidades.
- El backend es un monolito modular hexagonal bajo app/modules.
- Casos de uso y agentes pertenecen a application; no importan adapters,
  FastAPI, Pandas/SciPy, SQLAlchemy ni LangGraph.
- Definir dependencias externas como puertos e inyectar adaptadores en
  app/bootstrap.py o en el composition root HTTP app/api/main.py.
- Consumir otros módulos mediante puertos/contratos, no implementaciones privadas.
  Shared no importa módulos funcionales.
- Los modelos comunes viven en app/shared/domain y los DTO de integración en
  app/shared/contracts. No duplicar algoritmos ni agregar capas vacías.
- Nuevos endpoints pertenecen al adaptador HTTP del módulo dueño.
- Mantener compatibilidad pública y de reportes; cambios intencionales requieren
  pruebas y revisión de consumidores.
- No restaurar los antiguos árboles globales app/agents, app/analytics,
  app/application, app/adapters, app/domain o app/ports.
- Ejecutar `uv run python scripts/check_architecture.py` y
  `uv run pytest tests/architecture -q`, además de las pruebas afectadas.
- Separar fallos preexistentes de regresiones. No corregir algoritmos ajenos al
  alcance solo para dejar verde una reorganización.
- Consultar docs/architecture-path-map.json al adaptar ramas anteriores.
