# Evaluación del módulo del integrante 5

## Detección de relaciones potencialmente espurias

La unidad evaluada es una pareja de variables. El ground truth debe definir todas
las parejas del universo controlado, con etiquetas positivas y negativas explícitas.
No se deduce que una pareja no listada sea negativa. El orden A–B / B–A se normaliza.
Se rechazan parejas duplicadas y predicciones fuera del universo.

GroundTruth.relationship_labels contiene RelationshipLabel(variables,
potentially_spurious). El campo original spurious_relationships se conserva por
compatibilidad, pero por sí solo no permite una matriz de confusión completa.

La función evaluate_detection mide detección binaria:

- Detectada: decisión True.
- No detectada: False, None o pareja ausente.
- TP: positiva de ground truth detectada.
- FP: negativa de ground truth detectada.
- FN: positiva no detectada, incluidas abstenciones/omisiones.
- TN: negativa no detectada. No significa que el sistema la haya declarado robusta.

Precision = TP / (TP + FP).
Recall = TP / (TP + FN).
F1 = 2 TP / (2 TP + FP + FN).
False Positive Rate = FP / (FP + TN).

Denominadores cero producen None, no puntuaciones inventadas. F1 puede ser 0 cuando
hay positivos esperados y ninguna detección. El resultado incluye coverage y
abstentions_or_missing: no interpretar buen desempeño de no-detección sin revisar
cobertura y recall. Esta política mide detección, no exactitud de toda clasificación.

## Benchmarks

BenchmarkRunner ejecuta un workflow inyectado, conserva su reporte y registra
ExperimentRun en JSON. Solo calcula calidad de detección si el reporte es SUCCESS
y existe relationship_labels. SKIPPED y FAILED conservan calidad sin medir.
Los tiempos y llamadas siguen siendo válidos para esas ejecuciones.

Una lista de etiquetas correcta, por sí sola, no certifica las causas de relaciones
espurias. Usar casos controlados, justificar su generación y acordar sus etiquetas
con el equipo. Registrar procedencia, semilla, tamaño, versión del dataset, modelo,
prompt, temperatura, código y configuración. Los metadatos se pasan en configuration.

El ejemplo de demo contiene valores predefinidos. Su puntuación solo prueba el
cálculo de métricas; no valida el algoritmo crítico ni permite presentar F1 real.

## Repetibilidad

RepeatabilityRunner repite el mismo BenchmarkDataset con igual configuración, guarda
cada ExperimentRun y un ConsistencyRun. Requiere al menos dos ejecuciones.
conclusion_agreement compara decisiones exactas en parejas presentes en todas las
corridas. None no equivale a False. El acuerdo se mide únicamente cuando ambas
corridas clasifican la pareja. decision_coverage expresa el porcentaje de comparaciones
con decisiones; abstention_agreement reporta abstenciones conjuntas separadamente.
No se interpreta dos abstenciones como dos conclusiones coincidentes.
Reportes incompletos no reciben un valor ficticio de consistencia.

No se calcula aún similitud semántica del texto, consistencia de hipótesis o selección
de herramientas. Sus campos permanecen None hasta implementar protocolos adecuados.

## Tiempos y llamadas

Los tiempos se miden en segundos con perf_counter. El workflow conserva tiempo total,
duración de etapas y tiempo hasta disponer del primer insight; no es streaming al
navegador. FinalizeAnalysis identifica si mide solo finalización o suma un tiempo
previo suministrado. No comparar esos alcances como si fueran idénticos.

Wrappers de proveedor y herramientas registran llamadas intentadas, fallidas y duración.
Tokens ausentes permanecen sin medir. El número de iteraciones del grafo lineal original
se conserva en 1; deberá sustituirse por el contador del ciclo real del integrante 3.

## Evaluación humana

default_rubric devuelve seis criterios con anclas 1, 3 y 5: correctitud, relevancia,
claridad, evidencia, utilidad y prudencia causal. Las puntuaciones 2 y 4 son intermedias.
HumanInsightEvaluation exige los seis criterios una vez y justificación por criterio.
Conservar evaluator_id, run_id, insight_id y versión de rúbrica. Preferentemente utilizar
más de un evaluador y resolver discrepancias; no convertir la autoevaluación del LLM
en ground truth.
