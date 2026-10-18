# AUD-003 — Regresiones frontend

Base: develop 0fd1dfd2427dc45bb1dd1236f05f2270fe8ffc2d. Rama local: fix/aud-003-frontend-regressions.

## Alcance

- Unificar el estado vacío de Hallazgos con la terminología en español y sus pruebas.
- Retirar el import methodLabel sin uso en ReportPage.
- Actualizar selectores E2E del reporte de pagos a los nombres actuales en español.
- Comprobar las seis etapas por sus claves explícitas, incluida Association, en los reportes E2E y comprobar sus seis etiquetas en la prueba de la pantalla.

No se modifican contratos, algoritmos, guardas del backend, manejo de contexto (AUD-042), dependencias ni configuración de despliegue. No hay pruebas omitidas ni expectativas estadísticas rebajadas. La identidad aditiva sigue siendo una aserción obligatoria.

## Validación local

| Comprobación | Base | Resultado tras AUD-003 |
| --- | --- | --- |
| npm.cmd test | 35 aprobadas, 1 fallida | 36 aprobadas |
| npm.cmd run lint | methodLabel sin uso | Correcto |
| npm.cmd run build | Correcto | Correcto |
| Comprobador de arquitectura | 167 archivos, correcto | Backend intacto |
| Pruebas de arquitectura | 24 aprobadas | Backend intacto |
| Suite backend | 468 aprobadas, 4 fallidas | Backend intacto |
| Ruff | 2 errores en Planner y su prueba | Backend intacto |
| E2E con Edge y backend real | No se ejecutó completa antes de los cambios | 3 aprobadas, 3 fallidas |
| git diff --check | Correcto | Correcto |

Los resultados proceden de ejecuciones locales, no de CI ni del entorno desplegado. La validación backend se ejecutó antes de las correcciones de frontend; no se repite porque no cambian sus archivos.

## Fallos fuera del alcance

- Dos E2E no encuentran relaciones en Asociaciones y muestran The analysis service is busy. Try again later. Corresponde investigar el transporte y la capacidad en AUD-004, integrante 2. No se aumentaron límites ni se añadieron reintentos en las pruebas para disimularlo.
- El E2E de pagos ahora supera los selectores, obtiene el reporte SUCCESS y comprueba las seis etapas, pero no encuentra additive_identity. Corresponde a la política de Planner en AUD-001, integrante 3; también falla la prueba backend test_default_csv_produces_measured_critic_and_insights_without_a_question.
- Los otros fallos backend son test_fast_mode_uses_next_valid_anova_after_omitting_sparse_pair (AUD-001) y dos pruebas de Critic que contradicen el criterio descriptivo (AUD-002, integrante 4).
- Ruff conserva F841 en analysis_planning.py y F401 en test_planner_agent.py (AUD-006, integrante 3).

AUD-042 puede comenzar sobre estas correcciones sin esperar a que las suites integrales queden verdes. Mantener separados los fallos de las dependencias y cualquier nueva regresión.

## Comandos

Desde frontend: npm.cmd test; npm.cmd run lint; npm.cmd run build. Para E2E establecer PLAYWRIGHT_CHANNEL=msedge y ejecutar npm.cmd run test:e2e. Ejecutar ESLint después de Playwright, ya que Playwright recrea test-results y una exploración simultánea de ESLint puede observar la carpeta transitoriamente ausente.

Desde la raíz: uv run python scripts/check_architecture.py; uv run python -m pytest tests/architecture -q; uv run python -m pytest -q; uv run ruff check .
