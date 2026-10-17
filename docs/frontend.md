# Interfaz web de Data Intake

> Actualización del integrante 5: ver [guía de integración](integrante5-integracion.md).
> Las descripciones del skeleton de análisis reflejan la base original; la API de
> análisis y reporting se extendió en esta entrega.

## Estructura y tecnologías

`frontend/` pertenece al mismo repositorio que el backend hexagonal. Usa React,
TypeScript, Vite, Tailwind CSS y componentes locales siguiendo los patrones de
shadcn/ui (Slot, variantes CVA y utilidades de clases). Inter se distribuye como
fuente local con el bundle; Lucide aporta los iconos.

- `src/components/ui`: Button, Card y Badge.
- `src/components/layout`: sidebar, cabecera y AppShell.
- `src/features/data-intake`: formulario, archivos y estado de la petición.
- `src/features/dataset`: métricas, tabla, advertencias y descargas.
- `src/lib`: cliente HTTP y utilidades de presentación.
- `src/types/api.ts`: contratos generados, no editados manualmente.

El diseño sigue el PDF: superficies claras, acentos índigo, navegación por
intención, sidebar de 224 px en desktop y colapsada de 64 px a menor ancho.
Las tablas mantienen sus columnas mediante scroll horizontal; móviles usan
métricas en dos columnas. Incluye etiquetas accesibles, navegación de teclado,
skip-link, mensajes de estado y respeto por reduced-motion.

## Pantallas habilitadas

**New Analysis** permite cargar CSV/TSV por selección o arrastre, elegir separador
y encoding y adjuntar un DataDictionary JSON. La pregunta de investigación,
FAST/DEEP, TXT y SQL están señalados como Coming Soon.

**Dataset Overview** muestra metadatos reales: filas, columnas, roles, completitud,
tipos, nulos por columna, valores únicos, descripciones, procedencia y confianza
suministrada. El perfil y diccionario se descargan como JSON.

**Diccionario de datos** (`/dictionary`, Datos → Diccionario de datos) completa
AUD-011: consulta y descarga del diccionario del dataset activo, exclusivamente
de solo lectura. Reutiliza `IntakeProvider`, `IntakeResponse.summary.data_dictionary`,
`DatasetProfile`/`ColumnProfile`, los componentes visuales y `downloadJson`.
La consulta no relee el archivo ni solicita datos adicionales al backend.

La tabla incluye todas las columnas observadas y las entradas del diccionario:
tipo técnico observado, tipo declarado, semántica del diccionario, rol del perfil,
descripción, unidad, fuente, confianza, campos inferidos, justificación y
advertencias. `inferred_fields` distingue los agregados inferidos incluso en
entradas oficiales/manuales; una entrada `source=inferred` también se identifica
como inferida. El tipo técnico completado por inferencia no se presenta como
declarado. La semántica proporcionada y el rol del perfil se muestran por separado
para no ocultar discrepancias. La confianza ausente aparece como «No evaluada»,
los demás valores ausentes como «No disponible»; no se generan puntuaciones.

Los textos estructurales conocidos se traducen en la presentación; los metadatos
proporcionados y mensajes no reconocidos conservan su texto. React los representa
como texto, sin interpretar HTML. Las descripciones inferidas señalan que su
significado de negocio no está verificado. La tabla admite desplazamiento
horizontal por teclado y nombres largos con salto de línea.

Flujo: cargar CSV/TSV (con diccionario JSON opcional), pulsar «Comprender dataset»,
abrir Datos → Diccionario de datos y pulsar «Descargar diccionario JSON».
`<nombre>.dictionary.json` serializa el diccionario recibido, conserva nombres,
nulos y procedencia y no añade filas, perfil ni rutas internas. La descarga del
resumen del dataset sigue usando el mismo contrato y utilidad.

`DataDictionaryPage` consume los estados existentes de intake: sin resultado
ofrece «Ir a Nuevo análisis»; en carga oculta los metadatos anteriores; ante fallo
de carga ofrece «Revisar carga». Un diccionario vacío informa de la ausencia de
metadatos, muestra los tipos observados si existen y deshabilita la descarga.
Un error local de descarga permite reintentar. Cambiar el resultado o reiniciar
el proveedor actualiza o limpia la página; no hay un segundo estado de dataset.
Recargar el navegador elimina el resultado y devuelve la pantalla sin dataset.

Componentes: `features/dataset/DataDictionaryPage.tsx`, `DataDictionaryTable.tsx`
y `dictionary-presentation.ts`; composición en `app/App.tsx`, enlace en
`components/layout/Sidebar.tsx` y estilos limitados a la tabla en `globals.css`.
No cambia el backend ni OpenAPI: el módulo propietario continúa siendo
`app/modules/data_intake/`. No necesita un endpoint, puerto o persistencia nuevos.
No depende de `ColumnExplorer` y no incorpora edición ni versionado.

