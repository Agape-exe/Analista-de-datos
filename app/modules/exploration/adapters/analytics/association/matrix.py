from app.modules.exploration.adapters.analytics.association import measures
from app.modules.exploration.adapters.analytics.base import (
    DatasetTool,
    ToolOutput,
    finite,
    probability,
)
from app.modules.exploration.adapters.analytics.columns import column_array, require_role
from app.shared.application.errors import AnalysisNotApplicableError, ToolInputError
from app.shared.contracts.datasource import RegisteredDataset
from app.shared.domain.enums.semantic_type import SemanticType
from app.shared.domain.models.analysis import ToolRequest

MATRIX_METHODS = {"pearson": measures.pearson, "spearman": measures.spearman}


def correlation_matrix(
    data: RegisteredDataset, columns: list[str], method: str
) -> dict[str, object]:
    """Pairwise-complete correlation matrix; undefined cells are None, never NaN."""
    try:
        statistic = MATRIX_METHODS[method]
    except KeyError as error:
        raise ToolInputError(f"Unsupported correlation method: {method}") from error
    arrays = {name: column_array(data, name) for name in columns}
    size = len(columns)
    values: list[list[float | None]] = [[None] * size for _ in range(size)]
    p_values: list[list[float | None]] = [[None] * size for _ in range(size)]
    counts: list[list[int]] = [[0] * size for _ in range(size)]
    for i, x in enumerate(columns):
        for j in range(i, size):
            y = columns[j]
            try:
                measure = statistic(arrays[x], arrays[y])
            except AnalysisNotApplicableError:
                continue
            value, p_value = finite(measure.statistic), probability(measure.p_value)
            values[i][j] = values[j][i] = 1.0 if i == j else value
            p_values[i][j] = p_values[j][i] = None if i == j else p_value
            counts[i][j] = counts[j][i] = measure.sample_size
    return {
        "method": method,
        "columns": columns,
        "values": values,
        "p_values": p_values,
        "sample_sizes": counts,
    }


class CorrelationMatrixTool(DatasetTool):
    """Numeric correlation matrix; defaults to every numeric column when none are given."""

    name = "correlation_matrix"

    def supports(self, request: ToolRequest) -> bool:
        return super().supports(request) and len(request.variables) != 1

    def compute(self, data: RegisteredDataset, request: ToolRequest) -> ToolOutput:
        columns = list(request.variables) or data.columns_of_type(SemanticType.NUMERIC)
        for name in columns:
            require_role(data, name, SemanticType.NUMERIC)
        if len(columns) < 2:
            raise AnalysisNotApplicableError("A correlation matrix needs 2+ numeric columns.")
        method = str(request.parameters.get("method", "pearson"))
        matrix = correlation_matrix(data, columns, method)
        notes = []
        if any(value is None for row in matrix["values"] for value in row):
            notes.append("Some cells are undefined (constant columns or too few pairs).")
        return ToolOutput(
            result=matrix,
            variables=columns,
            sample_size=data.dataset.row_count,
            warnings=notes,
            metadata={"method": method},
        )
