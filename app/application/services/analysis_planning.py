import re
from dataclasses import dataclass
from itertools import combinations

from app.application.dto.agent import AgentContext
from app.domain.enums.semantic_type import SemanticType
from app.domain.models.analysis import AnalysisPlan, AnalysisStep, Hypothesis, ToolRequest
from app.domain.models.dataset import ColumnProfile

FAST_COLUMN_POOL_SIZE = 4
MAX_COLUMN_POOL_SIZE = 12
CONTROL_PATTERN = re.compile(
    r"(?<!\w)(?:control(?:ar|ando|ado|ada|es)?|ajust(?:ar|ando|ado|ada|e)?)(?!\w)"
)
CONTROL_WINDOW_CHARACTERS = 80


@dataclass(frozen=True)
class PlanningOutcome:
    plan: AnalysisPlan | None
    warnings: list[str]


@dataclass(frozen=True)
class _Candidate:
    family: str
    variables: tuple[str, ...]
    methods: tuple[str, ...]
    statement: str
    control_variable: str | None = None
    priority: int = 0


class DeterministicAnalysisPlanner:
    """Build bounded exploratory plans from serializable dataset metadata only."""

    def plan(self, context: AgentContext) -> PlanningOutcome:
        profile = context.dataset_profile
        dataset_id = context.dataset_id or (profile.dataset_id if profile is not None else None)
        if profile is None or dataset_id is None:
            return PlanningOutcome(None, ["Planner requires dataset metadata and a dataset id."])
        if context.dataset_id is not None and context.dataset_id != profile.dataset_id:
            raise ValueError("Planner received inconsistent dataset identifiers")
        configuration = context.configuration.analysis
        if profile.row_count < configuration.minimum_sample_size:
            return PlanningOutcome(
                None,
                [
                    "Dataset row count is below the configured minimum sample size; "
                    "no executable plan was created."
                ],
            )
        if configuration.max_tool_calls == 0:
            return PlanningOutcome(
                None, ["Tool-call budget is zero; no executable plan was created."]
            )

        typed_columns, warnings = self._typed_columns(context)
        candidates = self._candidates(
            typed_columns,
            context.input.user_question,
            configuration.mode,
            configuration.max_hypotheses,
        )
        if not candidates:
            return PlanningOutcome(
                None, warnings + ["No compatible variables were available for planning."]
            )
        plan = self._bounded_plan(
            candidates,
            dataset_id,
            configuration.max_hypotheses,
            configuration.max_tool_calls,
            configuration.mode,
        )
        if not plan.steps:
            return PlanningOutcome(None, warnings + ["Planning limits prevented executable steps."])
        return PlanningOutcome(plan, warnings)

    def _typed_columns(
        self, context: AgentContext
    ) -> tuple[dict[SemanticType, list[str]], list[str]]:
        assert context.dataset_profile is not None
        dictionary_types = {
            entry.column_name: _semantic_type(entry.semantic_type)
            for entry in (context.data_dictionary.entries if context.data_dictionary else [])
        }
        columns: dict[SemanticType, list[str]] = {
            SemanticType.NUMERIC: [],
            SemanticType.CATEGORICAL: [],
        }
        warnings: list[str] = []
        minimum = context.configuration.analysis.minimum_sample_size
        for profile in sorted(
            context.dataset_profile.columns, key=lambda column: column.column_name
        ):
            semantic = _effective_semantic_type(
                profile, dictionary_types.get(profile.column_name), warnings
            )
            observed = context.dataset_profile.row_count - (profile.missing_count or 0)
            if semantic in columns and observed >= minimum:
                columns[semantic].append(profile.column_name)
        return columns, warnings

    def _candidates(
        self,
        columns: dict[SemanticType, list[str]],
        question: str | None,
        mode: str,
        max_hypotheses: int,
    ) -> list[_Candidate]:
        pool_size = _column_pool_size(mode, max_hypotheses)
        numeric = _prioritized_column_pool(columns[SemanticType.NUMERIC], question, pool_size)
        categorical = _prioritized_column_pool(
            columns[SemanticType.CATEGORICAL], question, pool_size
        )
        candidates: list[_Candidate] = []
        control = _explicit_control(question, numeric)
        for first, second in combinations(numeric, 2):
            variables = (first, second)
            methods = ("pearson", "spearman")
            selected_control = control if control not in variables else None
            if selected_control is not None:
                methods += ("partial_correlation",)
            candidates.append(
                _Candidate(
                    family="numeric",
                    variables=variables,
                    methods=methods,
                    statement=(
                        f"Evaluate whether there is an association between {first} and {second}."
                    ),
                    control_variable=selected_control,
                    priority=_question_priority(question, (*variables, selected_control)),
                )
            )
        for first, second in combinations(categorical, 2):
            variables = (first, second)
            candidates.append(
                _Candidate(
                    family="categorical",
                    variables=variables,
                    methods=("chi_square", "cramers_v"),
                    statement=f"Evaluate whether {first} and {second} are associated.",
                    priority=_question_priority(question, variables),
                )
            )
        for category in categorical:
            for numeric_value in numeric:
                variables = (category, numeric_value)
                candidates.append(
                    _Candidate(
                        family="anova",
                        variables=variables,
                        methods=("anova_one_way",),
                        statement=(
                            f"Evaluate whether {numeric_value} differs across {category} groups."
                        ),
                        priority=_question_priority(question, variables),
                    )
                )
        return sorted(
            candidates,
            key=lambda candidate: (-candidate.priority, candidate.family, candidate.variables),
        )

    def _bounded_plan(
        self,
        candidates: list[_Candidate],
        dataset_id: str,
        max_hypotheses: int,
        max_tool_calls: int,
        mode: str,
    ) -> AnalysisPlan:
        hypotheses: list[Hypothesis] = []
        steps: list[AnalysisStep] = []
        used_families: set[str] = set()
        for candidate in candidates:
            if len(hypotheses) >= max_hypotheses or len(steps) >= max_tool_calls:
                break
            if mode == "fast" and candidate.family in used_families:
                continue
            remaining_calls = max_tool_calls - len(steps)
            methods = candidate.methods[:remaining_calls]
            if not methods:
                break
            hypothesis_id = f"hypothesis-{len(hypotheses) + 1}"
            hypothesis_variables = list(candidate.variables)
            if candidate.control_variable is not None:
                hypothesis_variables.append(candidate.control_variable)
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=hypothesis_id,
                    statement=candidate.statement,
                    variables=hypothesis_variables,
                )
            )
            for method in methods:
                parameters = (
                    {"control_variable": candidate.control_variable}
                    if method == "partial_correlation" and candidate.control_variable is not None
                    else {}
                )
                steps.append(
                    AnalysisStep(
                        step_id=f"step-{len(steps) + 1}-{method}",
                        hypothesis_id=hypothesis_id,
                        request=ToolRequest(
                            dataset_id=dataset_id,
                            method=method,
                            variables=list(candidate.variables),
                            parameters=parameters,
                        ),
                    )
                )
            used_families.add(candidate.family)
        return AnalysisPlan(hypotheses=hypotheses, steps=steps)


