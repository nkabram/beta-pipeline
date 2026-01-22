"""Context aggregator for combining research outputs into unified context."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import (
    AggregatedResearchContext,
    ClinicalContextFindings,
    ClinicalContextItem,
    ComplaintInput,
    DemographicsFindings,
    FoundationFindings,
    PipelineConfig,
    PipelineState,
    ResearchApp,
    SynonymFindings,
)
from ..parsers import (
    ClaudeDeepResearchParser,
    OpenDeepResearchParser,
    OpenAIDeepResearchParser,
)

logger = logging.getLogger(__name__)


class ContextAggregator:
    """Aggregates research outputs from multiple apps into unified context.

    Implements the smart orchestration strategy:
    - Foundation + Clinical Context: Prefer open_deep_research
    - Demographics: Prefer openai_deep_research (PRIMARY source)
    - Synthesis: Use claude-deep-research
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.open_deep_parser = OpenDeepResearchParser()
        self.openai_parser = OpenAIDeepResearchParser()
        self.claude_parser = ClaudeDeepResearchParser()

    def aggregate(self, state: PipelineState) -> AggregatedResearchContext:
        """Aggregate findings from all successful research apps.

        Args:
            state: Pipeline state with app execution results

        Returns:
            AggregatedResearchContext with combined findings
        """
        complaint = state.complaint

        # Get output directories from successful apps
        output_dirs = {
            app: result.output_dir
            for app, result in state.app_results.items()
            if result.is_success and result.output_dir
        }

        # Parse foundation (prefer open_deep_research)
        foundation = self._get_best_foundation(complaint, output_dirs)

        # Parse demographics (prefer openai_deep_research - PRIMARY source)
        demographics = self._get_best_demographics(complaint, output_dirs)

        # Parse clinical context (prefer open_deep_research)
        clinical_context = self._get_best_clinical_context(complaint, output_dirs)

        # Parse synonyms (prefer open_deep_research)
        synonyms = self._get_best_synonyms(complaint, output_dirs)

        # Get synthesis from claude-deep-research
        synthesis_summary = None
        identified_gaps = []
        if ResearchApp.CLAUDE_DEEP_RESEARCH in output_dirs:
            claude_dir = output_dirs[ResearchApp.CLAUDE_DEEP_RESEARCH]
            synthesis_summary = self.claude_parser.extract_synthesis_summary(
                claude_dir, complaint
            )
            identified_gaps = self.claude_parser.extract_identified_gaps(
                claude_dir, complaint
            )

        # Count total sources
        total_sources = (
            len(foundation.sources if foundation else [])
            + len(demographics.sources if demographics else [])
            + len(clinical_context.sources if clinical_context else [])
            + len(synonyms.sources if synonyms else [])
        )

        return AggregatedResearchContext(
            complaint_name=complaint.complaint,
            complaint_type=complaint.complaint_type.value,
            foundation=foundation or self._create_empty_foundation(complaint),
            demographics=demographics or self._create_empty_demographics(complaint),
            clinical_context=clinical_context or self._create_empty_clinical_context(complaint),
            synonyms=synonyms or self._create_empty_synonyms(complaint),
            synthesis_summary=synthesis_summary,
            identified_gaps=identified_gaps,
            contributing_apps=list(output_dirs.keys()),
            total_sources=total_sources,
        )

    def _get_best_foundation(
        self,
        complaint: ComplaintInput,
        output_dirs: dict[ResearchApp, Path],
    ) -> Optional[FoundationFindings]:
        """Get foundation findings, preferring open_deep_research."""
        # Priority order: open_deep_research, openai_deep_research, claude_deep_research
        priority_order = [
            (ResearchApp.OPEN_DEEP_RESEARCH, self.open_deep_parser),
            (ResearchApp.OPENAI_DEEP_RESEARCH, self.openai_parser),
            (ResearchApp.CLAUDE_DEEP_RESEARCH, self.claude_parser),
        ]

        for app, parser in priority_order:
            if app in output_dirs:
                findings = parser.parse_foundation(output_dirs[app], complaint)
                if findings:
                    logger.info(f"Using foundation from {app.value}")
                    return findings

        return None

    def _get_best_demographics(
        self,
        complaint: ComplaintInput,
        output_dirs: dict[ResearchApp, Path],
    ) -> Optional[DemographicsFindings]:
        """Get demographics findings, preferring openai_deep_research (PRIMARY)."""
        # Priority order: openai_deep_research (PRIMARY), open_deep_research, claude_deep_research
        priority_order = [
            (ResearchApp.OPENAI_DEEP_RESEARCH, self.openai_parser),
            (ResearchApp.OPEN_DEEP_RESEARCH, self.open_deep_parser),
            (ResearchApp.CLAUDE_DEEP_RESEARCH, self.claude_parser),
        ]

        for app, parser in priority_order:
            if app in output_dirs:
                findings = parser.parse_demographics(output_dirs[app], complaint)
                if findings and (findings.age_findings or findings.sex_findings):
                    logger.info(f"Using demographics from {app.value}")
                    return findings

        return None

    def _get_best_clinical_context(
        self,
        complaint: ComplaintInput,
        output_dirs: dict[ResearchApp, Path],
    ) -> Optional[ClinicalContextFindings]:
        """Get clinical context findings, preferring open_deep_research."""
        priority_order = [
            (ResearchApp.OPEN_DEEP_RESEARCH, self.open_deep_parser),
            (ResearchApp.OPENAI_DEEP_RESEARCH, self.openai_parser),
            (ResearchApp.CLAUDE_DEEP_RESEARCH, self.claude_parser),
        ]

        for app, parser in priority_order:
            if app in output_dirs:
                findings = parser.parse_clinical_context(output_dirs[app], complaint)
                if findings:
                    logger.info(f"Using clinical context from {app.value}")
                    return findings

        return None

    def _get_best_synonyms(
        self,
        complaint: ComplaintInput,
        output_dirs: dict[ResearchApp, Path],
    ) -> Optional[SynonymFindings]:
        """Get synonym findings, preferring open_deep_research."""
        priority_order = [
            (ResearchApp.OPEN_DEEP_RESEARCH, self.open_deep_parser),
            (ResearchApp.OPENAI_DEEP_RESEARCH, self.openai_parser),
            (ResearchApp.CLAUDE_DEEP_RESEARCH, self.claude_parser),
        ]

        for app, parser in priority_order:
            if app in output_dirs:
                findings = parser.parse_synonyms(output_dirs[app], complaint)
                if findings and findings.medical_synonyms:
                    logger.info(f"Using synonyms from {app.value}")
                    return findings

        return None

    def _create_empty_foundation(self, complaint: ComplaintInput) -> FoundationFindings:
        """Create empty foundation findings as fallback."""
        return FoundationFindings(
            source_app=ResearchApp.OPEN_DEEP_RESEARCH,
            complaint_name=complaint.complaint,
        )

    def _create_empty_demographics(self, complaint: ComplaintInput) -> DemographicsFindings:
        """Create empty demographics findings as fallback."""
        return DemographicsFindings(
            source_app=ResearchApp.OPENAI_DEEP_RESEARCH,
            complaint_name=complaint.complaint,
        )

    def _create_empty_clinical_context(
        self, complaint: ComplaintInput
    ) -> ClinicalContextFindings:
        """Create empty clinical context findings as fallback."""
        return ClinicalContextFindings(
            source_app=ResearchApp.OPEN_DEEP_RESEARCH,
            complaint_name=complaint.complaint,
        )

    def _create_empty_synonyms(self, complaint: ComplaintInput) -> SynonymFindings:
        """Create empty synonym findings as fallback."""
        return SynonymFindings(
            source_app=ResearchApp.OPEN_DEEP_RESEARCH,
            complaint_name=complaint.complaint,
        )

    def write_beta_research_context(
        self,
        context: AggregatedResearchContext,
        output_dir: Path,
    ) -> Path:
        """Write aggregated context for beta_research consumption.

        Creates a resources directory that beta_research can read
        via --include-local flag.

        Args:
            context: Aggregated research context
            output_dir: Base output directory for the complaint

        Returns:
            Path to the resources directory
        """
        import json

        # Create resources directory
        resources_dir = output_dir / f"{context.complaint_name.lower().replace(' ', '_')}_resources"
        resources_dir.mkdir(parents=True, exist_ok=True)

        # Write context as JSON
        context_file = resources_dir / "aggregated_context.json"
        context_data = context.to_beta_research_format()
        context_file.write_text(json.dumps(context_data, indent=2, default=str))

        # Write summary markdown for human readability
        summary_file = resources_dir / "research_summary.md"
        summary_content = self._generate_summary_markdown(context)
        summary_file.write_text(summary_content)

        logger.info(f"Wrote beta_research context to {resources_dir}")
        return resources_dir

    def _generate_summary_markdown(self, context: AggregatedResearchContext) -> str:
        """Generate a human-readable summary of aggregated findings."""
        lines = [
            f"# Research Summary: {context.complaint_name}",
            f"\nGenerated: {context.generated_at.isoformat()}",
            f"Type: {context.complaint_type}",
            f"Contributing apps: {', '.join(app.value for app in context.contributing_apps)}",
            f"Total sources: {context.total_sources}",
            "",
            "## Foundation",
        ]

        if context.foundation:
            if context.foundation.prevalence:
                lines.append(f"- Prevalence: {context.foundation.prevalence}")
            if context.foundation.differential_diagnoses:
                lines.append(f"- Differential diagnoses: {len(context.foundation.differential_diagnoses)}")
            if context.foundation.red_flags:
                lines.append(f"- Red flags: {len(context.foundation.red_flags)}")

        lines.extend(["", "## Demographics"])

        if context.demographics:
            lines.append(f"- Age groups analyzed: {len(context.demographics.age_findings)}")
            lines.append(f"- Sex-based findings: {len(context.demographics.sex_findings)}")
            lines.append(f"- Special populations: {len(context.demographics.special_population_findings)}")
            if context.demographics.created_modifiers:
                lines.append(f"- Modifiers created: {', '.join(context.demographics.created_modifiers)}")

        lines.extend(["", "## Clinical Context"])

        if context.clinical_context:
            for category in [
                "diagnostic",
                "risk_stratification",
                "management",
                "testing",
                "treatment",
            ]:
                items = getattr(context.clinical_context, category, [])
                if items:
                    lines.append(f"- {category.replace('_', ' ').title()}: {len(items)} items")

        if context.synthesis_summary:
            lines.extend(["", "## Synthesis", context.synthesis_summary])

        if context.identified_gaps:
            lines.extend(["", "## Identified Gaps"])
            for gap in context.identified_gaps:
                lines.append(f"- {gap}")

        return "\n".join(lines)
