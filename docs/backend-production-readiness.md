# Preparación del backend para producción

## Objetivo y base

Esta sesión prepara el backend FastAPI para una demostración académica de bajo
tráfico. No crea infraestructura ni despliega servicios. La base revisada es
`60a56160a29e67ee2aa85de1c92d4b4d00255535` de `origin/main`.

El flujo analítico no cambió: Data Understanding → Planner → Analysis → Critic
→ Insight → Reporte. Los cambios se limitan a configuración, rutas HTTP,
protección de recursos, persistencia y arranque.

## Problemas abordados y soluciones

| Problema de auditoría | Solución implementada |
| --- | --- |
| CORS inexistente | `deployment.cors_allowed_origins` configura `CORSMiddleware` con una lista explícita, sin credenciales del navegador. |
| `POST /analysis` admite rutas locales | La ruta se registra mediante un router local independiente y no se registra cuando `allow_local_analysis=false`; producción exige dicho valor. |
| Cargas ilimitadas | Producción exige un límite positivo de dataset; se recomienda 2 MiB. Los adaptadores existentes siguen contando bytes por chunks y responden 413. |
| Ráfagas y operaciones costosas | Un rate limiter y una capacidad de operaciones, ambos por proceso y acotados, devuelven 429 con `Retry-After`. |
| SQLite efímero | Se añade `psycopg` 3 y configuración SQLAlchemy para `postgresql+psycopg://` con TLS y pool pequeño. SQLite continúa siendo el valor local. |
| Arranque PaaS | `run.py` usa `127.0.0.1` en desarrollo y `0.0.0.0` solo tras validar producción; conserva `PORT` y un worker. |

## Archivos modificados

- `app/config/settings.py` y `app/config/defaults.toml`: grupo `deployment`,
  validación de producción y TLS PostgreSQL.
- `app/api/main.py`, `app/api/routes/*.py` y `app/api/protection.py`: CORS,
  visibilidad de rutas y protecciones HTTP en memoria.
- `app/bootstrap.py`: opciones SQLAlchemy de psycopg.
- `pyproject.toml` y `uv.lock`: dependencia `psycopg[binary]`.
- `run.py`: host, puerto dinámico y un worker.
- `.env.example`: variables sin secretos.
- Pruebas unitarias e integración de configuración y guardas.

## Configuración

### Desarrollo

Los valores por defecto preservan el uso local:

```text
MDA_DEPLOYMENT__ENVIRONMENT=development
MDA_DEPLOYMENT__ALLOW_LOCAL_ANALYSIS=true
MDA_PERSISTENCE__DATABASE_URL=sqlite:///:memory:
MDA_UPLOADS__MAX_DATASET_BYTES=0
```

CORS permite por defecto `http://localhost:5173` y
`http://127.0.0.1:5173`. El proxy de Vite sigue siendo una comodidad exclusiva
del desarrollo.

### Producción

Producción es explícita: solo se activa con
`MDA_DEPLOYMENT__ENVIRONMENT=production`. Al cargar settings, se rechaza una
configuración que no tenga:

- `MDA_DEPLOYMENT__CORS_ALLOWED_ORIGINS` como lista JSON de orígenes HTTPS
  concretos, sin `*`, rutas, credenciales ni comodines.
- `MDA_DEPLOYMENT__ALLOW_LOCAL_ANALYSIS=false`.
- `MDA_UPLOADS__MAX_DATASET_BYTES` entre 1 y `2097152`; el máximo inicial de
  producción es 2 MiB.
- `MDA_UPLOADS__MAX_DICTIONARY_BYTES` como máximo `262144`.
- `MDA_PERSISTENCE__DATABASE_URL` con dialecto `postgresql+psycopg://`.
- `MDA_PERSISTENCE__POSTGRES_SSLMODE` distinto de `disable`.

Ejemplo sin credenciales:

```text
MDA_DEPLOYMENT__ENVIRONMENT=production
MDA_DEPLOYMENT__CORS_ALLOWED_ORIGINS=["https://example.vercel.app"]
MDA_DEPLOYMENT__ALLOW_LOCAL_ANALYSIS=false
MDA_UPLOADS__MAX_DATASET_BYTES=2097152
MDA_UPLOADS__MAX_DICTIONARY_BYTES=262144
MDA_DEPLOYMENT__MAX_UPLOAD_REQUESTS=5
MDA_DEPLOYMENT__MAX_EXPLORATION_REQUESTS=20
MDA_DEPLOYMENT__MAX_REPORT_REQUESTS=60
MDA_DEPLOYMENT__MAX_CONCURRENT_OPERATIONS=1
MDA_PERSISTENCE__DATABASE_URL=postgresql+psycopg://<usuario>:<secreto>@<host>/<base>
MDA_PERSISTENCE__POSTGRES_SSLMODE=require
```

Las variables de CORS son una defensa del navegador, no una autenticación ni una
autorización de la API.

## Seguridad de endpoints y recursos

- `/analysis` queda fuera del OpenAPI y devuelve 404 cuando la política local
  está desactivada; `/analysis/upload` es la ruta pública prevista.
- `/analysis/upload`, `/intake` y
  `/datasets/{dataset_id}/tools/{tool_name}` comparten la capacidad de
  operaciones costosas. Cuando se excede devuelve 429 y libera la capacidad en
  excepciones.
