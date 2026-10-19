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
y encoding y adjuntar un DataDictionary JSON. La pregunta y las opciones de
planificación rápido/estándar están disponibles en **Hallazgos** (`/report`).
La carga enlaza a esa capacidad. TXT y SQL continúan pendientes; no hay modo profundo.

**Traza** (`/trace`) presenta el contexto del reporte, agentes, plan, decisiones,
herramientas y omisiones, con enlaces a resultados. Consume eventos instrumentados
del backend y señala reportes históricos sin instrumentación verificable. La
cabecera usa la identidad del reporte cuando se consulta un reporte recuperado.
Contratos vigentes: [auditoría de Planner y Analysis](planner-trace-audit.md).

**Dataset Overview** muestra metadatos reales: filas, columnas, roles, completitud,
tipos, nulos por columna, valores únicos, descripciones, procedencia y confianza
suministrada. El perfil y diccionario se descargan como JSON.

### AUD-010 — Consulta de filas en Dataset

La ruta existente `/dataset` integra la vista previa de filas sin reemplazar el
resumen, métricas, perfiles, completitud ni descargas. `IntakeProvider` sigue
siendo la única fuente del dataset activo y no se modifica. El panel se monta
con `IntakeResponse.profile.dataset_id`; al cambiar ese identificador se
reinicia su estado local. No se introduce otra pantalla ni almacenamiento global.

Flujo: cargar CSV/TSV → Comprender dataset → Dataset → Vista previa del dataset.
`getDatasetPreview` centraliza en `lib/api-client.ts` la consulta tipada
`GET /datasets/{dataset_id}/preview?offset=0&limit=20`. Los tipos proceden del
OpenAPI generado mediante `npm run generate:api`, sin modificar el backend ni
editar manualmente `types/api.ts`. El generador incorpora ruta, operación y
`DatasetPreview`; otras diferencias textuales son de orden. Se comprobó que las
declaraciones anteriores no cambian semánticamente.

`DatasetPreviewPanel` coordina tamaño de página, carga, errores y navegación;
`DatasetPreviewTable` muestra los valores y encabezados con sus tipos técnicos.
Ambos viven en `features/dataset/DatasetPreview.tsx`. `useDatasetPreview.ts`
gestiona las peticiones y su cancelación. Solo mantiene la página actual y no
precarga el resto. Los datos de prueba están exclusivamente en archivos de test.

La tabla conserva estrictamente `rows[i][j] → columns[j]`; no ordena, filtra ni
interpreta posiciones como identificadores de negocio. Muestra total, cantidad
devuelta y rango visible. Comienza con 20 filas y permite 10, 20, 50 o 100; un
cambio de tamaño reinicia a offset 0. «Siguiente» usa el `next_offset` devuelto
y se deshabilita si `has_more=false`. «Anterior» usa `offset` y `limit` de la
respuesta, sin bajar de cero, y está deshabilitado en la primera página. Los
controles se bloquean durante la carga para evitar solicitudes duplicadas.

El cliente valida la respuesta antes de mostrarla: dataset y página solicitados,
estructura de columnas y filas, anchos, valores escalares, conteos y metadatos
de paginación coherentes. Una respuesta incompleta o de otro dataset no se usa.
La página vacía válida tiene su propio mensaje. La región desplazable admite
foco y teclado, encabezados fijos, nombres largos y celdas con salto de línea;
no provoca desbordamiento horizontal de toda la pantalla. No trunca valores.

Cada petición tiene un `AbortController` y una clave de dataset/offset/limit/
reintento. El hook comprueba la cancelación tanto al resolver como al rechazar.
Solo expone resultados de la clave actual; al solicitar otra página oculta las
filas anteriores. Desmontar la pantalla, iniciar Nuevo análisis o cargar otro
dataset cancela la solicitud anterior. Una respuesta tardía no puede reemplazar
la del dataset o página actuales. No depende de `ColumnExplorer`.
El envío se difiere una microtarea para que la primera ejecución cancelada por
StrictMode en desarrollo no envíe un GET duplicado.

Estados y recuperación:

- Sin dataset/identificador: conserva el estado vacío y enlace de carga; no
  solicita preview.
