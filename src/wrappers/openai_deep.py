"""Wrapper for openai_deep_research (OpenAI deep research models)."""

from pathlib import Path
from typing import Optional

from ..models import ComplaintInput, PipelineConfig, ResearchApp
from .base import ToolWrapper


class OpenAIDeepResearchWrapper(ToolWrapper):
    """Wrapper for the openai_deep_research application.

    This app uses OpenAI's deep research models (o4-mini-deep-research).
    Primary role in pipeline: Demographics Analysis
    """

    def __init__(self, config: PipelineConfig):
        super().__init__(config)

    @property
    def app(self) -> ResearchApp:
        return ResearchApp.OPENAI_DEEP_RESEARCH

    @property
    def app_dir(self) -> Path:
        return self.config.openai_deep_research_dir

    @property
    def display_name(self) -> str:
        return "OpenAI Deep Research"

    def build_command(self, complaint: ComplaintInput) -> list[str]:
        """Build the 'just research' command for openai_deep_research.

        The app accepts complaint strings directly.
        """
        return ["just", "research", complaint.complaint]

    def find_output_directory(self, complaint: ComplaintInput) -> Optional[Path]:
        """Find the output directory for a completed research run.

        openai_deep_research creates directories like:
        output/{complaint}_{YYYYMMDD}_{HHMMSS}/
        """
        outputs_dir = self.app_dir / "output"
        prefix = complaint.normalized_name

        return self._find_latest_output_dir(outputs_dir, prefix)

    def list_output_files(self, output_dir: Path) -> list[str]:
        """List expected output files.

        openai_deep_research produces:
        - {complaint}_phase1_foundation_clinical.md
        - {complaint}_phase2_demographics.md
        - {complaint}_phase3_synonyms.md
        - {complaint}_metadata.json
        """
        if not output_dir or not output_dir.exists():
            return []

        files = []
        for f in output_dir.iterdir():
            if f.is_file() and (f.suffix == ".md" or f.suffix == ".json"):
                files.append(f.name)

        return files

    def check_availability(self) -> tuple[bool, str]:
        """Check if openai_deep_research is available.

        Additional check: Verify research.py exists.
        """
        base_available, base_message = super().check_availability()
        if not base_available:
            return base_available, base_message

        # Check for main research script
        research_script = self.app_dir / "research.py"
        if not research_script.exists():
            return False, f"research.py not found in {self.app_dir}"

        # Check for ResearchProtocol.md
        protocol = self.app_dir / "ResearchProtocol.md"
        if not protocol.exists():
            return False, f"ResearchProtocol.md not found in {self.app_dir}"

        return True, f"{self.display_name} is available"

    def get_phase1_output(self, output_dir: Path, complaint: ComplaintInput) -> Optional[Path]:
        """Get the Phase 1 (Foundation + Clinical) output file."""
        filename = f"{complaint.normalized_name}_phase1_foundation_clinical.md"
        file_path = output_dir / filename
        return file_path if file_path.exists() else None

    def get_phase2_output(self, output_dir: Path, complaint: ComplaintInput) -> Optional[Path]:
        """Get the Phase 2 (Demographics) output file."""
        filename = f"{complaint.normalized_name}_phase2_demographics.md"
        file_path = output_dir / filename
        return file_path if file_path.exists() else None

    def get_phase3_output(self, output_dir: Path, complaint: ComplaintInput) -> Optional[Path]:
        """Get the Phase 3 (Synonyms) output file."""
        filename = f"{complaint.normalized_name}_phase3_synonyms.md"
        file_path = output_dir / filename
        return file_path if file_path.exists() else None

    def get_metadata(self, output_dir: Path, complaint: ComplaintInput) -> Optional[Path]:
        """Get the metadata JSON file."""
        filename = f"{complaint.normalized_name}_metadata.json"
        file_path = output_dir / filename
        return file_path if file_path.exists() else None