Limitación: esta pantalla consulta los metadatos ya calculados en el navegador.
No comprueba la expulsión del dataset del almacén del servidor ni simula una
expiración que intake no comunica. Puede mostrar esos metadatos mientras exista
el resultado de intake; para recuperar un resultado perdido hay que cargar de
nuevo el archivo. La traducción no altera los valores del JSON exportado.

**Associations** (`/associations`) ejecuta las tools de EDA sobre el dataset del
intake: ranking de relaciones candidatas, scatter/boxplot del par seleccionado,
matriz de correlación e histograma/boxplot por columna. Detalles en
[eda-association.md](eda-association.md).

Una confianza ausente se presenta como Not evaluated. No se inventa un score de
calidad ni indicadores de duplicados/outliers. Los demás destinos futuros se muestran
deshabilitados. El estado es Intake completed, no una afirmación
de análisis multiagente terminado.

El resultado de intake vive en memoria del navegador: recargar la página lo descarta.
New Analysis inicia una carga nueva. En caso de error se preservan archivos/opciones
para corregir y reintentar.

**Insights y evidencia** (`/report`) ejecuta el análisis del archivo seleccionado,
muestra resultados, evidencia, métricas y estados, y descarga JSON/Markdown. Un
reporte se puede recuperar por run_id después de recargar la página; para conservarlo
tras reiniciar el backend se requiere una URL de SQLite persistente explícita.

## Backend y contratos

`POST /intake` acepta multipart:

| Campo | Tipo | Descripción |
|---|---|---|
| `file` | Archivo obligatorio | Dataset CSV o TSV |
| `data_dictionary` | Archivo opcional | JSON con `{ "entries": [...] }` |
| `delimiter` | String de un carácter | Separador CSV; TSV utiliza tabulador |
| `encoding` | String | UTF-8 por defecto |

Respuesta `IntakeResponse`: status, filename, profile, summary, completeness,
warnings y profiling_time. Los porcentajes de nulos se calculan en Python.
No se devuelven filas crudas ni rutas temporales del servidor.

La ruta HTTP delega en `IntakeUploadedDataset`, que depende de los puertos
`DataUnderstanding` y `UploadStorage`. `TemporaryUploadStorage` escribe con nombres
generados y limpia los archivos tras éxito o error; el servicio de comprensión
existente recibe la ruta temporal mediante AnalysisInput. No se introduce lógica
de clasificación en React ni FastAPI.

La configuración `[uploads]` usa `max_dataset_bytes = 0` por defecto: sin límite
de tamaño de dataset impuesto por la aplicación. Un valor positivo permite fijar
un límite en bytes. El diccionario tiene un límite de 1 MiB, el chunk es de 64 KiB
y el directorio temporal es opcional. Son valores sobrescribibles mediante TOML
o `MDA_UPLOADS__...`. El directorio personalizado debe existir. Las cargas no se
guardan automáticamente en `datasets/`. El procesamiento del dataset utiliza
memoria y su tamaño viable depende de los recursos disponibles.

Para desactivar un límite configurado previamente, establecer en `.env`:

```dotenv
MDA_UPLOADS__MAX_DATASET_BYTES=0
```

Reiniciar el backend después de cambiar la configuración.

Errores: 400 para archivo/diccionario no utilizable, 413 al superar límites y 422
para campos HTTP inválidos. El cliente muestra el mensaje y X-Request-ID cuando
está disponible, y distingue fallos de conexión del backend.

## Instalación y desarrollo

Backend, desde la raíz:

```powershell
uv sync --locked
uv run python run.py
```

Frontend, desde `frontend/`:

```powershell
npm.cmd ci
npm.cmd run dev
```

Abrir `http://localhost:5173`. El proxy Vite transforma `/api/intake` en `/intake`
contra `http://127.0.0.1:8000`; no requiere CORS para este flujo.
`frontend/.env.example` documenta VITE_API_BASE_URL y API_PROXY_TARGET.

Generar nuevamente contratos después de cambiar modelos o rutas:

```powershell
npm.cmd run generate:api
```

El script lee OpenAPI directamente desde la aplicación Python, sin necesitar un
servidor activo. Para producción, `npm.cmd run build` genera `frontend/dist`; el hosting
debe servir la SPA y reenviar `/api/*` al backend quitando ese prefijo. Los módulos
de infraestructura del backend siguen en su estructura actual.

## Verificación

```powershell
# Desde frontend/
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
```

Tests de navegador con backend real y un CSV de tres filas:

