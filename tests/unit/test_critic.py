from pathlib import Path

from app.modules.critical_review.application.agents.critic import CriticAgent
from app.shared.config.settings import Settings
from app.shared.contracts.agent import AgentContext
from app.shared.contracts.analysis_input import (
    AnalysisInput,
    resolve_configuration,
)
from app.shared.domain.enums.statuses import AnalysisStatus
from app.shared.domain.models.analysis import (
    AnalysisResult,
    AssociationResult,
)


class MustNotCallLLM:
    async def generate(self, request):
        raise AssertionError("El Critic no debe llamar al LLM en esta prueba")


# PRUEBA 1: Detectar una relación potencialmente espuria
async def test_critic_detects_potentially_spurious_relationship():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Simular una correlación de Pearson
    asociacion = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.81,
        p_value=0.001,
    )

    # Simular una correlación parcial controlando "campaña"
    analisis = AnalysisResult(
        method="partial_correlation",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.16,
        sample_size=100,
        metadata={"control_variables": ["campaña"]},
    )

    # Construir el contexto
    context = AgentContext(
        run_id="test-critic-001",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[asociacion],
        analysis_results=[analisis],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar el resultado
    assert resultado.status == AnalysisStatus.SUCCESS
    assert len(resultado.update.evidence) == 1
    assert len(resultado.update.relationship_assessments) == 1

    evaluacion = resultado.update.relationship_assessments[0]

    assert evaluacion.potentially_spurious is True
    assert evaluacion.variables == ["publicidad", "ventas"]
    assert evaluacion.evidence_ids == [resultado.update.evidence[0].evidence_id]

    # Verificar que la evidencia se generó
    evidencia = resultado.update.evidence[0]
    assert evidencia.analysis_id == analisis.analysis_id
    assert "campaña" in evidencia.description


# PRUEBA 2: Verificar qué ocurre cuando falta evidencia
async def test_critic_skips_when_partial_correlation_is_missing():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Simular una correlación de Pearson
    asociacion = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.81,
        p_value=0.001,
    )

    # Construir contexto sin correlación parcial
    context = AgentContext(
        run_id="test-critic-002",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[asociacion],
        analysis_results=[],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar que no invente una conclusión
    assert resultado.status == AnalysisStatus.SKIPPED
    assert resultado.update.relationship_assessments is None
    assert resultado.warnings


# PRUEBA 3: Rechazar una correlación parcial sin variable de control
async def test_critic_rejects_missing_control_variables():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Simular la correlación original
    asociacion = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.81,
        p_value=0.001,
    )

    # Correlación parcial sin identificar la variable de control
    analisis = AnalysisResult(
        method="partial_correlation",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.16,
        sample_size=100,
        metadata={},
    )

    # Construir el contexto
    context = AgentContext(
        run_id="test-critic-003",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[asociacion],
        analysis_results=[analisis],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar que rechaza la evidencia incompleta
    assert resultado.status == AnalysisStatus.SKIPPED
    assert resultado.update.evidence is None
    assert resultado.update.relationship_assessments is None
    assert resultado.warnings


# PRUEBA 4: Rechazar una variable de control incorrecta
async def test_critic_rejects_control_variable_equal_to_analyzed_variable():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Simular la correlación original
    asociacion = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.81,
        p_value=0.001,
    )

    # Control incorrecto: publicidad es una variable analizada
    analisis = AnalysisResult(
        method="partial_correlation",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.16,
        sample_size=100,
        metadata={"control_variables": ["publicidad"]},
    )

    # Construir el contexto
    context = AgentContext(
        run_id="test-critic-004",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[asociacion],
        analysis_results=[analisis],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar que rechaza el control incorrecto
    assert resultado.status == AnalysisStatus.SKIPPED
    assert resultado.update.evidence is None
    assert resultado.update.relationship_assessments is None
    assert resultado.warnings

    # AUD-033: Verificar el motivo del control inválido
    assert any("coincide con una variable analizada" in warning for warning in resultado.warnings)


# PRUEBA 5: Detectar un cambio de signo en la correlación
async def test_critic_detects_sign_change():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Simular una correlación original positiva
    asociacion = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.75,
        p_value=0.001,
    )

    # Simular una correlación parcial negativa
    # Controlando la variable "campaña"
    analisis = AnalysisResult(
        method="partial_correlation",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=-0.40,
        sample_size=100,
        metadata={"control_variables": ["campaña"]},
    )

    # Construir el contexto del agente
    context = AgentContext(
        run_id="test-critic-005",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[asociacion],
        analysis_results=[analisis],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar que el análisis fue realizado
    assert resultado.status == AnalysisStatus.SUCCESS

    # Verificar que se generaron evidencias y evaluaciones
    assert len(resultado.update.evidence) == 1
    assert len(resultado.update.relationship_assessments) == 1

    # Comprobar que se detectó el cambio de signo
    evidencia = resultado.update.evidence[0]

    assert "Cambio de signo: True" in evidencia.description
    assert evidencia.analysis_id == analisis.analysis_id

    # Comprobar que se generó una alerta estadística
    evaluacion = resultado.update.relationship_assessments[0]

    assert evaluacion.potentially_spurious is True
    assert evaluacion.variables == ["publicidad", "ventas"]
    assert evaluacion.evidence_ids == [evidencia.evidence_id]
    assert evaluacion.rationale


# PRUEBA 6: Evaluar una correlación que permanece estable
async def test_critic_detects_stable_relationship():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Correlación original
    asociacion = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.81,
        p_value=0.001,
    )

    # Correlación parcial con poco debilitamiento
    analisis = AnalysisResult(
        method="partial_correlation",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.76,
        sample_size=100,
        metadata={"control_variables": ["campaña"]},
    )

    # Construir el contexto
    context = AgentContext(
        run_id="test-critic-006",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[asociacion],
        analysis_results=[analisis],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar ejecución exitosa
    assert resultado.status == AnalysisStatus.SUCCESS

    # Verificar que generó evidencia
    assert len(resultado.update.evidence) == 1
    assert len(resultado.update.relationship_assessments) == 1

    evidencia = resultado.update.evidence[0]
    assert "Cambio de signo: False" in evidencia.description
    assert evidencia.analysis_id == analisis.analysis_id

    # Verificar que no se activó la alerta
    evaluacion = resultado.update.relationship_assessments[0]

    assert evaluacion.potentially_spurious is None
    assert evaluacion.evidence_ids == [evidencia.evidence_id]
    assert evaluacion.rationale


# PRUEBA 7: Verificar la comparación Pearson vs Spearman
async def test_critic_compares_pearson_and_spearman():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Simular una correlación Pearson
    pearson = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.81,
        p_value=0.001,
    )

    # Simular una correlación Spearman
    spearman = AssociationResult(
        method="spearman",
        variables=["publicidad", "ventas"],
        strength=0.78,
        p_value=0.002,
    )

    # Simular una correlación parcial controlando campaña
    analisis = AnalysisResult(
        method="partial_correlation",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.16,
        sample_size=100,
        metadata={"control_variables": ["campaña"]},
    )

    # Construir el contexto del agente
    context = AgentContext(
        run_id="test-critic-007",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[pearson, spearman],
        analysis_results=[analisis],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar ejecución correcta
    assert resultado.status == AnalysisStatus.SUCCESS

    # Verificar que se generó evidencia
    assert len(resultado.update.evidence) == 1
    assert len(resultado.update.relationship_assessments) == 1

    evidencia = resultado.update.evidence[0]

    # Comprobar los valores de las correlaciones
    assert "Correlación original: 0.810" in evidencia.description
    assert "Spearman: 0.780" in evidencia.description

    # Verificar la diferencia entre Pearson y Spearman
    assert "Diferencia Pearson-Spearman: 0.030" in evidencia.description

    # Verificar la evaluación final
    evaluacion = resultado.update.relationship_assessments[0]

    assert evaluacion.potentially_spurious is True
    assert evaluacion.variables == ["publicidad", "ventas"]
    assert evaluacion.evidence_ids == [evidencia.evidence_id]


# PRUEBA 8: Registrar una discrepancia elevada entre Pearson y Spearman
async def test_critic_detects_high_correlation_disagreement():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Correlación Pearson elevada
    pearson = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.85,
        p_value=0.001,
    )

    # Correlación Spearman considerablemente menor
    spearman = AssociationResult(
        method="spearman",
        variables=["publicidad", "ventas"],
        strength=0.25,
        p_value=0.02,
    )

    # Correlación parcial relativamente estable
    analisis = AnalysisResult(
        method="partial_correlation",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.80,
        sample_size=100,
        metadata={"control_variables": ["campaña"]},
    )

    # Preparar el contexto
    context = AgentContext(
        run_id="test-critic-008",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[pearson, spearman],
        analysis_results=[analisis],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar ejecución
    assert resultado.status == AnalysisStatus.SUCCESS

    # Comprobar la diferencia Pearson-Spearman
    assert len(resultado.update.evidence) == 1
    evidencia = resultado.update.evidence[0]

    assert "Spearman: 0.250" in evidencia.description
    assert "Diferencia Pearson-Spearman: 0.600" in evidencia.description

    # La discrepancia todavía no activa una alerta independiente
    evaluacion = resultado.update.relationship_assessments[0]

    assert evaluacion.potentially_spurious is None
    assert evaluacion.evidence_ids == [evidencia.evidence_id]


# PRUEBA 9: Evaluar el impacto de los outliers
async def test_critic_evaluates_outlier_impact():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Correlación original
    asociacion = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.85,
        p_value=0.001,
    )

    # Correlación después de excluir outliers
    analisis = AnalysisResult(
        method="correlation_without_outliers",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.30,
        sample_size=95,
        metadata={
            "outlier_method": "IQR",
            "removed_count": 5,
        },
    )

    # Construir el contexto del Critic
    context = AgentContext(
        run_id="test-critic-009",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[asociacion],
        analysis_results=[analisis],
    )

    # Ejecutar el agente
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar ejecución exitosa
    assert resultado.status == AnalysisStatus.SUCCESS

    # Verificar la evidencia estadística
    assert len(resultado.update.evidence) == 1

    evidencia = resultado.update.evidence[0]

    assert "Correlación original: 0.850" in evidencia.description
    assert "Correlación sin outliers: 0.300" in evidencia.description
    assert "Impacto absoluto: 0.550" in evidencia.description
    assert "Método de detección: IQR" in evidencia.description
    assert "Observaciones eliminadas: 5" in evidencia.description
    assert "Impacto elevado: True" in evidencia.description

    # Verificar la evaluación
    assert len(resultado.update.relationship_assessments) == 1

    evaluacion = resultado.update.relationship_assessments[0]

    # El impacto por sí solo no demuestra espuriedad
    assert evaluacion.potentially_spurious is None

    # Debe advertir sobre la sensibilidad a outliers
    assert "sensibilidad elevada" in evaluacion.rationale

    # Verificar trazabilidad de la evidencia
    assert evaluacion.evidence_ids == [evidencia.evidence_id]
    assert evidencia.analysis_id == analisis.analysis_id