- Cargando: indicador accesible, sin filas anteriores presentadas como actuales.
- Conexión fallida o error inesperado: explicación y botón «Reintentar».
- `DATASET_NOT_FOUND`: detecta `DatasetExpiredError`, explica la ausencia en
  memoria y ofrece volver a Nuevo análisis. No presupone un TTL: el backend usa
  LRU y pierde datasets al reiniciar.
- `PREVIEW_TOO_LARGE`: explica el exceso y permite reducir las filas por página.
  Advierte que una celda o esquema grande puede seguir fallando con menos filas.
- Validación, respuesta incompleta, `PREVIEW_UNSUPPORTED` y límites 429: mensajes
  controlados y reintento, sin mostrar trazas o detalles internos del servidor.

Se respetan los límites de AUD-009: máximo 100 filas, 1000 columnas, 10000
celdas, 1 MiB de respuesta y 64 KiB por valor serializado. Detalles del contrato
y normalización en [data-intake.md](data-intake.md); esta pantalla no modifica
esa política ni introduce un endpoint adicional.

Valores: los strings conservan su contenido (incluidos ISO y ceros iniciales),
los booleanos se muestran como `true`/`false` y los números mediante su
representación textual disponible, sin formato que añada redondeo. `null` se
distingue como «Sin dato»; la cadena `"null"` continúa siendo texto, y la cadena
vacía se identifica como «Texto vacío». React representa las celdas como texto,
sin interpretar HTML.

**Precisión numérica:** el parser JSON estándar puede redondear enteros fuera
del rango seguro de JavaScript antes de que lleguen al componente. Se verificó,
por ejemplo, que el token `9007199254740993` se convierte en `9007199254740992`
y no supera `Number.isSafeInteger`. Para conservar compatibilidad sin un parser
global ni cambios backend, las celdas numéricas enteras no seguras muestran
«Precisión no garantizada», ocultando el número potencialmente redondeado y
ofreciendo una advertencia de página. Consultar el archivo original para el
valor exacto. Los identificadores que llegan como string y los enteros seguros
no cambian. Esta solución evita afirmar una precisión que no se puede recuperar.

Se implementa únicamente AUD-010: no añade algoritmos, calidad avanzada,
referencias de anomalías ni cambios de Planner, Analysis, Critic o Reporting.

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

## AUD-014 — Calidad de datos

La opción **Calidad de datos** del menú abre `/quality`. Cargar un CSV o TSV en
Nuevo análisis, abrir Calidad desde el menú o «Ver calidad de datos» en Dataset.
La pantalla consulta únicamente `GET /datasets/{dataset_id}/quality` de AUD-013;
el identificador procede de `IntakeResponse.profile.dataset_id`. No vuelve a
subir ni leer el archivo, no ejecuta tools de Exploration y no calcula métricas
de calidad en React. IntakeProvider continúa como única fuente del dataset activo.

Se presentan nombre del archivo, procedencia y estado de evaluación, dimensiones,
celdas faltantes y su porcentaje, filas completas/incompletas, duplicadas
adicionales, porcentaje de duplicados y grupos repetidos. La tabla de faltantes
conserva nombres, tipos técnicos y orden del contrato. Los porcentajes se toman
del servidor, con el formateador existente (hasta dos decimales); 0% se muestra
explícitamente. La sección de duplicados explica la igualdad de filas completas
y la exclusión de la primera aparición de cada grupo. No inventa registros,
posiciones, ejemplos individuales, limpieza ni un puntaje global.

`rules` se renderiza dinámicamente, sin asumir que siempre habrá dos reglas:

- **PASS · Cumplida:** la regla fue evaluada y se cumplió.
- **FAIL · Incumplida:** fue evaluada y hay incumplimientos; se muestra el conteo
  observado cuando existe y el motivo proporcionado por el backend.
- **NOT_EVALUATED · No evaluada:** no se acreditan condiciones suficientes. Se
  muestra el motivo y no se atribuye un conteo a la regla.

El estado global EVALUATED significa evaluación completada, no calidad general
acreditada. Tablas sin filas o columnas se muestran como NOT_EVALUATED, sin
confundirlo con FAIL. Los conteos vacíos devueltos por el servidor se presentan
como tales. No se infieren métricas o decisiones que el contrato no proporciona.

### Componentes, transporte y sincronización

