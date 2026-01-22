"""Shared models for the deep research pipeline."""

from .complaint import (
    AgeGroup,
    ComplaintInput,
    ComplaintType,
    DemographicCombination,
    Sex,
    SpecialPopulation,
    TraumaAgeGroup,
    TraumaDemographicCombination,
    TRAUMA_TO_MEDICAL_AGE_MAPPING,
)
from .outputs import (
    AggregatedResearchContext,
    ClinicalContextFindings,
    ClinicalContextItem,
    DemographicFinding,
    DemographicsFindings,
    FoundationFindings,
    SourceReference,
    SynonymEntry,
    SynonymFindings,
)
from .state import (
    AppExecutionResult,
    PipelineConfig,
    PipelinePhase,
    PipelineState,
    ResearchApp,
    ResearchAppStatus,
)

__all__ = [
    # Complaint models
    "AgeGroup",
    "ComplaintInput",
    "ComplaintType",
    "DemographicCombination",
    "Sex",
    "SpecialPopulation",
    "TraumaAgeGroup",
    "TraumaDemographicCombination",
    "TRAUMA_TO_MEDICAL_AGE_MAPPING",
    # State models
    "AppExecutionResult",
    "PipelineConfig",
    "PipelinePhase",
    "PipelineState",
    "ResearchApp",
    "ResearchAppStatus",
    # Output models
    "AggregatedResearchContext",
    "ClinicalContextFindings",
    "ClinicalContextItem",
    "DemographicFinding",
    "DemographicsFindings",
    "FoundationFindings",
    "SourceReference",
    "SynonymEntry",
    "SynonymFindings",
]