# PRUEBA 10: Evaluar diferencias entre subgrupos
async def test_critic_evaluates_subgroup_heterogeneity():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Correlación original encontrada por el Analyst
    asociacion = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.70,
        p_value=0.001,
    )

    # Simular resultados estadísticos por regiones
    analisis = AnalysisResult(
        method="analyze_subgroups",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        result={
            "group_by": "region",
            "groups": [
                {
                    "group": "Norte",
                    "correlation": 0.80,
                    "sample_size": 50,
                },
                {
                    "group": "Sur",
                    "correlation": -0.40,
                    "sample_size": 45,
                },
            ],
        },
    )

    # Construir el contexto
    context = AgentContext(
        run_id="test-critic-010",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[asociacion],
        analysis_results=[analisis],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar ejecución correcta
    assert resultado.status == AnalysisStatus.SUCCESS

    # Verificar evidencia
    assert len(resultado.update.evidence) == 1
    evidencia = resultado.update.evidence[0]

    assert "Variable de agrupación: region" in evidencia.description
    assert "Heterogeneidad: 1.200" in evidencia.description
    assert "Alerta de heterogeneidad: True" in evidencia.description
    assert evidencia.analysis_id == analisis.analysis_id

    # Verificar evaluación
    assert len(resultado.update.relationship_assessments) == 1
    evaluacion = resultado.update.relationship_assessments[0]

    assert evaluacion.potentially_spurious is None
    assert "heterogeneidad elevada" in evaluacion.rationale
    assert evaluacion.evidence_ids == [evidencia.evidence_id]


# PRUEBA 11: Evaluar la variación temporal de correlaciones
async def test_critic_evaluates_temporal_variation():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    # Correlación original encontrada
    asociacion = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.80,
        p_value=0.001,
    )

    # Simular correlaciones de tres periodos
    analisis = AnalysisResult(
        method="analyze_temporal",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        result={
            "time_column": "mes",
            "periods": [
                {
                    "period": "2026-01",
                    "correlation": 0.80,
                    "sample_size": 50,
                },
                {
                    "period": "2026-02",
                    "correlation": 0.75,
                    "sample_size": 48,
                },
                {
                    "period": "2026-03",
                    "correlation": -0.30,
                    "sample_size": 52,
                },
            ],
        },
    )

    # Construir el contexto
    context = AgentContext(
        run_id="test-critic-011",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[asociacion],
        analysis_results=[analisis],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Verificar ejecución exitosa
    assert resultado.status == AnalysisStatus.SUCCESS

    # Verificar evidencia temporal
    assert len(resultado.update.evidence) == 1
    evidencia = resultado.update.evidence[0]

    assert "Variable temporal: mes" in evidencia.description
    assert "Variación temporal máxima: 1.050" in evidencia.description
    assert "Alerta temporal: True" in evidencia.description
    assert evidencia.analysis_id == analisis.analysis_id

    # Verificar evaluación
    assert len(resultado.update.relationship_assessments) == 1
    evaluacion = resultado.update.relationship_assessments[0]

    # La variación temporal no demuestra espuriedad
    assert evaluacion.potentially_spurious is None

    # Debe registrar la advertencia
    assert "inestabilidad temporal elevada" in evaluacion.rationale

    # Verificar trazabilidad
    assert evaluacion.evidence_ids == [evidencia.evidence_id]


# PRUEBA 12: Evitar falsas alertas por cambios de signo mínimos
async def test_critic_ignores_tiny_sign_change():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})

    settings = Settings(_env_file=None)

    asociacion = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.02,
        p_value=0.80,
    )

    analisis = AnalysisResult(
        method="partial_correlation",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=-0.02,
        sample_size=100,
        metadata={"control_variables": ["campaña"]},
    )

    context = AgentContext(
        run_id="test-critic-012",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[asociacion],
        analysis_results=[analisis],
    )

    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    assert resultado.status == AnalysisStatus.SUCCESS

    evidencia = resultado.update.evidence[0]
    assert "Cambio de signo: True" in evidencia.description

    evaluacion = resultado.update.relationship_assessments[0]

    # La inversión cercana a cero no activa la alerta
    assert evaluacion.potentially_spurious is None