```powershell
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

Si Edge ya está instalado en Windows, se puede usar sin descargar Chromium:

```powershell
$env:PLAYWRIGHT_CHANNEL = "msedge"
npm.cmd run test:e2e
```

Playwright inicia servidores exclusivos en 8016 (backend) y 5186 (frontend), con
proxy explícito entre ellos. No reutiliza los servidores de desarrollo de 8000/5173.
Los puertos se pueden cambiar con E2E_BACKEND_PORT y E2E_FRONTEND_PORT; deben estar
libres. Las cuatro pruebas verifican intake y descarga del perfil, asociaciones y
gráficos, reportes SKIPPED/SUCCESS, evidencia, descargas JSON/Markdown, recuperación
por run_id y coexistencia de EDA con el análisis. Comprueban el layout hasta 390 px.
Las capturas son opcionales mediante UI_SCREENSHOT_DIR (directorio existente).
Los tests unitarios usan respuestas de prueba solo en archivos de testing;
las pantallas de producción no incluyen datasets o resultados simulados.

Desde la raíz, ejecutar también pytest y Ruff antes de integrar cambios.

### Validación de AUD-011 — 17 de octubre de 2026

Base exclusiva: `origin/develop` actualizado mediante `git fetch origin`, SHA
`61d189b24bc316462bfe8c41fca2f72597ad0661` (merge del PR #28). Implementación en
`feat/aud-011-data-dictionary`, worktree aislado `Analista-de-datos-aud011`.
No se modificaron backend, contratos generados, algoritmos, dependencias ni
worktrees anteriores; no se realizaron commits, push, PR ni merges.

Las comprobaciones se ejecutaron antes y después sobre el mismo worktree:

| Comprobación | Línea base sin cambios | Resultado con AUD-011 |
| --- | --- | --- |
| `uv sync --locked` | Correcto | Correcto |
| `uv run python scripts/check_architecture.py` | Correcto, 162 archivos Python | Igual |
| `uv run python -m pytest tests/architecture -q` | 24 aprobadas | 24 aprobadas |
| `uv run python -m pytest` | 375 aprobadas, 4 fallidas | 375 aprobadas, las mismas 4 fallidas |
| `uv run ruff check .` | 2 errores ajenos | Los mismos 2 errores |
| `uv run ruff format --check .` | 249 archivos formateados | Igual |
| `npm ci` | Correcto | Correcto |
| `npm test` | 18 aprobadas, 1 fallida | 35 aprobadas, la misma 1 fallida |
| `npm run lint` | 1 error ajeno | El mismo error |
| `npm run build` | Correcto | Correcto (incluye TypeScript) |

Fallos preexistentes de pytest, reproducidos sin cambios:

- `tests/integration/test_anova_planning.py::test_fast_mode_uses_next_valid_anova_after_omitting_sparse_pair`.
- `tests/integration/test_critic_pipeline.py::test_default_csv_produces_measured_critic_and_insights_without_a_question`.
- `tests/unit/test_critic.py::test_critic_reports_significant_results_without_robustness_as_preliminary`.
- `tests/unit/test_critic.py::test_critic_skips_when_no_result_is_significant`.

Ruff conserva F841 (`unranked`) en
`app/modules/analysis/application/services/analysis_planning.py:273` y F401
(`AssociationResult`) en `tests/unit/test_planner_agent.py:10`.
Frontend conserva el fallo `null metrics stay unmeasured and no insights are
invented` de `ReportPage.test.tsx` y el import sin uso `methodLabel` de
`features/reports/ReportPage.tsx:6` en ESLint. No se corrigieron módulos ajenos.

Pruebas específicas: **17/17 aprobadas** en `DataDictionaryPage.test.tsx`. Cubren
navegación y ruta directa, ausencia de dataset, visualización, valores declarados
e inferidos, opcionales ausentes, diccionario vacío, advertencias, JSON y nulos,
reintento de descarga, cambio de dataset, reinicio, carga fallida, respuesta tardía
tras cancelación y contenido no confiable. La descarga se compara con el contrato
recibido sin transformarlo. ESLint limitado a los archivos TypeScript de AUD-011
termina sin errores.

Comprobación adicional con backend real y Edge: **1/1 E2E aprobada**, ejecutando
`npm run test:e2e -- e2e/dictionary.spec.ts` con `PLAYWRIGHT_CHANNEL=msedge`.
Carga CSV con diccionario oficial parcial y después TSV sin diccionario,
comprueba procedencia, confianza, inferencias, ambas descargas y sus nombres,
cambio/reinicio, pérdida del estado al recargar y ausencia de errores JavaScript.
Comprueba anchos de 1440, 1024 y 390 px sin desbordamiento de la página y con
desplazamiento interno de la tabla; las capturas se revisaron visualmente.
Para guardar capturas, establecer `UI_SCREENSHOT_DIR` a una carpeta existente.

Fallos nuevos pendientes de AUD-011: **0**. No se añadieron pruebas backend porque
no hay cambios backend. La suite completa sigue teniendo los fallos anteriores:
AUD-011 está listo para revisión funcional, con esos fallos ajenos documentados.
