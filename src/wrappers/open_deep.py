"""Wrapper for open_deep_research (LangChain-based research tool)."""

from pathlib import Path
from typing import Optional

from ..models import ComplaintInput, PipelineConfig, ResearchApp
from .base import ToolWrapper


class OpenDeepResearchWrapper(ToolWrapper):
    """Wrapper for the open_deep_research application.

    This app uses LangGraph with a deep research server.
    Primary role in pipeline: Foundation + Clinical Context + Synonyms
    """

    def __init__(self, config: PipelineConfig):
        super().__init__(config)

    @property
    def app(self) -> ResearchApp:
        return ResearchApp.OPEN_DEEP_RESEARCH

    @property
    def app_dir(self) -> Path:
        return self.config.open_deep_research_dir

    @property
    def display_name(self) -> str:
        return "Open Deep Research"

    def build_command(self, complaint: ComplaintInput) -> list[str]:
        """Build the 'just go' command for open_deep_research.

        The app expects complaint names, which it matches to JSON files
        in the complaints/ directory.
        """
        # Use 'just go' which is the main research command
        return ["just", "go", complaint.complaint]

    def find_output_directory(self, complaint: ComplaintInput) -> Optional[Path]:
        """Find the output directory for a completed research run.

        open_deep_research creates directories like:
        outputs/{complaint}_{YYYYMMDD}_{HHMMSS}/
        """
        outputs_dir = self.app_dir / "outputs"
        prefix = complaint.normalized_name

        return self._find_latest_output_dir(outputs_dir, prefix)

    def list_output_files(self, output_dir: Path) -> list[str]:
        """List expected output files.

        open_deep_research produces:
        - {complaint}_foundation_clinical_context.md (Phase A)
        - {complaint}_demographics_analysis.md (Phase B)
        - {complaint}_synonym_terminology.md (Phase C)
        """
        if not output_dir or not output_dir.exists():
            return []

        expected_suffixes = [
            "_foundation_clinical_context.md",
            "_demographics_analysis.md",
            "_synonym_terminology.md",
        ]

        files = []
        for f in output_dir.iterdir():
            if f.is_file() and f.suffix == ".md":
                files.append(f.name)

        return files

    def check_availability(self) -> tuple[bool, str]:
        """Check if open_deep_research is available.

        Additional check: Verify the LangGraph server is referenced
        in langgraph.json.
        """
        base_available, base_message = super().check_availability()
        if not base_available:
            return base_available, base_message

        # Check for langgraph.json
        langgraph_config = self.app_dir / "langgraph.json"
        if not langgraph_config.exists():
            return False, f"langgraph.json not found in {self.app_dir}"

        # Check for complaints directory
        complaints_dir = self.app_dir / "complaints"
        if not complaints_dir.exists():
            return False, f"complaints/ directory not found in {self.app_dir}"

        return True, f"{self.display_name} is available"

    def get_phase_a_output(self, output_dir: Path, complaint: ComplaintInput) -> Optional[Path]:
        """Get the Phase A (Foundation + Clinical Context) output file."""
        filename = f"{complaint.normalized_name}_foundation_clinical_context.md"
        file_path = output_dir / filename
        return file_path if file_path.exists() else None

    def get_phase_b_output(self, output_dir: Path, complaint: ComplaintInput) -> Optional[Path]:
        """Get the Phase B (Demographics Analysis) output file."""
        filename = f"{complaint.normalized_name}_demographics_analysis.md"
        file_path = output_dir / filename
        return file_path if file_path.exists() else None

    def get_phase_c_output(self, output_dir: Path, complaint: ComplaintInput) -> Optional[Path]:
        """Get the Phase C (Synonym & Terminology) output file."""
        filename = f"{complaint.normalized_name}_synonym_terminology.md"
        file_path = output_dir / filename
        return file_path if file_path.exists() else None