# PRUEBA 13: Evaluar múltiples evidencias de robustez
async def test_critic_combines_robustness_evidence():
    path = Path(__file__).parents[1] / "fixtures" / "sample.csv"

    entrada = AnalysisInput(source={"kind": "csv", "path": path})
    settings = Settings(_env_file=None)

    # Correlación original
    pearson = AssociationResult(
        method="pearson",
        variables=["publicidad", "ventas"],
        strength=0.81,
        p_value=0.001,
    )

    # 1. Correlación parcial
    parcial = AnalysisResult(
        method="partial_correlation",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.16,
        sample_size=100,
        metadata={"control_variables": ["campaña"]},
    )

    # 2. Correlación sin outliers
    outliers = AnalysisResult(
        method="correlation_without_outliers",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.30,
        sample_size=95,
        metadata={
            "outlier_method": "IQR",
            "removed_count": 5,
        },
    )

    # 3. Análisis por subgrupos
    subgrupos = AnalysisResult(
        method="analyze_subgroups",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        result={
            "group_by": "region",
            "groups": [
                {
                    "group": "Norte",
                    "correlation": 0.80,
                    "sample_size": 50,
                },
                {
                    "group": "Sur",
                    "correlation": -0.40,
                    "sample_size": 45,
                },
            ],
        },
    )

    # 4. Análisis temporal
    temporal = AnalysisResult(
        method="analyze_temporal",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        result={
            "time_column": "mes",
            "periods": [
                {
                    "period": "2026-01",
                    "correlation": 0.80,
                    "sample_size": 50,
                },
                {
                    "period": "2026-02",
                    "correlation": 0.75,
                    "sample_size": 48,
                },
                {
                    "period": "2026-03",
                    "correlation": -0.30,
                    "sample_size": 52,
                },
            ],
        },
    )

    # Construir el contexto completo
    context = AgentContext(
        run_id="test-critic-013",
        input=entrada,
        configuration=resolve_configuration(settings, entrada.configuration),
        associations=[pearson],
        analysis_results=[
            parcial,
            outliers,
            subgrupos,
            temporal,
        ],
    )

    # Ejecutar el Critic
    critic = CriticAgent(MustNotCallLLM())
    resultado = await critic.run(context)

    # Comprobar ejecución
    assert resultado.status == AnalysisStatus.SUCCESS

    # Debe generar cuatro evidencias
    assert len(resultado.update.evidence) == 4

    # Todas deben corresponder a los análisis recibidos
    analysis_ids = {evidencia.analysis_id for evidencia in resultado.update.evidence}

    assert analysis_ids == {
        parcial.analysis_id,
        outliers.analysis_id,
        subgrupos.analysis_id,
        temporal.analysis_id,
    }

    # Debe generar una sola evaluación de la relación
    assert len(resultado.update.relationship_assessments) == 1

    evaluacion = resultado.update.relationship_assessments[0]

    # Verificar vinculación de todas las evidencias
    evidence_ids = {evidencia.evidence_id for evidencia in resultado.update.evidence}

    assert set(evaluacion.evidence_ids) == evidence_ids

    # La correlación parcial activa la alerta
    assert evaluacion.potentially_spurious is True

    # Verificar que incluye todas las advertencias
    assert "debilitamiento importante" in evaluacion.rationale
    assert "sensibilidad elevada" in evaluacion.rationale
    assert "heterogeneidad elevada" in evaluacion.rationale
    assert "inestabilidad temporal elevada" in evaluacion.rationale