- `features/quality/DataQualityPage.tsx`: página conectada a IntakeProvider y
  panel de resultados con tarjetas, tabla semántica, resumen de duplicados y reglas.
- `features/quality/useDatasetQuality.ts`: consulta bajo demanda, reintento,
  AbortController y descarte de respuestas obsoletas. El panel se monta con key
  del dataset; cambiar o reiniciar intake elimina el estado anterior. Un cambio
  de consulta oculta inmediatamente datos previos. Al desmontar se aborta la
  solicitud. La microtarea inicial evita el GET duplicado del efecto descartado
  por React StrictMode. No hay polling, precarga de otras pantallas ni caché durable.
- `lib/api-client.ts`: `getDatasetQuality(datasetId, signal)` reutiliza el helper
  HTTP, codifica el identificador y devuelve DatasetQuality tipado.
- `lib/quality-response.ts`: valida identidad, estados, enteros seguros no
  negativos, finitud/rango de porcentajes, dimensiones y coherencia de conteos,
  columnas únicas, reglas y opcionales. HTTP 200 inconsistente genera
  INVALID_RESPONSE. Estas comprobaciones no sustituyen ni recalculan porcentajes
  o algoritmos backend para su presentación.
- `types/api.ts` se regenera con `npm run generate:api`, sin edición manual.
  Se incorporan la ruta/operación de calidad y sus seis esquemas. La comparación
  de declaraciones TypeScript conserva todos los contratos anteriores.

Se reutilizan Card, Badge, Button, iconos Lucide, formateadores y estilos del
proyecto. La tabla tiene encabezados, caption y región desplazable enfocables
por teclado; los estados se anuncian mediante status/alert. Las etiquetas de
reglas incluyen texto y colores con contraste reforzado. La cuadrícula se adapta
a escritorio, tablet y móvil; las columnas anchas desplazan dentro de la tabla.
React representa los nombres y descripciones como texto, sin interpretar HTML.

Dataset conserva resumen, métricas de intake, perfiles, preview/paginación y
descargas. Su sección «Calidad de datos de un vistazo» invita a la evaluación
completa y comunica que el control de duplicados está disponible. El placeholder
«Puntaje de calidad» se sustituye por «Controles de calidad · Disponibles»:
no afirma resultados antes de consultar la API. La prueba existente de App se
adapta a ese cambio y conserva la comprobación de las dos confianzas de columna
no evaluadas, las descargas y demás aserciones funcionales.

### Estados, errores y limitaciones

Sin dataset no hay solicitud y se ofrece volver a Nuevo análisis. Durante una
carga de intake no se presentan resultados anteriores. Las respuestas y errores
se muestran exclusivamente para la consulta vigente:

| Situación | Presentación y acción |
| --- | --- |
| 404 DATASET_NOT_FOUND | Dataset ya no registrado; volver a cargar |
| 413 QUALITY_TOO_LARGE | Presupuesto excedido, sin resultados parciales; volver a la carga |
| 422 QUALITY_UNSUPPORTED | Evaluación no compatible, distinta de una regla FAIL |
| 429 REQUEST_RATE_LIMITED / ANALYSIS_CAPACITY_EXCEEDED | Esperar y reintentar |
| Fallo de red | Mensaje comprensible y Reintentar |
| Respuesta inválida u otro error | Error controlado y Reintentar, sin métricas inconsistentes |

No se muestran trazas ni mensajes internos del servidor. El dataset está en el
almacén temporal LRU del backend, sin TTL ni persistencia durable. Un reinicio o
expulsión requiere recarga; tampoco se conserva intake al recargar el navegador.
AUD-013 limita evaluaciones a 250.000 filas, 1.000 columnas, 2.000.000 celdas,
64 MiB de datos estimados (no RSS garantizado), textos de 65.536 caracteres y
1 MiB de respuesta. AUD-014 no cambia esos límites ni el backend. No añade
autenticación, persistencia, dependencias, AUD-018 o nuevas reglas de calidad.

### Evidencias reproducibles

Desde `frontend/`, con Edge instalado y los puertos libres:

```powershell
New-Item -ItemType Directory -Path '..\..\aud014-evidence' -Force | Out-Null
$env:PLAYWRIGHT_CHANNEL = 'msedge'
$env:E2E_BACKEND_PORT = '8024'
$env:E2E_FRONTEND_PORT = '5194'
$env:UI_SCREENSHOT_DIR = (Resolve-Path '..\..\aud014-evidence').Path
npm run test:e2e -- e2e/quality.spec.ts
npm test -- src/lib/api-client.quality.test.ts src/features/quality/DataQualityPage.test.tsx --maxWorkers=1
npm run typecheck
npm run build
npm run lint
```

Playwright inicia servidores nuevos, con reuseExistingServer desactivado y proxy
explícito, y utiliza CSV sintéticos. Comprueba la respuesta real de AUD-013 y los
conteos, reglas FAIL/PASS, navegación Dataset/Diccionario, ausencia de consultas
de calidad fuera de su pantalla, teclado y anchos 1440/1024/390 px. Los errores
404, 413 y desconexión se inducen mediante interceptación controlada; el reintento
consulta de nuevo al backend real. Esa interceptación no se presenta como un
fallo real del servidor. Se exige ausencia de errores JavaScript de página.

Las capturas quedan fuera del repositorio, en `aud014-evidence`: escritorio,
móvil, faltantes, duplicados, reglas FAIL y PASS, sin dataset, dataset no disponible,
desconexión y evaluación demasiado grande. Los logs de pruebas, compilación,
arquitectura y generación se guardan en el directorio padre con prefijo aud014.

### Validación local de AUD-014

