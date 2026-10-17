# Critic e Insight con evidencia calculada

El flujo predeterminado conecta resultados estadísticos exitosos con Evidence, RelationshipAssessment e Insight. Cada evidencia conserva el analysis_id real y cada insight referencia sus evidencias. Pearson, Spearman, ANOVA, chi cuadrado, V de Cramer e identidades aditivas admiten revisión descriptiva. Sin resultados medidos compatibles, Critic e Insight siguen SKIPPED; no se fabrican estadísticas para completar etapas.

potentially_spurious=None significa clasificación indeterminada. SUCCESS significa que hubo una evaluación trazable, no que se demostró robustez, causalidad o ausencia de espuriedad.

## Planificación y herramientas

El registro autoriza nueve herramientas: pearson, spearman, partial_correlation, chi_square, cramers_v, anova_one_way, correlation_without_outliers, analyze_subgroups y additive_identity.

El plan respeta el presupuesto global y las dependencias. Prioriza medidas continuas sobre códigos enteros, excluye constantes numéricas y propone Pearson/Spearman, sensibilidad a outliers y subgrupos cuando hay categorías. La correlación parcial requiere controles explícitos. Una columna total permite proponer una suma de otras dos medidas; la igualdad se calcula sobre datos reales y no se deduce del nombre. No es un detector general de fórmulas.

El diagnóstico de outliers usa límites conjuntos de 1.5 IQR sin modificar el dataset. Si quedan menos de tres casos o alguna variable es constante, devuelve SKIPPED sin coeficientes ficticios. Subgrupos exige al menos dos grupos evaluables, registra exclusiones y limita el análisis a 50 grupos sin muestreo. Los diagnósticos opcionales pueden omitirse aunque las cinco etapas del flujo concluyan SUCCESS.

El intake reconoce fechas %d/%m/%Y y etiquetas explícitas como Nº contribuyente como identificadores discretos. Cantidad contribuyentes sigue siendo una medida. El CSV completo permanece local; los agentes reciben metadatos y resultados.

## Validación

Prueba local con el CSV Alcabala de 36 645 filas: cinco etapas SUCCESS, cinco evidencias y tres insights. Se verificó Impuesto pagado + Intereses pagados = Total pagado en todas las filas con tolerancia absoluta 1e-8. El diagnóstico IQR se omitió porque los intereses retenidos quedaron constantes; el análisis por distrito sí produjo resultados. La clasificación de espuriedad permanece indeterminada.

Se comprobó integridad del archivo original, referencias, recuperación del reporte tras reinicio y coexistencia con EDA. No se incluyen datos privados ni reportes locales en el repositorio.

Regresión: 304 pruebas backend, 16 frontend y cinco E2E con Edge. Ruff, ESLint y compilación frontend satisfactorios.