def _critic_context(results: list[AnalysisResult]) -> AgentContext:
    entrada = AnalysisInput(
        source={"kind": "csv", "path": Path(__file__).parents[1] / "fixtures" / "sample.csv"}
    )
    return AgentContext(
        run_id="test-critic-preliminar",
        input=entrada,
        configuration=resolve_configuration(Settings(_env_file=None), entrada.configuration),
        analysis_results=results,
    )


async def test_critic_reviews_measured_results_as_indeterminate():
    pearson = AnalysisResult(
        method="pearson",
        variables=["ingreso", "gasto"],
        status=AnalysisStatus.SUCCESS,
        result={"correlation": 0.8},
        effect_size=0.8,
        p_value=0.001,
        sample_size=100,
    )

    spearman = pearson.model_copy(update={"analysis_id": "spearman-1", "method": "spearman"})

    chi = AnalysisResult(
        method="chi_square",
        variables=["region", "segmento"],
        status=AnalysisStatus.SUCCESS,
        result={"chi_square": 1.2},
        p_value=0.4,
        sample_size=100,
    )

    resultado = await CriticAgent(MustNotCallLLM()).run(_critic_context([pearson, spearman, chi]))

    assert resultado.status == AnalysisStatus.SUCCESS

    # Tres resultados estadísticos deben generar tres evidencias.
    assert len(resultado.update.evidence) == 3

    # Se genera una evaluación por cada par de variables.
    assert len(resultado.update.relationship_assessments) == 2

    assert {evidencia.analysis_id for evidencia in resultado.update.evidence} == {
        pearson.analysis_id,
        spearman.analysis_id,
        chi.analysis_id,
    }

    # La clasificación permanece indeterminada.
    for evaluacion in resultado.update.relationship_assessments:
        assert evaluacion.potentially_spurious is None
        assert evaluacion.evidence_ids
        assert "indeterminad" in evaluacion.rationale.lower()


