import re
from dataclasses import dataclass, replace
from itertools import combinations

from app.application.dto.agent import AgentContext
from app.application.dto.planning import AnovaGroupSummaries, AnovaGroupSummary
from app.domain.enums.semantic_type import SemanticType
from app.domain.models.analysis import (
    AnalysisPlan,
    AnalysisStep,
    AssociationResult,
    Hypothesis,
    ToolRequest,
)
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
    group_by: str | None = None
    priority: int = 0
    screening_rank: int | None = None


class DeterministicAnalysisPlanner:
    """Build bounded exploratory plans from serializable dataset metadata only."""

    def plan(
        self, context: AgentContext, anova_groups: AnovaGroupSummaries | None = None
    ) -> PlanningOutcome:
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
            _screening_ranks(context.associations),
        )
        supported: list[_Candidate] = []
        profiles = {column.column_name: column for column in profile.columns}
        for candidate in candidates:
            if candidate.family == "anova":
                category, numeric = candidate.variables
                summary = (anova_groups or {}).get((category, numeric))
                reason = _anova_sample_problem(
                    profiles[category], profiles[numeric], profile.row_count, summary
                )
                if reason is not None:
                    warnings.append(f"ANOVA omitted for '{category}' and '{numeric}': {reason}")
                    continue
            supported.append(candidate)
        candidates = supported
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

    def anova_pairs(self, context: AgentContext) -> list[tuple[str, str]]:
        """List only bounded, metadata-compatible pairs for local count summaries."""
        profile = context.dataset_profile
        if (
            profile is None
            or profile.row_count < context.configuration.analysis.minimum_sample_size
            or context.configuration.analysis.max_tool_calls == 0
        ):
            return []
        columns, _ = self._typed_columns(context)
        profiles = {column.column_name: column for column in profile.columns}
        pairs: list[tuple[str, str]] = []
        for candidate in self._candidates(
            columns,
            context.input.user_question,
            context.configuration.analysis.mode,
            context.configuration.analysis.max_hypotheses,
            _screening_ranks(context.associations),
        ):
            if candidate.family != "anova":
                continue
            category, numeric = candidate.variables
            if (
                _anova_sample_problem(profiles[category], profiles[numeric], profile.row_count)
                is None
            ):
                pairs.append((category, numeric))
        return pairs

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
            if semantic == SemanticType.NUMERIC and profile.unique_count in (0, 1):
                warnings.append(f"Planner omitted constant numeric column '{profile.column_name}'.")
                continue
            observed = context.dataset_profile.row_count - (profile.missing_count or 0)
            if semantic in columns and observed >= minimum:
                columns[semantic].append(profile.column_name)
        profiles = {column.column_name: column for column in context.dataset_profile.columns}
        columns[SemanticType.NUMERIC].sort(
            key=lambda name: (
                not (
                    "float" in profiles[name].data_type.casefold()
                    or profiles[name].data_type.casefold() in {"number", "double"}
                )
            )
        )
        return columns, warnings

    def _candidates(
        self,
        columns: dict[SemanticType, list[str]],
        question: str | None,
        mode: str,
        max_hypotheses: int,
        screening: dict[frozenset[str], int] | None = None,
    ) -> list[_Candidate]:
        screening = screening or {}
        screened_columns = list(
            dict.fromkeys(
                column
                for pair in sorted(screening, key=screening.__getitem__)
                for column in sorted(pair)
            )
        )
        pool_size = _column_pool_size(mode, max_hypotheses)
        numeric = _prioritized_column_pool(
            columns[SemanticType.NUMERIC], question, pool_size, screened_columns
        )
        categorical = _prioritized_column_pool(
            columns[SemanticType.CATEGORICAL], question, pool_size, screened_columns
        )
        candidates: list[_Candidate] = []
        control = _explicit_control(question, numeric)
        for first, second in combinations(numeric, 2):
            variables = (first, second)
            methods = ("pearson", "spearman")
            selected_control = control if control not in variables else None
            if selected_control is not None:
                methods += ("partial_correlation",)
            methods += ("correlation_without_outliers",)
            group_by = categorical[0] if categorical else None
            if group_by is not None:
                methods += ("analyze_subgroups",)
            candidates.append(
                _Candidate(
                    family="numeric",
                    variables=variables,
                    methods=methods,
                    statement=(
                        f"Evaluate whether there is an association between {first} and {second}."
                    ),
                    control_variable=selected_control,
                    group_by=group_by,
                    priority=_question_priority(question, (*variables, selected_control)),
                )
            )
        for total in numeric:
            if not re.search(r"(?<!\w)(?:total|sum)(?!\w)", total.casefold().replace("_", " ")):
                continue
            components = [name for name in numeric if name != total][:2]
            if len(components) == 2:
                variables = (*components, total)
                candidates.append(
                    _Candidate(
                        family="identity",
                        variables=variables,
                        methods=("additive_identity",),
                        statement=(
                            f"Check whether {total} equals {components[0]} plus {components[1]}."
                        ),
                        priority=_question_priority(question, variables),
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
        candidates = [
            replace(candidate, screening_rank=screening.get(frozenset(candidate.variables)))
            for candidate in candidates
        ]
        if screening:
            # Screening found significant pairs: plan those plus anything the question names.
            candidates = [
                candidate
                for candidate in candidates
                if candidate.screening_rank is not None or candidate.priority > 0
            ] or candidates
        unranked = len(screening)
        return sorted(
            candidates,
            key=lambda candidate: (-candidate.priority, candidate.family),
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
            if candidate.group_by is not None:
                hypothesis_variables.append(candidate.group_by)
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=hypothesis_id,
                    statement=candidate.statement,
                    variables=hypothesis_variables,
                )
            )
            baseline_step_id: str | None = None
            for method in methods:
                parameters = (
                    {"control_variable": candidate.control_variable}
                    if method == "partial_correlation" and candidate.control_variable is not None
                    else {}
                )
                if method == "analyze_subgroups":
                    parameters = {"group_by": candidate.group_by}
                dependencies = (
                    [baseline_step_id]
                    if baseline_step_id is not None
                    and method in {"correlation_without_outliers", "analyze_subgroups"}
                    else []
                )
                steps.append(
                    AnalysisStep(
                        step_id=f"step-{len(steps) + 1}-{method}",
                        hypothesis_id=hypothesis_id,
                        depends_on=dependencies,
                        request=ToolRequest(
                            dataset_id=dataset_id,
                            method=method,
                            variables=list(candidate.variables),
                            parameters=parameters,
                        ),
                    )
                )
                if method == "pearson":
                    baseline_step_id = steps[-1].step_id
            used_families.add(candidate.family)
        return AnalysisPlan(hypotheses=hypotheses, steps=steps)


def _anova_sample_problem(
    category: ColumnProfile,
    numeric: ColumnProfile,
    row_count: int,
    summary: AnovaGroupSummary | None = None,
) -> str | None:
    if summary is not None:
        if summary.group_count < 2:
            return "at least two groups with complete observations are required."
        if summary.minimum_group_size < 2:
            return "each group requires at least two complete observations."
        return None
    # Metadata-only callers can still exclude cases that are provably insufficient.
    groups = category.unique_count
    if groups is not None:
        if groups < 2:
            return "at least two groups are required."
        observed = row_count - (category.missing_count or 0)
        if observed <= groups or (numeric.missing_count == 0 and observed < 2 * groups):
            return "each group requires at least two complete observations."
    return None


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


def _prioritized_column_pool(
    columns: list[str],
    question: str | None,
    pool_size: int,
    screened: list[str] | None = None,
) -> list[str]:
    """Keep a bounded deterministic pool: question mentions, then screened columns by rank."""
    mentioned = [column for column in columns if question and _mentioned(question, column)]
    ranked = [column for column in screened or [] if column in columns and column not in mentioned]
    rest = [column for column in columns if column not in mentioned and column not in ranked]
    return (mentioned + ranked + rest)[:pool_size]


def _screening_ranks(associations: list[AssociationResult]) -> dict[frozenset[str], int]:
    """Rank column pairs by first appearance; screening lists the strongest pairs first."""
    ranks: dict[frozenset[str], int] = {}
    for association in associations:
        if len(association.variables) == 2:
            ranks.setdefault(frozenset(association.variables), len(ranks))
    return ranks


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
