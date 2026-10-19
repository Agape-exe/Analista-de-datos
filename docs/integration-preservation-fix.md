# Corrección de integración y conservación del trabajo del equipo

Base: develop `88aebfea974eed23e52eee5de01e28955727b336`, contenido idéntico a main
`7a5af784359d464df5484754ce0f8246cdcf491b`. Fecha: 18/10/2026, America/Lima.

## Objetivo y cambios

Corregir las tres conexiones detectadas en la revisión, conservando los aportes
ya integrados. No se restaura un archivo completo desde una versión antigua ni
se revierte el PR #41.

- **AUD-015:** se recuperan el enlace Configurar Hallazgos y los mensajes de
  capacidades disponibles agregados en `04d3708` y descartados en `d22267b`.
  Permanecen el control de montaje, la cancelación, los archivos del formulario y
  la revisión de contexto. Se aclara que Python procesa el dataset en el servidor.
- **AUD-036:** Association conserva ID real, advertencias y número de pruebas del
  screening en su canal `screening_summary`. Critic consume ese canal para
  adjuntar procedencia por par. No se inserta un resultado de ranking ficticio
  entre los resultados presupuestados de Analysis. Se distingue el ajuste de p
  del screening del retesteo posterior. El lector anterior sigue disponible
  para resultados históricos; un resumen sin identidad verificable no inventa
  procedencia.
- **AUD-038:** se conserva Solicitar correlación parcial como consulta
  exploratoria. Se añade Generar nuevo reporte con este control: una selección
  explícita y validada genera un plan acotado Pearson → correlación parcial,
  evidencia, traza y un nuevo run persistido. El reporte anterior se conserva.

## Contrato aditivo

`POST /analysis/datasets/{dataset_id}` mantiene sus campos previos y admite:

```json
{
  "control_selection": {
    "variables": ["x", "y"],
    "control_variable": "control"
  }
}
```

No se interpretan nombres de columna como instrucciones en lenguaje natural.
Los objetivos y el control deben ser tres columnas numéricas distintas del
dataset solicitado. Una selección inválida se rechaza con 422. No se añaden
herramientas ni algoritmos estadísticos: se reutilizan los existentes.

La selección requiere al menos dos llamadas y respeta el presupuesto y la
muestra mínima del servidor. Si el presupuesto no alcanza, Planner registra
la omisión con las variables y el control; no ejecuta solo Pearson como si la
solicitud estuviera completa. Un baseline fallido/omitido bloquea el paso
dependiente. Los parámetros elegidos permanecen en el plan del reporte y el
resultado conserva su step_id y la referencia desde los eventos.

Los campos nuevos son opcionales. Las snapshots anteriores de OpenAPI no se
reescriben: la prueba de compatibilidad reconoce únicamente esta ampliación
explícita y sigue comparando todas las propiedades anteriores. Los tipos
TypeScript se regeneran con el generador oficial. No hay migración SQL.

## Pruebas y validación local

| Comprobación | Resultado |
| --- | --- |
| Backend completo | 725 pruebas aprobadas, frente a 714 de la base |
| Arquitectura | Checker correcto; 178 archivos de aplicación |
| Frontend completo | 303 pruebas aprobadas en 30 archivos, frente a 301 de la base |
| Ruff check y format | Correctos |
| ESLint y TypeScript/Vite | Correctos; 1661 módulos en build |
| Nuevo E2E con backend real y Edge | Aprobado: control → nuevo reporte → recuperación de ambos runs → procedencia → traza → resultado |

Las once pruebas de integración añadidas cubren procedencia real y persistencia,
control integrado y recuperación tras recrear la app, ocho selecciones inválidas
y presupuesto insuficiente. Se conservan todas las pruebas anteriores. El E2E
nuevo comprueba el flujo real; no simula un reporte que ya traiga las correcciones.

El primer intento E2E utilizó el texto de Hallazgos para buscar el ID en
Relaciones y falló en el selector; se corrigió al texto real Reporte. La prueba
posterior pasó sin modificar el comportamiento de la interfaz para acomodarla.
El montaje local compartido de node_modules emitió un aviso de fuente fuera de
la allowlist de Vite; no se alteró la configuración de producción y no se afirma
una validación de tipografía a partir de ese montaje.

## Evidencias para la entrega

1. En Nuevo análisis: enlace Configurar Hallazgos y estado Disponible en Hallazgos.
2. En Relaciones: selección de un control y botón de generar un nuevo reporte.
3. En el reporte guardado: IDs distintos para el reporte anterior y el nuevo.
4. En Traza: pasos Pearson/parcial, dependencia y enlace al resultado.
5. En las limitaciones de la evaluación: ID, n, método y p ajustado del screening.
6. En GitHub: PR de corrección con los nueve jobs de CI y, después, PR develop→main.

## Alcance pendiente

Esta corrección no declara terminado todo el backlog: la validación real del
despliegue y PostgreSQL de AUD-008 requiere su evidencia y un reinicio autorizado.
Las extensiones P2 continúan fuera de este cambio. Las ampliaciones del backlog
inicial que no estaban en el prompt operativo del integrante 1 deben acordarse
por separado; su código entregado se conserva.
