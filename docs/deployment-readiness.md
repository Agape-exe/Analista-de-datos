# Auditoría de preparación para despliegue del MVP

## Objetivo y alcance

Esta auditoría evalúa el estado de `origin/main` para un MVP académico de
Multiagent Data Analyst. No configura servicios en la nube ni cambia el
comportamiento de la aplicación. Sus recomendaciones parten del commit
`173ca997` (`Merge pull request #22`), revisado el 17 de octubre de 2026.

El PR #21 sigue abierto hacia `develop`, no hacia `main`. Por tanto, esta
evaluación cubre los formatos disponibles en la rama auditada: **CSV y TSV**.
No presupone los formatos adicionales propuestos en dicho PR.

## Estado del backend

- Python: `>=3.12`, comprobado localmente con CPython 3.12.10.
- Aplicación: FastAPI, Uvicorn, Pandas, SciPy, scikit-learn, LangGraph y
  SQLAlchemy están declarados en `pyproject.toml`; la suite instaló 68 paquetes.
- `GET /health` existe y devuelve `{"status":"ok"}`. Es un endpoint de
  *liveness*, no una comprobación de base de datos ni de preparación analítica.
- El grafo y los agentes se construyen al iniciar el lifespan de FastAPI. Las
  herramientas estadísticas se ejecutan en un único proceso. La configuración
  actual tiene `timeout_seconds=15`; los cálculos síncronos de Pandas/SciPy no
  tienen interrupción fuerte garantizada si bloquean el hilo.
- `run.py` invoca Uvicorn sin `host` ni `port` explícitos. Para un PaaS debe
  utilizarse un comando que enlace `0.0.0.0` y el puerto entregado por el
  proveedor, por ejemplo:

  ```text
  uv run uvicorn app.api.main:app --host 0.0.0.0 --port $PORT
  ```

  Este comando debe incorporarse en la configuración de despliegue de una sesión
  posterior, no se creó ningún archivo de infraestructura en esta auditoría.

### Mediciones locales reproducibles

Estas cifras se obtuvieron en Windows, sin tráfico ni dataset cargado; no son
una garantía de consumo en Linux:

| Medición | Resultado |
| --- | ---: |
| Importación caliente de FastAPI, Pandas, SciPy, scikit-learn, LangGraph y `app.api.main` | 4.564 s |
| Inicio hasta `GET /health` | 5.307 s |
| Memoria residente del proceso Python que atendía Uvicorn | ~210.9 MB |
| Memoria privada indicada por Windows | ~1,141.9 MB |

La memoria residente deja margen limitado en una instancia de 512 MB para el
proceso, Pandas y las copias transitorias de un dataset. El valor de memoria
privada de Windows no debe compararse directamente con el límite RSS/cgroup de
Linux. Antes de publicar se debe medir en el contenedor Linux del proveedor con
un CSV cercano al límite elegido.

## Estado del frontend

- Node requerido: `>=20.19.0` (`frontend/package.json`).
- Instalación: `npm ci`; compilación: `npm run build`; salida: `frontend/dist`.
- Vite configura el proxy `/api` solamente en `server`, por lo que funciona en
  desarrollo y no existe en un despliegue estático.
- El cliente obtiene la base desde `VITE_API_BASE_URL` (por defecto `/api`). En
  Vercel debe definirse, durante el build, con la URL HTTPS pública del backend,
  sin barra final: `VITE_API_BASE_URL=https://<backend>.onrender.com`.
- Se utiliza `BrowserRouter`. El host estático debe servir `index.html` como
  fallback para rutas de cliente como `/report`; hay que configurar una rewrite
  de SPA en el proveedor elegido.
- Las descargas Markdown son enlaces directos al backend. Funcionan con una URL
  HTTPS pública; las peticiones `fetch` de la SPA, en cambio, requieren CORS.

## Persistencia

- Predeterminado actual: `sqlite:///:memory:`. Los reportes desaparecen cuando
  el proceso se reinicia, se redeploya o Render lo suspende.
- `SqlAlchemyAnalysisRepository` inicializa el esquema con
  `Base.metadata.create_all()` y guarda el JSON serializado de `AnalysisReport`.
  El reporte contiene perfiles, resultados, evidencia, evaluaciones, insights y
  métricas; no almacena `LoadedDataset`, `LocalTable` ni las filas completas.
