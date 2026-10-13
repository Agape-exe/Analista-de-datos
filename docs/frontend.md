# Interfaz web de Data Intake

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

Una confianza ausente se presenta como Not evaluated. No se inventa un score de
calidad ni indicadores de duplicados/outliers. Las asociaciones y demás destinos
futuros se muestran deshabilitados. El estado es Intake completed, no una afirmación
de análisis multiagente terminado.

El resultado vive en memoria del navegador: recargar la página lo descarta. New
Analysis inicia una carga nueva. En caso de error se preservan archivos/opciones
para corregir y reintentar. No existe historial persistente en esta entrega.

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
npm ci
npm run dev
```

Abrir `http://localhost:5173`. El proxy Vite transforma `/api/intake` en `/intake`
contra `http://127.0.0.1:8000`; no requiere CORS para este flujo.
`frontend/.env.example` documenta VITE_API_BASE_URL y API_PROXY_TARGET.

Generar nuevamente contratos después de cambiar modelos o rutas:

```powershell
npm run generate:api
```

El script lee OpenAPI directamente desde la aplicación Python, sin necesitar un
servidor activo. Para producción, `npm run build` genera `frontend/dist`; el hosting
debe servir la SPA y reenviar `/api/*` al backend quitando ese prefijo. Los módulos
de infraestructura del backend siguen en su estructura actual.

## Verificación

```powershell
# Desde frontend/
npm run typecheck
npm run lint
npm test
npm run build
```

Tests de navegador con backend real y un CSV de tres filas:

```powershell
npx playwright install chromium
npm run test:e2e
```

Si Edge ya está instalado en Windows, se puede usar sin descargar Chromium:

```powershell
$env:PLAYWRIGHT_CHANNEL = "msedge"
npm run test:e2e
```

Playwright inicia los servidores si no están activos. Verifica carga real,
descarga del perfil, ausencia de errores JS y layout a 1440, 1024 y 480 px.
Las capturas son opcionales mediante UI_SCREENSHOT_DIR (directorio existente).
Los tests unitarios usan respuestas de prueba solo en archivos de testing;
las pantallas de producción no incluyen datasets o resultados simulados.

Desde la raíz, ejecutar también pytest y Ruff antes de integrar cambios.