- Upload/intake, exploración y lecturas de reportes tienen límites de tasa por
  IP de conexión. La estructura es LRU acotada por `max_tracked_clients`.
- No se confían cabeceras `X-Forwarded-For`; detrás de un proxy todas las
  solicitudes pueden parecer del proxy. Una identificación real del cliente
  requiere configuración explícita del proxy confiable o autenticación futura.
- No se limita `/health`.
- `TemporaryUploadStorage` conserva el conteo en streaming y elimina el
  directorio temporal. El servidor/proxy debe establecer además un límite del
  cuerpo HTTP: FastAPI no sustituye un límite de borde para multipart.

No hay autenticación. `run_id` y `dataset_id` no son permisos. La demostración
no debe recibir datos personales o sensibles, y los reportes persistentes pueden
ser consultables por quien conozca su identificador.

## Persistencia SQLAlchemy y PostgreSQL

`SqlAlchemyAnalysisRepository` se conserva. Con la URL psycopg, el engine usa
`pool_pre_ping=True`, `pool_size=1`, `max_overflow=0`, reciclado a 300 segundos
y `sslmode=require` por defecto. Si la URL declara `sslmode`, debe coincidir con
`MDA_PERSISTENCE__POSTGRES_SSLMODE`; en producción el modo efectivo solo puede
ser `require`, `verify-ca` o `verify-full`. Esto impide que un parámetro de URL
debilite silenciosamente TLS. Este perfil está pensado para un worker pequeño y
conexiones remotas que se cierran por inactividad.

`Base.metadata.create_all()` crea el esquema inicial de manera no destructiva,
pero no reemplaza migraciones versionadas para cambios futuros. SQLite continúa
siendo válido para desarrollo y pruebas.

La conexión y recuperación contra Neon/PostgreSQL real están **NO EJECUTADAS**:
no se recibió una URL ni se creó infraestructura durante esta sesión.

## Arranque en Render

Python requerido: 3.12+. Para una instalación nativa con uv se propone:

```text
Build: uv sync --frozen --no-dev
Start: uv run --no-sync python run.py
Health check: /health
```

Alternativamente, el start command puede ser
`uv run uvicorn app.api.main:app --host 0.0.0.0 --port $PORT --workers 1`.
No se deben ejecutar múltiples workers en Render Free: cada uno cargaría sus
propios registros en memoria, multiplicaría el consumo y haría no compartidos
los límites de tasa/capacidad.

En Render se debe seleccionar el runtime Python y fijar una versión totalmente
cualificada mediante `PYTHON_VERSION`, por ejemplo `PYTHON_VERSION=3.12.11`.
El flag `--no-sync` es apropiado para el start command porque el build ya ejecutó
`uv sync --frozen --no-dev`; si el entorno no se creó correctamente, el proceso
fallará en lugar de resolver o instalar dependencias durante el arranque.

Render Free mantiene 512 MB y suspende servicios inactivos; Pandas y SciPy dejan
poco margen para datasets grandes. Los límites de 2 MiB y una operación costosa
simultánea son una política inicial, no una garantía de aislamiento de memoria.
Se debe medir RSS con CSV reales antes de la presentación.

## Frontend futuro

Vercel deberá compilar con
`VITE_API_BASE_URL=https://<backend-render>`. La SPA usa `BrowserRouter`, por lo
que Vercel requerirá una rewrite a `index.html`. El origen Vercel HTTPS debe ser
incluido literalmente en `MDA_DEPLOYMENT__CORS_ALLOWED_ORIGINS`. Las descargas
de Markdown continúan siendo enlaces directos HTTPS al backend.

## Validación

Resultados de esta rama:

| Comando | Resultado |
| --- | --- |
| `uv sync --locked` | aprobado; 71 paquetes resueltos, incluido `psycopg` 3.3.6 |
| `uv run python -m pytest` | 336 pruebas aprobadas en 5.64 s |
| `uv run ruff check .` | aprobado |
| `uv run ruff format --check .` | 202 archivos formateados |
| `git diff --check` y `git diff --cached --check` | aprobados |
| `npm test` | 5 archivos / 16 pruebas aprobadas |
| `npm run lint` | aprobado |
| `npm run build` | aprobado |

Las pruebas nuevas cubren settings de desarrollo/producción, rechazo de política
insegura, CORS/preflight, ocultamiento de `/analysis`, límite exacto de carga,
429/`Retry-After`, liberación de capacidad, opciones PostgreSQL y arranque PaaS.

## Pendientes y criterios para la sesión 3

1. Ejecutar una prueba de integración real contra una URL Neon configurada como
   secreto y comprobar reinicio + recuperación del reporte.
2. Medir memoria y latencia de Linux/Render para CSV de 0.5, 1 y 2 MiB.
3. Configurar límite de cuerpo en el proxy/PaaS, CORS final y rate limits tras
   conocer el dominio Vercel.
4. Definir retención y eliminación de reportes; no se implementó porque exige
   política de producto y migración/limpieza persistente.
5. Ejecutar Playwright en CI Ubuntu; no se modifica React en esta sesión.
6. Antes de exposición pública, decidir autenticación o aceptar explícitamente
   el alcance de demo sin privacidad multiusuario.

El backend está preparado para revisión técnica, no está desplegado ni debe
presentarse como plataforma multiusuario segura.
