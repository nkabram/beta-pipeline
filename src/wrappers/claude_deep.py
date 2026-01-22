"""Wrapper for claude-deep-research (Anthropic orchestrator-worker)."""

from pathlib import Path
from typing import Optional

from ..models import ComplaintInput, PipelineConfig, ResearchApp
from .base import ToolWrapper


class ClaudeDeepResearchWrapper(ToolWrapper):
    """Wrapper for the claude-deep-research application.

    This app uses Claude's orchestrator-worker pattern with Sonnet 4.
    Primary role in pipeline: Synthesis & Gap Analysis
    """

    def __init__(self, config: PipelineConfig):
        super().__init__(config)

    @property
    def app(self) -> ResearchApp:
        return ResearchApp.CLAUDE_DEEP_RESEARCH

    @property
    def app_dir(self) -> Path:
        return self.config.claude_deep_research_dir

    @property
    def display_name(self) -> str:
        return "Claude Deep Research"

    def build_command(self, complaint: ComplaintInput) -> list[str]:
        """Build the 'just medical' command for claude-deep-research.

        The app accepts topic strings with a mode flag.
        """
        return ["just", "medical", complaint.complaint]

    def find_output_directory(self, complaint: ComplaintInput) -> Optional[Path]:
        """Find the output directory for a completed research run.

        claude-deep-research creates directories like:
        output/{complaint_slug}_{YYYYMMDD}_{HHMMSS}/
        """
        outputs_dir = self.app_dir / "output"
        prefix = complaint.normalized_name

        return self._find_latest_output_dir(outputs_dir, prefix)

    def list_output_files(self, output_dir: Path) -> list[str]:
        """List expected output files.

        claude-deep-research produces:
        - {complaint}_research_report.md (synthesized report)
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
        """Check if claude-deep-research is available.

        Additional check: Verify research.py and protocols exist.
        """
        base_available, base_message = super().check_availability()
        if not base_available:
            return base_available, base_message

        # Check for main research script
        research_script = self.app_dir / "research.py"
        if not research_script.exists():
            return False, f"research.py not found in {self.app_dir}"

        # Check for MedicalResearchProtocol.md
        protocol = self.app_dir / "MedicalResearchProtocol.md"
        if not protocol.exists():
            return False, f"MedicalResearchProtocol.md not found in {self.app_dir}"

        return True, f"{self.display_name} is available"

    def get_research_report(self, output_dir: Path, complaint: ComplaintInput) -> Optional[Path]:
        """Get the main research report file."""
        filename = f"{complaint.normalized_name}_research_report.md"
        file_path = output_dir / filename
        return file_path if file_path.exists() else None

    def get_metadata(self, output_dir: Path, complaint: ComplaintInput) -> Optional[Path]:
        """Get the metadata JSON file."""
        filename = f"{complaint.normalized_name}_metadata.json"
        file_path = output_dir / filename
        return file_path if file_path.exists() else None
