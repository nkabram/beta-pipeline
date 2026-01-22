"""Normalized output models for research findings across all apps."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .complaint import AgeGroup, Sex, SpecialPopulation, TraumaAgeGroup
from .state import ResearchApp


class SourceReference(BaseModel):
    """A source/citation from research."""

    title: str
    url: Optional[str] = None
    domain: Optional[str] = None
    tier: Optional[int] = Field(None, description="Evidence tier (1-3)")
    accessed_date: Optional[datetime] = None


class DemographicFinding(BaseModel):
    """A finding specific to a demographic group."""

    age_group: Optional[AgeGroup] = None
    trauma_age_group: Optional[TraumaAgeGroup] = None
    sex: Optional[Sex] = None
    special_population: Optional[SpecialPopulation] = None

    finding_type: str = Field(..., description="Type: differential, presentation, treatment, risk")
    content: str = Field(..., description="The actual finding text")
    clinical_significance: Optional[str] = None
    priority_score: Optional[int] = Field(None, ge=0, le=100)
    sources: list[SourceReference] = Field(default_factory=list)

    @property
    def demographic_identifier(self) -> str:
        """Return identifier for this demographic."""
        parts = []
        if self.age_group:
            parts.append(self.age_group.value)
        if self.trauma_age_group:
            parts.append(self.trauma_age_group.value)
        if self.sex:
            parts.append(self.sex.value)
        if self.special_population:
            parts.append(self.special_population.value)
        return "_".join(parts) if parts else "general"


class ClinicalContextItem(BaseModel):
    """A clinical context item from research."""

    category: str = Field(
        ...,
        description="Category: diagnostic, risk_stratification, management, testing, treatment, decision_support, medicolegal"
    )
    title: str
    content: str
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    sources: list[SourceReference] = Field(default_factory=list)


class SynonymEntry(BaseModel):
    """A synonym or alternative term for the complaint."""

    term: str
    term_type: str = Field(
        ...,
        description="Type: medical_synonym, abbreviation, lay_term, regional_variation, pediatric_term"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    context: Optional[str] = None
    sources: list[SourceReference] = Field(default_factory=list)


class FoundationFindings(BaseModel):
    """Normalized foundation/epidemiology findings."""

    source_app: ResearchApp
    complaint_name: str

    # Epidemiology
    prevalence: Optional[str] = None
    incidence: Optional[str] = None
    common_etiologies: list[str] = Field(default_factory=list)

    # Differential diagnosis
    differential_diagnoses: list[dict[str, Any]] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)

    # Pathophysiology
    pathophysiology_summary: Optional[str] = None

    sources: list[SourceReference] = Field(default_factory=list)
    raw_content: Optional[str] = Field(None, description="Original markdown content")


class DemographicsFindings(BaseModel):
    """Normalized demographics analysis findings."""

    source_app: ResearchApp
    complaint_name: str

    # Age-stratified findings
    age_findings: dict[str, list[DemographicFinding]] = Field(
        default_factory=dict,
        description="Keyed by age group identifier"
    )

    # Sex-based findings
    sex_findings: dict[str, list[DemographicFinding]] = Field(
        default_factory=dict,
        description="Keyed by sex value"
    )

    # Special population findings
    special_population_findings: dict[str, list[DemographicFinding]] = Field(
        default_factory=dict,
        description="Keyed by special population identifier"
    )

    # Modifier creation decisions
    created_modifiers: list[str] = Field(
        default_factory=list,
        description="List of demographic identifiers that warranted modifiers"
    )

    sources: list[SourceReference] = Field(default_factory=list)
    raw_content: Optional[str] = Field(None, description="Original markdown content")


class ClinicalContextFindings(BaseModel):
    """Normalized clinical context findings."""

    source_app: ResearchApp
    complaint_name: str

    # 7 clinical context categories
    diagnostic: list[ClinicalContextItem] = Field(default_factory=list)
    risk_stratification: list[ClinicalContextItem] = Field(default_factory=list)
    management: list[ClinicalContextItem] = Field(default_factory=list)
    testing: list[ClinicalContextItem] = Field(default_factory=list)
    treatment: list[ClinicalContextItem] = Field(default_factory=list)
    decision_support: list[ClinicalContextItem] = Field(default_factory=list)
    medicolegal: list[ClinicalContextItem] = Field(default_factory=list)

    sources: list[SourceReference] = Field(default_factory=list)
    raw_content: Optional[str] = Field(None, description="Original markdown content")


class SynonymFindings(BaseModel):
    """Normalized synonym/terminology findings."""

    source_app: ResearchApp
    complaint_name: str

    medical_synonyms: list[SynonymEntry] = Field(default_factory=list)
    abbreviations: list[SynonymEntry] = Field(default_factory=list)
    lay_terms: list[SynonymEntry] = Field(default_factory=list)
    regional_variations: list[SynonymEntry] = Field(default_factory=list)
    pediatric_terms: list[SynonymEntry] = Field(default_factory=list)

    sources: list[SourceReference] = Field(default_factory=list)
    raw_content: Optional[str] = Field(None, description="Original markdown content")


class AggregatedResearchContext(BaseModel):
    """Aggregated context from all research apps for beta_research consumption."""

    complaint_name: str
    complaint_type: str
    generated_at: datetime = Field(default_factory=datetime.now)

    # Combined findings from all apps
    foundation: FoundationFindings
    demographics: DemographicsFindings
    clinical_context: ClinicalContextFindings
    synonyms: SynonymFindings

    # Synthesis notes (from claude-deep-research)
    synthesis_summary: Optional[str] = None
    identified_gaps: list[str] = Field(default_factory=list)

    # Source tracking
    contributing_apps: list[ResearchApp] = Field(default_factory=list)
    total_sources: int = 0

    def to_beta_research_format(self) -> dict[str, Any]:
        """Convert to format consumable by beta_research local resources."""
        return {
            "complaint": self.complaint_name,
            "type": self.complaint_type,
            "generated_at": self.generated_at.isoformat(),
            "foundation": {
                "prevalence": self.foundation.prevalence,
                "incidence": self.foundation.incidence,
                "etiologies": self.foundation.common_etiologies,
                "differential": self.foundation.differential_diagnoses,
                "red_flags": self.foundation.red_flags,
                "pathophysiology": self.foundation.pathophysiology_summary,
            },
            "demographics": {
                "age_groups": self.demographics.age_findings,
                "sex_based": self.demographics.sex_findings,
                "special_populations": self.demographics.special_population_findings,
                "modifiers": self.demographics.created_modifiers,
            },
            "clinical_context": {
                "diagnostic": [item.model_dump() for item in self.clinical_context.diagnostic],
                "risk_stratification": [item.model_dump() for item in self.clinical_context.risk_stratification],
                "management": [item.model_dump() for item in self.clinical_context.management],
                "testing": [item.model_dump() for item in self.clinical_context.testing],
                "treatment": [item.model_dump() for item in self.clinical_context.treatment],
                "decision_support": [item.model_dump() for item in self.clinical_context.decision_support],
                "medicolegal": [item.model_dump() for item in self.clinical_context.medicolegal],
            },
            "synonyms": {
                "medical": [s.model_dump() for s in self.synonyms.medical_synonyms],
                "abbreviations": [s.model_dump() for s in self.synonyms.abbreviations],
                "lay_terms": [s.model_dump() for s in self.synonyms.lay_terms],
            },
            "synthesis": {
                "summary": self.synthesis_summary,
                "gaps": self.identified_gaps,
            },
            "metadata": {
                "apps": [app.value for app in self.contributing_apps],
                "total_sources": self.total_sources,
            },
        }
