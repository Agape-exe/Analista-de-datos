from itertools import combinations

import numpy as np

from app.analytics.association import measures
from app.analytics.association.measures import Measure
from app.analytics.base import DatasetTool, ToolOutput, finite, probability
from app.analytics.columns import ASSOCIABLE, column_array, present, require_role
from app.application.dto.datasource import RegisteredDataset
from app.application.errors import AnalysisNotApplicableError
from app.domain.enums.semantic_type import SemanticType
from app.domain.models.analysis import AssociationResult, RankedRelationship, ToolRequest

DIVERGENCE = 0.2


class RelationshipRankingTool(DatasetTool):
    """Screen every eligible column pair and rank candidate relationships.

    Each pair gets the tests that fit its semantic types. The best-scoring test with a
    p-value is the primary result; mutual information is supporting evidence. p-values
    are corrected with Benjamini-Hochberg across all tests before filtering.
    """

    name = "relationship_ranking"

    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput:
        columns = list(request.variables) or data.columns_of_type(*ASSOCIABLE)
        for name in columns:
            require_role(data, name, *ASSOCIABLE)
        arrays, excluded = self._eligible(data, columns)
        pairs = list(combinations(arrays, 2))
        notes: list[str] = []
        if len(pairs) > self.options.max_pairs:
            notes.append(
                f"{len(pairs)} pairs found; only the first {self.options.max_pairs} were screened."
            )
            pairs = pairs[: self.options.max_pairs]
        if not pairs:
            raise AnalysisNotApplicableError("Fewer than 2 eligible columns to associate.")

        screened: list[tuple[str, str, list[Measure]]] = []
        skipped: list[dict[str, str]] = []
        for x, y in pairs:
            try:
                screened.append((x, y, self._measure_pair(data, arrays, x, y)))
            except AnalysisNotApplicableError as error:
                skipped.append({"x": x, "y": y, "reason": str(error)})

        tested = [m for _, _, pair in screened for m in pair if m.p_value is not None]
        adjusted = dict(
            zip(
                map(id, tested),
                measures.benjamini_hochberg([m.p_value for m in tested]),
                strict=True,
            )
        )
        alpha = float(request.parameters.get("significance_level", self.options.significance_level))
        ranked = [
            relationship
            for x, y, pair in screened
            if (relationship := self._relationship(x, y, pair, adjusted)).adjusted_p_value
            is not None
            and relationship.adjusted_p_value <= alpha
        ]
        ranked.sort(key=lambda item: (-item.score, item.adjusted_p_value or 0, item.x, item.y))
        limit = int(request.parameters.get("top_k", self.options.top_relationships))
        notes.append("Relationships are statistical candidates, not causal or validated findings.")
        return ToolOutput(
            result={
                "top_relationships": [item.model_dump(mode="json") for item in ranked[:limit]],
                "evaluated_pairs": len(screened),
                "significant_pairs": len(ranked),
                "skipped_pairs": skipped,
                "excluded_columns": excluded,
                "significance_level": alpha,
                "correction": "benjamini-hochberg",
            },
            variables=list(arrays),
            sample_size=data.dataset.row_count,
            warnings=notes,
            metadata={"tests_performed": len(tested)},
        )

    def _eligible(
        self, data: RegisteredDataset, columns: list[str]
    ) -> tuple[dict[str, np.ndarray], dict[str, str]]:
        arrays: dict[str, np.ndarray] = {}
        excluded: dict[str, str] = {}
        for name in columns:
            values = column_array(data, name)
            observed = values[present(values)]
            distinct = len(set(observed.tolist()))
            if distinct <= 1:
                excluded[name] = "constant or empty column"
            elif values.dtype == object and distinct > self.options.max_categories:
                excluded[name] = f"{distinct} categories exceed {self.options.max_categories}"
            else:
                arrays[name] = values
        return arrays, excluded

    def _measure_pair(
        self, data: RegisteredDataset, arrays: dict[str, np.ndarray], x: str, y: str
    ) -> list[Measure]:
        x_values, y_values = arrays[x], arrays[y]
        roles = (data.semantic_type(x), data.semantic_type(y))
        if roles == (SemanticType.NUMERIC, SemanticType.NUMERIC):
            results = [measures.pearson(x_values, y_values), measures.spearman(x_values, y_values)]
        elif roles == (SemanticType.CATEGORICAL, SemanticType.CATEGORICAL):
            results = [measures.cramers_v(x_values, y_values)]
        else:
            numeric, labels = (
                (x_values, y_values) if roles[0] == SemanticType.NUMERIC else (y_values, x_values)
            )
            results = [measures.group_difference(numeric, labels, self.options.normality_alpha)]
        self.require_sample(results[0].sample_size, f"{x} vs {y}")
        try:
            results.append(
                measures.mutual_information(
                    x_values,
                    y_values,
                    self.options.mutual_information_neighbors,
                    self.options.random_seed,
                    self.options.mutual_information_max_rows,
                )
            )
        except AnalysisNotApplicableError:
            pass
        return results

    @staticmethod
    def _relationship(
        x: str, y: str, pair: list[Measure], adjusted: dict[int, float]
    ) -> RankedRelationship:
        primary = max((m for m in pair if m.p_value is not None), key=lambda m: m.score)
        notes = list(primary.warnings)
        by_method = {m.method: m for m in pair}
        if "pearson" in by_method and "spearman" in by_method:
            gap = abs(by_method["pearson"].effect_size - by_method["spearman"].effect_size)
            if gap > DIVERGENCE:
                notes.append(
                    "Pearson and Spearman disagree; check outliers or non-linear patterns."
                )
        mi = by_method.get("mutual_information")
        if mi is not None and mi.score - primary.score > DIVERGENCE:
            notes.append("Mutual information suggests a non-linear dependence.")
        return RankedRelationship(
            x=x,
            y=y,
            method=primary.method,
            score=finite(primary.score) or 0.0,
            strength=finite(primary.effect_size),
            p_value=probability(primary.p_value),
            adjusted_p_value=probability(adjusted.get(id(primary))),
            sample_size=primary.sample_size,
            supporting=[
                AssociationResult(
                    method=m.method,
                    variables=[x, y],
                    strength=finite(m.effect_size),
                    p_value=probability(m.p_value),
                )
                for m in pair
                if m is not primary
            ],
            warnings=notes,
        )
