from enum import StrEnum


class AnalysisStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class DictionarySource(StrEnum):
    OFFICIAL = "official"
    MANUAL = "manual"
    SCHEMA = "schema"
    INFERRED = "inferred"
