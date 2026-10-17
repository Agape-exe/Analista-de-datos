from collections.abc import Callable

import numpy as np

from app.analytics.association import measures
from app.analytics.association.measures import Measure
from app.analytics.base import DatasetTool, ToolOutput, finite
from app.analytics.columns import ASSOCIABLE, column_array, present, require_role
from app.application.dto.datasource import RegisteredDataset
from app.application.errors import AnalysisNotApplicableError
from app.domain.enums.semantic_type import SemanticType
from app.domain.models.analysis import ToolRequest

NUMERIC = SemanticType.NUMERIC
CATEGORICAL = SemanticType.CATEGORICAL


def measure_output(measure: Measure, variables: list[str]) -> ToolOutput:
    details = {
        key: finite(value) if isinstance(value, float) else value
        for key, value in measure.details.items()
    }
    if isinstance(details.get("confidence_interval"), list):
        details["confidence_interval"] = [finite(v) for v in details["confidence_interval"]]
    return ToolOutput(
        result={
            "statistic": finite(measure.statistic),
            "effect_size": finite(measure.effect_size),
            "score": finite(measure.score),
            **details,
        },
        variables=variables,
        p_value=measure.p_value,
        effect_size=measure.effect_size,
        sample_size=measure.sample_size,
        warnings=measure.warnings,
    )


def check_categories(values: np.ndarray, name: str, limit: int) -> None:
    categories = len({value for value in values[present(values)]})
    if categories > limit:
        raise AnalysisNotApplicableError(
            f"{name}: {categories} categories exceed the configured limit of {limit}."
        )


class PairTool(DatasetTool):
    """Association between exactly two columns."""

    min_variables = 2
    max_variables = 2

    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput:
        x, y = request.variables
        if x == y:
            raise AnalysisNotApplicableError("Association requires two different columns.")
        measure = self.measure(data, x, y)
        self.require_sample(measure.sample_size, f"{x} vs {y}")
        return measure_output(measure, [x, y])

    def measure(self, data: RegisteredDataset, x: str, y: str) -> Measure:
        raise NotImplementedError


class NumericPairTool(PairTool):
    statistic: Callable[[np.ndarray, np.ndarray], Measure]

    def measure(self, data: RegisteredDataset, x: str, y: str) -> Measure:
        require_role(data, x, NUMERIC)
        require_role(data, y, NUMERIC)
        return self.statistic(column_array(data, x), column_array(data, y))


class PearsonTool(NumericPairTool):
    name = "pearson"
    statistic = staticmethod(measures.pearson)


class SpearmanTool(NumericPairTool):
    name = "spearman"
    statistic = staticmethod(measures.spearman)


class CategoricalPairTool(PairTool):
    statistic: Callable[[np.ndarray, np.ndarray], Measure]

    def measure(self, data: RegisteredDataset, x: str, y: str) -> Measure:
        require_role(data, x, CATEGORICAL)
        require_role(data, y, CATEGORICAL)
        x_values, y_values = column_array(data, x), column_array(data, y)
        check_categories(x_values, x, self.options.max_categories)
        check_categories(y_values, y, self.options.max_categories)
        return self.statistic(x_values, y_values)


class ChiSquareTool(CategoricalPairTool):
    name = "chi_square"
    statistic = staticmethod(measures.chi_square)


class CramersVTool(CategoricalPairTool):
    name = "cramers_v"
    statistic = staticmethod(measures.cramers_v)


class GroupTool(PairTool):
    """Numeric column compared across the groups of a categorical column (any order)."""

    def measure(self, data: RegisteredDataset, x: str, y: str) -> Measure:
        roles = {data.semantic_type(x), data.semantic_type(y)}
        if roles != {NUMERIC, CATEGORICAL}:
            raise AnalysisNotApplicableError(
                f"{self.name} needs one numeric and one categorical column."
            )
        numeric, group = (x, y) if data.semantic_type(x) == NUMERIC else (y, x)
        labels = column_array(data, group)
        check_categories(labels, group, self.options.max_categories)
        return self.groups(column_array(data, numeric), labels)

    def groups(self, values: np.ndarray, labels: np.ndarray) -> Measure:
        raise NotImplementedError


class AnovaTool(GroupTool):
    name = "anova"

    def groups(self, values: np.ndarray, labels: np.ndarray) -> Measure:
        return measures.anova(values, labels, self.options.normality_alpha)


class KruskalWallisTool(GroupTool):
    name = "kruskal_wallis"

    def groups(self, values: np.ndarray, labels: np.ndarray) -> Measure:
        return measures.kruskal_wallis(values, labels)


class MutualInformationTool(PairTool):
    name = "mutual_information"

    def measure(self, data: RegisteredDataset, x: str, y: str) -> Measure:
        require_role(data, x, *ASSOCIABLE)
        require_role(data, y, *ASSOCIABLE)
        x_values, y_values = column_array(data, x), column_array(data, y)
        for name, values in ((x, x_values), (y, y_values)):
            if values.dtype == object:
                check_categories(values, name, self.options.max_categories)
        return measures.mutual_information(
            x_values,
            y_values,
            self.options.mutual_information_neighbors,
            self.options.random_seed,
            self.options.mutual_information_max_rows,
        )