def _semantic_type(value: str | None) -> SemanticType | None:
    try:
        return SemanticType(value) if value is not None else None
    except ValueError:
        return None


def _effective_semantic_type(
    column: ColumnProfile,
    dictionary_type: SemanticType | None,
    warnings: list[str],
) -> SemanticType | None:
    profile_type = column.semantic_type
    if profile_type not in (None, SemanticType.UNKNOWN):
        if dictionary_type not in (None, SemanticType.UNKNOWN, profile_type):
            warnings.append(
                f"{column.column_name}: dictionary semantic type conflicts with the observed "
                "profile and was ignored."
            )
        return profile_type
    return dictionary_type


def _question_priority(question: str | None, variables: tuple[str | None, ...]) -> int:
    if not question:
        return 0
    return sum(1 for variable in variables if variable and _mentioned(question, variable))


def _column_pool_size(mode: str, max_hypotheses: int) -> int:
    if mode == "fast":
        return FAST_COLUMN_POOL_SIZE
    return min(MAX_COLUMN_POOL_SIZE, max(FAST_COLUMN_POOL_SIZE, max_hypotheses + 1))


def _prioritized_column_pool(columns: list[str], question: str | None, pool_size: int) -> list[str]:
    """Keep a bounded deterministic pool, with exact question mentions first."""
    mentioned = [column for column in columns if question and _mentioned(question, column)]
    unmentioned = [column for column in columns if column not in mentioned]
    return (mentioned + unmentioned)[:pool_size]


def _explicit_control(question: str | None, numeric_columns: list[str]) -> str | None:
    if not question:
        return None
    control_matches = list(CONTROL_PATTERN.finditer(question.casefold()))
    if not control_matches:
        return None
    candidates = {
        column
        for column in numeric_columns
        if any(
            control.end() <= mention.start()
            and mention.start() - control.end() <= CONTROL_WINDOW_CHARACTERS
            for control in control_matches
            for mention in _column_mentions(question, column)
        )
    }
    return next(iter(candidates)) if len(candidates) == 1 else None


def _mentioned(question: str, column: str) -> bool:
    return bool(_column_mentions(question, column))


def _column_mentions(question: str, column: str) -> list[re.Match[str]]:
    parts = [part for part in re.split(r"[_\s]+", column.casefold()) if part]
    if not parts:
        return []
    pattern = r"(?<!\w)" + r"[\s_]+".join(map(re.escape, parts)) + r"(?!\w)"
    return list(re.finditer(pattern, question.casefold()))