- La URL puede configurarse mediante
  `MDA_PERSISTENCE__DATABASE_URL`. La dependencia del proyecto no incluye un
  controlador PostgreSQL (`psycopg`, `psycopg2` o `asyncpg`), por lo que una
  URL de Neon no funcionará hasta añadir un driver compatible y probar la
  conexión.
- Para un MVP de una sola instancia, el repositorio SQLAlchemy existente es una
  base adecuada. Falta una estrategia de migraciones/versionado de esquema,
  necesaria si el modelo de reporte evoluciona después de guardar datos reales.

## Seguridad mínima para una demo pública

| Hallazgo | Riesgo | Acción prioritaria propuesta |
| --- | --- | --- |
| `MDA_UPLOADS__MAX_DATASET_BYTES=0` | Carga ilimitada; con Pandas puede agotar 512 MB y disco temporal | Establecer inicialmente `2097152` (2 MiB), medir y ajustar antes de la demo. |
| Sin `CORSMiddleware` | El frontend en Vercel no podrá usar el API de Render desde el navegador | Añadir una lista configurable y explícita de orígenes permitidos HTTPS. |
| `POST /analysis` acepta `source.path` | Un cliente público podría solicitar lectura de rutas locales del servidor | No exponer esta ruta públicamente; conservarla solo para desarrollo o restringirla a una raíz segura. Usar `/analysis/upload` para el MVP. |
| Sin autenticación/autorización | Cualquier cliente puede solicitar reportes si conoce/adivina el `run_id`, y utilizar intake/EDA | Declarar explícitamente demo pública; como mínimo introducir rate limiting y una política de retención. No subir datos personales. |
| Archivos temporales | Se manejan correctamente dentro de `TemporaryDirectory`, pero comparten el disco efímero de la instancia | Mantener la carga y análisis en una sola solicitud, fijar límites y no persistir rutas. |
| Cálculos CPU-bound | El timeout cooperativo no garantiza detener Pandas/SciPy bloqueantes | Limitar tamaño de archivo, columnas y presupuesto de herramientas; documentar el límite de 15 s como objetivo, no como aislamiento duro. |

La carga multipart valida extensión CSV/TSV, delimitador de un carácter y tamaño
cuando se configura. La lectura valida cabeceras, codificación y anchura de
filas. No sustituye límites de proxy/PaaS, autenticación ni rate limiting.

## Evaluación de proveedores (verificada el 17 de octubre de 2026)

| Alternativa | Coste inicial | Compatibilidad y limitaciones relevantes | Veredicto |
| --- | --- | --- | --- |
| A. Vercel Hobby + Render Free + Neon Free | $0 mientras no se excedan cuotas | Vercel Hobby es gratuito para uso personal/no comercial; Render Free ofrece 512 MB/0.1 CPU, una sola instancia y suspensión tras 15 min; Neon Free ofrece PostgreSQL con cuotas y scale-to-zero | **Recomendada para demostración académica de bajo tráfico**, tras aplicar los bloqueos de seguridad y medir el límite de carga. |
| B. Render para frontend y backend + Neon | $0 mientras no se excedan cuotas | Un static site de Render es gratuito y simplifica el proveedor, pero el backend conserva el cold start y 512 MB. Sigue necesitando CORS si son orígenes distintos. | Alternativa sencilla si se prefiere un único panel; no resuelve la limitación de memoria. |
| C. Vercel Hobby + Railway Free + Neon Free | $0 inicial, pero crédito muy limitado | Railway ofrece prueba de $5/30 días y luego $1 mensual; el plan Free limita a 0.5 GB RAM por servicio. | Menos predecible para una clase que Render Free; usar solo si se valida consumo y la cuenta obtiene acceso de prueba suficiente. |

