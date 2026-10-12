class DataSourceError(Exception):
    """A local source could not be loaded."""


class LLMDisabledError(Exception):
    """No configured language model is available."""


class WorkflowUnavailableError(Exception):
    """The complete analysis workflow is not enabled."""


class ToolRegistryError(Exception):
    """A tool registration or lookup failed."""