async def test_critic_reviews_non_significant_measured_result():
    no_significativo = AnalysisResult(
        method="pearson",
        variables=["ingreso", "ruido"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.05,
        p_value=0.6,
        sample_size=100,
    )

    resultado = await CriticAgent(MustNotCallLLM()).run(_critic_context([no_significativo]))

    # Un resultado medido puede revisarse descriptivamente
    # aunque su valor p no sea significativo.
    assert resultado.status == AnalysisStatus.SUCCESS

    assert len(resultado.update.evidence) == 1
    assert len(resultado.update.relationship_assessments) == 1

    evidencia = resultado.update.evidence[0]
    evaluacion = resultado.update.relationship_assessments[0]

    assert evidencia.analysis_id == no_significativo.analysis_id
    assert evaluacion.evidence_ids == [evidencia.evidence_id]
    assert evaluacion.potentially_spurious is None


# AUD-002: Revisar resultados medidos aunque no exista valor p
async def test_critic_reviews_measured_result_without_p_value():
    pearson = AnalysisResult(
        method="pearson",
        variables=["ingreso", "gasto"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.70,
        sample_size=100,
        p_value=None,
    )

    resultado = await CriticAgent(MustNotCallLLM()).run(_critic_context([pearson]))

    assert resultado.status == AnalysisStatus.SUCCESS
    assert len(resultado.update.evidence) == 1
    assert len(resultado.update.relationship_assessments) == 1

    evidencia = resultado.update.evidence[0]
    evaluacion = resultado.update.relationship_assessments[0]

    assert evidencia.analysis_id == pearson.analysis_id
    assert evaluacion.evidence_ids == [evidencia.evidence_id]
    assert evaluacion.potentially_spurious is None


# AUD-002: No generar evidencia si falta el cálculo estadístico
async def test_critic_skips_significant_result_without_coefficient():
    pearson = AnalysisResult(
        method="pearson",
        variables=["ingreso", "gasto"],
        status=AnalysisStatus.SUCCESS,
        effect_size=None,
        p_value=0.001,
        sample_size=100,
    )

    resultado = await CriticAgent(MustNotCallLLM()).run(_critic_context([pearson]))

    assert resultado.status == AnalysisStatus.SKIPPED
    assert resultado.update.evidence is None
    assert resultado.update.relationship_assessments is None
    assert resultado.warnings


# AUD-033: Conservar el motivo de un análisis omitido
async def test_critic_preserves_skipped_analysis_reason():
    omitted = AnalysisResult(
        analysis_id="partial-omitted-001",
        method="partial_correlation",
        variables=["ingreso", "gasto"],
        status=AnalysisStatus.SKIPPED,
        warnings=["No hay suficientes observaciones para el cálculo."],
    )

    resultado = await CriticAgent(MustNotCallLLM()).run(_critic_context([omitted]))

    assert resultado.status == AnalysisStatus.SKIPPED
    assert resultado.update.evidence is None
    assert resultado.update.relationship_assessments is None
    assert any(
        "partial-omitted-001" in warning and "No hay suficientes observaciones" in warning
        for warning in resultado.warnings
    )


# AUD-033: Conservar advertencias incluso cuando hay resultados válidos
async def test_critic_preserves_warnings_with_successful_results():
    pearson = AnalysisResult(
        analysis_id="pearson-valid-001",
        method="pearson",
        variables=["ingreso", "gasto"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.75,
        sample_size=100,
    )

    omitted = AnalysisResult(
        analysis_id="partial-omitted-002",
        method="partial_correlation",
        variables=["ingreso", "gasto"],
        status=AnalysisStatus.SKIPPED,
        warnings=["La variable de control no es evaluable."],
    )

    resultado = await CriticAgent(MustNotCallLLM()).run(_critic_context([pearson, omitted]))

    assert resultado.status == AnalysisStatus.SUCCESS

    assert {evidencia.analysis_id for evidencia in resultado.update.evidence} == {
        "pearson-valid-001"
    }

    assert any(
        "partial-omitted-002" in warning and "variable de control" in warning
        for warning in resultado.warnings
    )


# AUD-033: Conservar el motivo de un análisis fallido
async def test_critic_preserves_failed_analysis_reason():
    failed = AnalysisResult(
        analysis_id="partial-failed-001",
        method="partial_correlation",
        variables=["ingreso", "gasto"],
        status=AnalysisStatus.FAILED,
        warnings=["Error durante el cálculo de correlación parcial."],
    )

    resultado = await CriticAgent(MustNotCallLLM()).run(_critic_context([failed]))

    # Sin cálculos válidos, Critic debe omitir la evaluación.
    assert resultado.status == AnalysisStatus.SKIPPED

    # No debe fabricar evidencias ni evaluaciones.
    assert resultado.update.evidence is None
    assert resultado.update.relationship_assessments is None

    # Debe conservar la identificación y el motivo del fallo.
    assert any(
        "partial-failed-001" in warning and "Error durante el cálculo" in warning
        for warning in resultado.warnings
    )


# AUD-036: Verificar la integración de la procedencia con Critic
async def test_critic_preserves_screening_provenance():
    screening = AnalysisResult(
        analysis_id="screening-001",
        method="relationship_ranking",
        status=AnalysisStatus.SUCCESS,
        result={
            "top_relationships": [
                {
                    "x": "publicidad",
                    "y": "ventas",
                    "method": "pearson",
                    "score": 0.85,
                    "strength": 0.80,
                    "p_value": 0.001,
                    "adjusted_p_value": 0.008,
                    "sample_size": 100,
                    "warnings": ["Posible influencia de outliers."],
                    "supporting": [
                        {
                            "method": "spearman",
                            "variables": ["publicidad", "ventas"],
                            "strength": 0.75,
                            "p_value": 0.002,
                        }
                    ],
                }
            ],
            "correction": "benjamini-hochberg",
            "significance_level": 0.05,
        },
    )

    pearson = AnalysisResult(
        analysis_id="pearson-001",
        method="pearson",
        variables=["publicidad", "ventas"],
        status=AnalysisStatus.SUCCESS,
        effect_size=0.80,
        result={"correlation": 0.80},
        sample_size=100,
        p_value=0.001,
    )

    resultado = await CriticAgent(MustNotCallLLM()).run(_critic_context([screening, pearson]))

    assert resultado.status == AnalysisStatus.SUCCESS

    evaluacion = resultado.update.relationship_assessments[0]

    # La clasificación continúa siendo indeterminada
    assert evaluacion.potentially_spurious is None

    # La evaluación conserva la procedencia del screening
    limitaciones = " ".join(evaluacion.limitations)

    assert "screening-001" in limitaciones
    assert "pearson" in limitaciones
    assert "n=100" in limitaciones
    assert "p crudo=0.001" in limitaciones
    assert "p ajustado=0.008" in limitaciones
    assert "benjamini-hochberg" in limitaciones
    assert "spearman" in limitaciones
    assert "Posible influencia de outliers" in limitaciones

    # No crear evidencia ficticia del screening
    assert {evidencia.analysis_id for evidencia in resultado.update.evidence} == {"pearson-001"}