Fuentes oficiales actuales: [Vercel Hobby](https://vercel.com/docs/plans/hobby),
[límites Vercel](https://vercel.com/docs/limits), [Render Free](https://render.com/docs/free),
[planes de cómputo Render](https://render.com/docs/compute-plans),
[Railway Free Trial](https://docs.railway.com/pricing/free-trial),
[precios Railway](https://railway.com/pricing), [Neon Free](https://neon.com/blog/neon-free-plan-1-gb-per-project).
Los planes gratuitos y sus cuotas cambian: deben verificarse de nuevo justo antes
de crear los servicios. La fuente de Neon más reciente anuncia 1 GB de Postgres
por proyecto y 100 CU-hours mensuales; no se debe asumir que esa cuota permanecerá
sin cambios.

### Arquitectura recomendada

Para la demostración: frontend estático en Vercel Hobby, API FastAPI en un único
Render Free web service y reportes en Neon PostgreSQL. Coste previsto: **$0/mes**
si el uso se mantiene dentro de los planes gratuitos. El primer acceso tras
inactividad del backend puede tardar alrededor de un minuto según Render; el
arranque local medido no representa ese cold start remoto.

Variables necesarias una vez preparada la infraestructura:

```text
MDA_PERSISTENCE__DATABASE_URL=postgresql+<driver>://...
MDA_UPLOADS__MAX_DATASET_BYTES=2097152
MDA_UPLOADS__MAX_DICTIONARY_BYTES=262144
VITE_API_BASE_URL=https://<backend-publico>
```

El origen permitido de CORS aún no tiene configuración en el proyecto: requerirá
una variable y una implementación mínima en la siguiente sesión.

## Validación de referencia

| Comprobación | Resultado |
| --- | --- |
| `uv run python -m pytest` | 311 aprobadas en 7.20 s |
| `uv run ruff check .` | aprobado |
| `uv run ruff format --check .` | 195 archivos formateados |
| `npm ci` | instalado; 0 vulnerabilidades reportadas por npm |
| `npm test` | 5 archivos / 16 pruebas aprobadas |
| `npm run lint` | aprobado |
| `npm run build` | aprobado; Vite generó `dist` |
| `npm run test:e2e` | bloqueado en este Windows: Playwright/Chromium falla antes de cada caso con `browserType.launch: spawn UNKNOWN` |

El backend de E2E sí alcanzó a iniciar Uvicorn antes del fallo. Este resultado no
demuestra una regresión funcional. Ejecutar `npm ci`, `npx playwright install
--with-deps` y `npm run test:e2e` en GitHub Actions Ubuntu para validar los cinco
casos con Chromium en un entorno compatible.

## Bloqueantes y plan priorizado

1. **Antes de exponer el API:** deshabilitar/restringir `POST /analysis` en
   producción, añadir CORS con lista de orígenes, límite de carga y rate limiting
   básico.
2. **Persistencia:** declarar un driver PostgreSQL, configurar Neon mediante
   variables del proveedor y validar creación de esquema, guardado y recuperación
   tras reiniciar el proceso.
3. **Configuración de despliegue:** definir build/start commands, host/`$PORT`,
   health check `/health`, rewrite SPA y `VITE_API_BASE_URL`; no se implementó en
   esta auditoría.
4. **Capacidad:** medir RSS y latencia en Linux con archivos de 0.5, 1 y 2 MiB;
   mantener un único worker y reducir el límite si el RSS se aproxima a 512 MB.
5. **Validación remota:** añadir/usar CI Ubuntu para Playwright, probar CORS desde
   el dominio estático y comprobar el cold start de Render antes de la clase.
6. **Operación de demo:** definir retención de reportes, aviso de privacidad y
   prohibición de datos sensibles; no hay autenticación ni aislamiento por usuario.

## Capacidades y límites de la rama auditada

Implementado y comprobado por pruebas: carga CSV/TSV, perfilado, EDA en memoria,
Planner/Analysis, herramientas estadísticas, Critic/Insight, reportes y descarga
Markdown. Parcial: despliegue productivo, persistencia PostgreSQL, CORS, límites
operativos y E2E del navegador en este equipo. Pendiente: infraestructura de
producción, autenticación, rate limiting, migraciones y una política de datos.

La arquitectura candidata es apta para un MVP académico de tráfico bajo **solo
después** de resolver los cuatro primeros puntos del plan priorizado. No es una
configuración adecuada para cargas grandes, datos sensibles ni disponibilidad
continua.