Base exclusiva `origin/develop`, SHA
`9481cff2ec0b2e3fa1331edcd154ff16170914f5` (PR #36, con #28, #29, #33 y #34).
Worktree `Analista-de-datos-aud014`, rama `feat/aud-014-quality-screen`.

| Comprobación | Línea base | Con AUD-014 |
| --- | --- | --- |
| Tests frontend completos | 83 aprobadas, 1 fallo | 138 aprobadas, el mismo fallo |
| Tests específicos nuevos | No existían | 55 aprobadas (33 cliente, 22 pantalla/integración) |
| E2E específicos con Edge/backend real | No existían | 2 aprobados |
| E2E completos | 4 aprobados, 4 fallos | 6 aprobados, los mismos 4 fallos |
| TypeScript y build | Correctos | Correctos |
| ESLint general | 1 error ajeno | El mismo error |
| ESLint de archivos AUD-014 | No aplica | Correcto |
| AST y arquitectura | 172 archivos correctos, 24 pruebas aprobadas | Igual |
| Generación OpenAPI | Faltaban tipos de calidad | Script oficial correcto, contratos previos preservados |
| git diff --check | Correcto | Correcto |

El fallo unitario preexistente es
`ReportPage.test.tsx::null metrics stay unmeasured and no insights are invented`.
ESLint mantiene el import `methodLabel` sin uso en ReportPage.tsx:6.
Los cuatro E2E fallidos, reconfirmados antes y después sin modificar sus pruebas,
son Associations (`associations computed by the real backend are ranked and drawn`)
y los tres de report.spec.ts (`member 5 report reuses the intake dataset and retrieves
report`, `EDA and a complete report coexist with recovery and downloads`,
`default dated payments produce critical evidence and traceable insights`).
No se corrigieron algoritmos ni pantallas de esos módulos. No se presentan las
suites generales como completamente aprobadas.

Las capturas solicitadas se generaron y revisaron visualmente fuera del repositorio:
`quality-screen-desktop.png`, `quality-screen-mobile.png`,
`quality-missing-values.png`, `quality-duplicates.png`, `quality-rules-fail.png`,
`quality-rules-pass.png`, `quality-no-dataset.png`, `quality-expired-dataset.png`,
`quality-error.png`, más `quality-too-large.png`. Se comprobó ausencia de
desbordamiento horizontal de página en 1440/1024/390 px y desplazamiento interno
mediante teclado. No se modificaron backend, IntakeProvider, dependencias o
snapshots HTTP. No se identificaron regresiones nuevas en las validaciones
ejecutadas. Resultados locales, no CI. Cambios sin staging, commit ni publicación,
pendientes de revisión técnica. Alcance exclusivo AUD-014; AUD-018 no iniciado.

## AUD-018 — Ejemplos IQR con registro original

La sección existente «Distribución de columna» de Asociaciones incorpora
«Ejemplos de valores atípicos». Consume `iqr.example_rows` de la herramienta
outliers y muestra el registro (`row_index + 1`), valor e identificación IQR.
Se conservan valores repetidos con sus posiciones distintas y el orden del
servidor. La posición coincide con el preview de AUD-009; no es un identificador
de negocio, índice de Pandas o número de línea física del archivo. Un atípico
puede ser válido y la interfaz no propone eliminarlo automáticamente.

`OutlierExamples` comprueba identidad de la columna, posiciones enteras válidas
dentro del total del dataset, ausencia de posiciones duplicadas y correspondencia
con `iqr.examples`. No busca valores para asignar registros. El contrato nuevo
es opcional: las respuestas antiguas sin referencias muestran que no están
disponibles. Sin atípicos, límite de ejemplos cero, columna insuficiente y
resultados SKIPPED/FAILED tienen mensajes propios, sin ejemplos ficticios.
Errores de red/capacidad permiten reintentar; dataset no disponible ofrece
volver a cargar. Carga, cambios de columna y respuestas stale ocultan referencias
anteriores. useTool ignora éxitos de solicitudes canceladas; el explorador se
reinicia al cambiar dataset. Los gráficos mantienen su comportamiento anterior.

La consulta de outliers espera histograma y descriptivas de la columna y usa la
prioridad más baja de la cola de transporte. Cambiar únicamente la agrupación del boxplot no repite
outliers. Los reintentos no alteran variables ni parámetros de la herramienta.
Los valores conservan la normalización estadística anterior de seis decimales;
un valor no representable como número JSON se presenta explícitamente como tal.
La tabla usa caption, encabezados y región desplazable accesible por teclado,
con diseño adaptable. La pantalla Anomalías se habilitó después con AUD-017.
No hay nueva pantalla, dependencias ni cambios en Analysis, Critic o Reporting.

El detalle de la correspondencia, límites y contrato aditivo está en
[EDA & Association](eda-association.md#aud-018--referencias-originales-en-ejemplos-iqr).
AnalysisResult.result sigue siendo JSON libre: no cambia OpenAPI ni se regenera
el archivo de tipos API. Solo se amplían las formas manuales de exploration.ts.

Para reproducir desde `frontend/`, con Edge y puertos libres:

```powershell
New-Item -ItemType Directory -Path '..\..\aud018-evidence' -Force | Out-Null
$env:PLAYWRIGHT_CHANNEL = 'msedge'
$env:E2E_BACKEND_PORT = '8028'
$env:E2E_FRONTEND_PORT = '5198'
$env:UI_SCREENSHOT_DIR = (Resolve-Path '..\..\aud018-evidence').Path
npm run test:e2e -- e2e/outlier-row-references.spec.ts
npm test -- src/features/associations/OutlierExamples.test.tsx src/features/associations/AssociationsPage.test.tsx --maxWorkers=1
npm run typecheck
npm run build
```

El E2E usa backend real y CSV sintético con 47 registros, nulos previos e
intercalados, atípicos positivos/negativos y repetidos. Contrasta las posiciones
1/44/45 con el preview y exige registros 2/45/46 en pantalla, ausencia de errores
JavaScript y layout sin desbordamiento en 1440/1024/390 px. Otro E2E comprueba el
estado sin atípicos. Los servidores son nuevos, con puertos aislados y sin
reuseExistingServer. Capturas externas: `outliers-original-positions.png`,
`outliers-with-missing-values.png`, `outliers-repeated-values.png`,
`outliers-column-explorer.png`, `outliers-empty-state.png` y `outliers-mobile.png`.
La captura de nulos muestra los registros reales en Dataset; las otras vistas
corresponden al explorador o su estado vacío. No se usan datos privados.

Validación local: 20 pruebas frontend nuevas y las 3 existentes de Associations
aprobadas; suite general con 158 aprobadas y el mismo fallo previo de ReportPage.
Los 2 E2E nuevos pasan con Edge y backend real; la suite E2E tiene 8 aprobados y
los mismos 4 fallos anteriores de Associations/Reporting. TypeScript, build y
ESLint de AUD-018 correctos; ESLint general conserva methodLabel sin uso en
ReportPage.tsx. Arquitectura: 172 archivos correctos y 24 pruebas aprobadas.
La comparación completa de línea base/backend consta en eda-association.md.
No se identificaron regresiones nuevas en las comprobaciones ejecutadas; no
se presentan las suites generales como completamente aprobadas.

## AUD-021 — Contingencia categórica

En Asociaciones, un par de columnas categóricas muestra la tabla de
`chart_contingency` en lugar del antiguo placeholder: conteos con sombreado de un
solo tono (el número siempre visible), totales por fila y columna, y modos «% de
fila», «% de columna» y «% del total»; el margen que no es la base del
porcentaje muestra la distribución global. Las celdas con frecuencia esperada
menor que 5 llevan †. Las advertencias se redactan desde los contadores
estructurados (frecuencias esperadas < 5 y < 1, combinaciones ausentes, filas
excluidas, categorías agrupadas en «Otras») y siempre recuerdan que una
asociación no implica causalidad. `contingency-contract.ts` lee el resultado con
`edaOutcome` (AUD-022): la tabla es de un par, así que solo acepta un resultado
completo y trata uno parcial como no válido. `src/test/contingency-fixture.ts`
contiene el resultado de ejemplo y el e2e usa `tests/fixtures/contingency.csv`.

## AUD-017 — Anomalías

Ruta `/anomalies` («Anomalías» en la barra lateral). Una sola consulta
`outliers` con `variables: []` evalúa todas las columnas numéricas:

- Resumen por columna: observaciones, atípicos IQR y MAD (conteo y porcentaje) y
  estado (muestra pequeña, constante, MAD = 0, IQR = 0) con las mismas reglas que
  el explorador de Asociaciones (`classifyOutliers`). Una columna constante o sin
  evaluar nunca se presenta como «0 atípicos».
- Detalle de la columna elegida: regla y límites IQR (Q1 − k·IQR, Q3 + k·IQR);
  regla MAD (|z robusto| > umbral), mediana, MAD y límites equivalentes en
  unidades de la variable; diagrama de caja (`chart_boxplot`, agrupable).
- Ejemplos IQR y MAD unidos por registro original (`row_index`), con el z robusto
  cuando MAD lo marcó. «Ver registro» consulta bajo demanda la vista previa con
  `offset = row_index` y `limit = 1` y muestra todos los valores de ese registro;
  nunca se infiere un registro a partir del valor. Referencias inválidas o
  ausentes se explican y no se muestran.
- Aviso permanente: un atípico estadístico no es necesariamente un error; no se
  corrige ni se elimina.

Respuestas anteriores sin el detalle MAD siguen funcionando: los límites MAD se
indican como no disponibles y solo se muestran ejemplos IQR.

## AUD-035 — Revisión de afirmaciones estadísticas

Criterio: sección 8 de critic-contract.md (AUD-002). En Asociaciones, Patrones,
Anomalías y la tabla de contingencia se distinguen cuatro niveles:

| Nivel | Qué se afirma | Dónde se dice |
|---|---|---|
| Descripción | Magnitud en estos datos: puntaje 0–1, tamaño del efecto, conteos, centro y dispersión | Aviso de Asociaciones, cabeceras «Puntaje (0–1)» y «Tamaño del efecto», Patrones |
| Asociación | Las columnas varían juntas en este dataset | Aviso de Asociaciones, contingencia |
| Significancia | p ajustado (Benjamini-Hochberg) en el ranking; el resto de p son «sin corregir» | Aviso, heatmap, pares fuera del ranking |
| Causalidad | Nunca se infiere; la robustez se revisa en Relaciones y Hallazgos | Aviso, contingencia, recta de dispersión |

Cambios: un ranking vacío aclara que no demuestra ausencia de asociación; los
p de la matriz y de pruebas individuales se presentan como sin corregir; la
recta de dispersión se presenta como ajuste lineal descriptivo; «Evidencia de
apoyo» pasa a «Otras medidas del mismo par»; los avisos en inglés de las tools
de exploración se traducen solo al mostrarse (`notes.ts`, el original se
conserva si no se reconoce). Atípicos: Anomalías y los ejemplos IQR mantienen
que un atípico no es necesariamente un error y no se corrige ni elimina.

Fuera de alcance (código compartido de reportes): `result_descriptions.py`
escribe «Valor p» sin indicar si está corregido.

## Transporte de herramientas y capacidad del backend

El backend admite `max_concurrent_operations` operaciones a la vez (1 en el perfil
de producción) y un cupo de peticiones por minuto por IP. `api-client` coordina
todas las peticiones del navegador para no producir esos 429 por sí mismo:

- Cola compartida (`request-gate.ts`) con `VITE_MAX_CONCURRENT_REQUESTS`
  peticiones simultáneas, 1 por defecto. Un valor mayor que la capacidad del
  backend solo convierte peticiones en 429.
- Prioridades: ranking, heatmap y Patrones (`PRIORITY.primary`) antes que el
  explorador de columnas; `outliers` (`PRIORITY.secondary`) al final. Las
  peticiones de un mismo render se ordenan juntas antes de enviarse.
- Cancelación: una petición en cola se descarta sin enviarse. Una herramienta ya
  enviada sigue calculándose en el servidor, así que conserva su plaza hasta la
  respuesta (máximo 60 s) aunque su resultado ya no se muestre.
- `useTool` reutiliza resultados `SUCCESS`/`SKIPPED` (deterministas para un
  dataset en memoria; máximo 200) y comparte una sola petición entre llamadas
  idénticas. Volver a una columna o a la página no repite consultas.
- `ANALYSIS_CAPACITY_EXCEEDED`: backoff exponencial con jitter (1, 2, 4 y 8 s,
  nunca menor que `Retry-After`), 5 intentos como máximo; después, error con
  botón Reintentar. Un `Retry-After` mayor de 10 s falla de inmediato.
- `REQUEST_RATE_LIMITED`: se respeta `Retry-After` (hasta 10 s, 2 reintentos).
  Esperas más largas, o un `Retry-After` ilegible, fallan de inmediato, pausan la
  cola y rechazan las peticiones en espera con el mismo mensaje, sin ráfagas.
- Errores de red y resultados `FAILED` no se reintentan automáticamente.

`Retry-After` y `X-Request-ID` se exponen por CORS (`app/api/main.py`); sin ello
el navegador no puede leerlas cuando frontend y backend tienen orígenes
distintos (Vercel y Render). Detrás de un proxy, el cupo por IP puede ser
compartido por todas las personas usuarias (docs/backend-production-readiness.md).

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
`frontend/.env.example` documenta VITE_API_BASE_URL, API_PROXY_TARGET y
VITE_MAX_CONCURRENT_REQUESTS.

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

### Evidencias reproducibles de AUD-010

Desde `frontend/`, con Edge instalado:

```powershell
New-Item -ItemType Directory -Path '..\..\aud010-evidence' -Force | Out-Null
$env:PLAYWRIGHT_CHANNEL = 'msedge'
$env:UI_SCREENSHOT_DIR = (Resolve-Path '..\..\aud010-evidence').Path
npm run test:e2e -- e2e/dataset-preview.spec.ts e2e/intake.spec.ts e2e/dictionary.spec.ts |
    Tee-Object -FilePath '..\..\aud010-e2e-evidence.txt'

npm test -- src/lib/api-client.preview.test.ts src/features/dataset/DatasetPreview.test.tsx --maxWorkers=1 |
    Tee-Object -FilePath '..\..\aud010-tests-evidence.txt'
npm run typecheck
npm run build
```

Playwright inicia el backend y frontend reales con el proxy configurado. Si los
puertos están ocupados, definir `E2E_BACKEND_PORT` y `E2E_FRONTEND_PORT` antes de
ejecutar. La prueba CSV crea 45 filas sintéticas, verifica el GET de AUD-009,
sus parámetros y respuestas, recorre primera/intermedia/última página, vuelve
atrás, cambia tamaño y comprueba que no se solicitan páginas adicionales.
También verifica nulos, ceros iniciales, teclado y anchos 1440/1024/390 px.

La segunda prueba carga un TSV real con enteros mayores al rango seguro y
comprueba la respuesta JSON original y la advertencia de precisión en pantalla.
Los escenarios de desconexión y 413 se inducen mediante interceptación controlada
del navegador; los reintentos vuelven a consultar el backend real. No se presenta
esa interceptación como una respuesta real de tamaño excesivo del servidor.

Las capturas quedan fuera del repositorio: `dataset-screen-1440.png`,
`dataset-screen-390.png`, `dataset-preview-1440.png`, `dataset-preview-1024.png`,
`dataset-preview-390.png`, `dataset-preview-last.png`,
`dataset-preview-network-error.png` y `dataset-preview-too-large.png`.
Las pruebas existentes también generan sus capturas de carga y diccionario.

### Validación de AUD-010 — 17 de octubre de 2026

Worktree aislado `Analista-de-datos-aud010`, rama `feat/aud-010-dataset-screen`,
creado desde `origin/develop` actualizado en
`0fd1dfd2427dc45bb1dd1236f05f2270fe8ffc2d`. Se verificó que incluye los PR #28,
#29 y #33. Los worktrees de AUD-009 y AUD-011 se conservaron. No se hicieron
commits, push, PR, merge ni rebase en esta implementación.

| Verificación | Línea base | Resultado con AUD-010 |
| --- | --- | --- |
| `uv sync --locked` | Correcto | Correcto |
| Comprobador de arquitectura | 167 archivos Python, correcto | Igual |
| Tests de arquitectura | 24 aprobados | 24 aprobados |
| Suite backend completa | 468 aprobados, 4 fallidos | Mismos resultados y fallos |
| Ruff general | 2 errores preexistentes | Mismos errores |
| Ruff format | 257 archivos correctos | Igual |
| `npm ci` | Correcto | Correcto |
| `npm run generate:api` | Preview aún no incluido en los tipos | Ruta, operación y DTO de AUD-009 incorporados por el generador |
| `npm run typecheck` | Correcto | Correcto |
| `npm test` | 35 aprobados, 1 fallo funcional preexistente reconfirmado | 83 aprobados, el mismo fallo |
| Tests específicos nuevos | No existían | 48 aprobados |
| ESLint general | 1 error preexistente | Mismo error |
| ESLint de archivos TypeScript de AUD-010 | No aplica | Correcto |
| `npm run build` | Correcto | Correcto |
| E2E con Edge y backend real | Pruebas existentes de carga/diccionario | 4 aprobados: 2 nuevos de AUD-010 y 2 existentes |
| `git diff --check` | Correcto | Correcto |

Durante las primeras ejecuciones de línea base, antes de implementar, hubo
fallos intermitentes por tiempos de espera en varias pruebas. La repetición
posterior sin modificar pruebas ni aumentar sus tiempos quedó en 35 aprobadas
y el fallo conocido de ReportPage. La ejecución final normal de `npm test`
conservó únicamente ese fallo, con 83 aprobadas. No se cambiaron timeouts ni
configuración del runner para ocultar errores.

Los cuatro fallos backend de ANOVA/Planner/Critic y los dos errores Ruff son los
mismos identificados en la validación de AUD-011 de esta página; se compararon
las salidas de línea base y final. Frontend mantiene el fallo
`null metrics stay unmeasured and no insights are invented` de
`features/reports/ReportPage.test.tsx` y ESLint mantiene `methodLabel` sin uso en
`features/reports/ReportPage.tsx:6`.

Los 48 tests nuevos comprueban transporte tipado y parámetros, validación de
respuestas, relación filas/columnas, paginación, tamaño de página, nulos y tipos,
precisión numérica, carga y errores, reintento, cancelación y respuestas tardías,
StrictMode sin GET duplicado, teclado, reinicio y convivencia con los perfiles
y el diccionario. La prueba E2E comprueba por separado el diseño adaptable.

Se adaptaron únicamente mocks de dos pruebas de integración existentes
(diccionario y reportes) para reconocer el GET nuevo al pasar por Dataset, sin
consumir respuestas reservadas a otras operaciones. Se conservaron sus
comprobaciones funcionales; el fallo previo de ReportPage no fue modificado.
No cambia la implementación de Reporting ni del diccionario.

No se modificaron backend, instantáneas OpenAPI, IntakeProvider, dependencias,
algoritmos, persistencia o despliegue. La comprobación de declaraciones del
archivo generado confirmó que todos los contratos anteriores siguen iguales y
que únicamente se agregan los tres elementos de preview. Capturas de escritorio,
móvil, última página y errores revisadas visualmente fuera del repositorio.
**Regresiones nuevas pendientes: 0.** La suite completa conserva los fallos
preexistentes; AUD-010 está lista para revisión funcional y técnica.

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
