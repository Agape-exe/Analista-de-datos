# Definition of Done

Checklist por incremento o Pull Request:

- [ ] Cumple contrato común
- [ ] Tests añadidos
- [ ] Tests existentes pasan
- [ ] Manejo de errores
- [ ] Configuración no hardcodeada
- [ ] Logging/trazabilidad cuando corresponda
- [ ] Documentación actualizada
- [ ] Ruff correcto
- [ ] Pull Request revisado
- [ ] Integrado al flujo principal

Comandos de verificación:

```text
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

No declarar una capacidad analítica terminada únicamente porque el skeleton
compila: verificar resultados reales, evidencia y comportamiento ante errores.
