"""Pipeline state models for tracking research progress."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from .complaint import ComplaintInput, ComplaintType


class ResearchAppStatus(str, Enum):
    """Status of a research application execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ResearchApp(str, Enum):
    """The three research applications in the pipeline."""

    OPEN_DEEP_RESEARCH = "open_deep_research"
    OPENAI_DEEP_RESEARCH = "openai_deep_research"
    CLAUDE_DEEP_RESEARCH = "claude_deep_research"


class AppExecutionResult(BaseModel):
    """Result of executing a single research application."""

    app: ResearchApp
    status: ResearchAppStatus
    output_dir: Optional[Path] = None
    output_files: list[str] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    exit_code: Optional[int] = None

    @property
    def is_success(self) -> bool:
        """Check if execution completed successfully."""
        return self.status == ResearchAppStatus.COMPLETED


class PipelinePhase(str, Enum):
    """Phases of the orchestration pipeline."""

    INITIALIZATION = "initialization"
    RESEARCH_EXECUTION = "research_execution"
    OUTPUT_PARSING = "output_parsing"
    CONTEXT_AGGREGATION = "context_aggregation"
    TEMPLATE_GENERATION = "template_generation"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineState(BaseModel):
    """Mutable state for the orchestration pipeline."""

    # Input
    complaint: ComplaintInput

    # Timing
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # Current phase
    current_phase: PipelinePhase = PipelinePhase.INITIALIZATION

    # Research app results
    app_results: dict[ResearchApp, AppExecutionResult] = Field(default_factory=dict)

    # Parsed outputs (populated after parsing phase)
    parsed_foundation: Optional[dict[str, Any]] = None
    parsed_demographics: Optional[dict[str, Any]] = None
    parsed_clinical_context: Optional[dict[str, Any]] = None
    parsed_synonyms: Optional[dict[str, Any]] = None

    # Aggregated context for beta_research
    aggregated_context: Optional[dict[str, Any]] = None

    # Final outputs
    output_directory: Optional[Path] = None
    generated_templates: list[str] = Field(default_factory=list)

    # Error tracking
    errors: list[str] = Field(default_factory=list)

    @property
    def is_medical(self) -> bool:
        """Check if this is a medical (non-trauma) complaint."""
        return self.complaint.complaint_type == ComplaintType.MEDICAL

    @property
    def is_trauma(self) -> bool:
        """Check if this is a trauma complaint."""
        return self.complaint.complaint_type == ComplaintType.TRAUMA

    @property
    def all_apps_completed(self) -> bool:
        """Check if all research apps have completed (success or failure)."""
        terminal_statuses = {
            ResearchAppStatus.COMPLETED,
            ResearchAppStatus.FAILED,
            ResearchAppStatus.SKIPPED,
        }
        return all(
            result.status in terminal_statuses
            for result in self.app_results.values()
        )

    @property
    def successful_apps(self) -> list[ResearchApp]:
        """Return list of apps that completed successfully."""
        return [
            app for app, result in self.app_results.items()
            if result.is_success
        ]

    def add_error(self, error: str) -> None:
        """Add an error message to the state."""
        self.errors.append(f"[{datetime.now().isoformat()}] {error}")

    def mark_phase(self, phase: PipelinePhase) -> None:
        """Update the current phase."""
        self.current_phase = phase
        if phase == PipelinePhase.COMPLETED:
            self.completed_at = datetime.now()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Return total pipeline duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class PipelineConfig(BaseModel):
    """Configuration for the orchestration pipeline."""

    # Base paths
    base_output_dir: Path = Field(default=Path("reports"))

    # Research app directories
    open_deep_research_dir: Path = Field(default=Path("D:/research/open_deep_research"))
    openai_deep_research_dir: Path = Field(default=Path("D:/research/openai_deep_research"))
    claude_deep_research_dir: Path = Field(default=Path("D:/research/claude-deep-research"))
    beta_research_dir: Path = Field(default=Path("D:/research/beta_research"))

    # Execution settings
    timeout_seconds: int = Field(default=3600, description="Max time per app in seconds")
    parallel_execution: bool = Field(default=True, description="Run apps in parallel")
    max_workers: int = Field(default=3, description="Max parallel workers")

    # Specialization settings (which app handles what)
    foundation_app: ResearchApp = Field(
        default=ResearchApp.OPEN_DEEP_RESEARCH,
        description="Primary app for foundation + clinical context"
    )
    demographics_app: ResearchApp = Field(
        default=ResearchApp.OPENAI_DEEP_RESEARCH,
        description="Primary app for demographics analysis"
    )
    synthesis_app: ResearchApp = Field(
        default=ResearchApp.CLAUDE_DEEP_RESEARCH,
        description="Primary app for synthesis and gap analysis"
    )

    # Fallback settings
    enable_fallbacks: bool = Field(
        default=True,
        description="Use another app if primary fails"
    )

    # Beta research integration
    run_beta_research: bool = Field(default=True, description="Run beta_research for templates")
    beta_research_include_local: bool = Field(default=True, description="Include local resources")

    def get_app_dir(self, app: ResearchApp) -> Path:
        """Get the directory for a specific research app."""
        mapping = {
            ResearchApp.OPEN_DEEP_RESEARCH: self.open_deep_research_dir,
            ResearchApp.OPENAI_DEEP_RESEARCH: self.openai_deep_research_dir,
            ResearchApp.CLAUDE_DEEP_RESEARCH: self.claude_deep_research_dir,
        }
        return mapping[app]
