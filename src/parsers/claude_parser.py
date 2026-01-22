"""Parser for claude-deep-research outputs."""

import re
from pathlib import Path
from typing import Any, Optional

from ..models import (
    AgeGroup,
    ClinicalContextFindings,
    ClinicalContextItem,
    ComplaintInput,
    DemographicFinding,
    DemographicsFindings,
    FoundationFindings,
    ResearchApp,
    Sex,
    SpecialPopulation,
    SynonymEntry,
    SynonymFindings,
)
from .base import BaseParser


class ClaudeDeepResearchParser(BaseParser):
    """Parser for claude-deep-research output files.

    Parses:
    - {complaint}_research_report.md (synthesized report)
    - {complaint}_metadata.json

    Note: claude-deep-research produces a single synthesized report,
    not separate phase files. This parser extracts relevant sections
    from the unified report.
    """

    @property
    def app(self) -> ResearchApp:
        return ResearchApp.CLAUDE_DEEP_RESEARCH

    def _get_file_path(self, output_dir: Path, complaint: ComplaintInput, suffix: str) -> Path:
        """Construct file path for a given output type."""
        return output_dir / f"{complaint.normalized_name}{suffix}"

    def _parse_foundation_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[FoundationFindings]:
        """Parse foundation from synthesized report."""
        file_path = self._get_file_path(output_dir, complaint, "_research_report.md")
        content = self._read_file(file_path)
        if not content:
            return None

        # Extract key findings / executive summary
        exec_summary = self._extract_section(content, "Executive Summary|Summary|Overview")

        # Extract epidemiology if present
        prevalence = None
        incidence = None
        epidemiology_section = self._extract_section(content, "Epidemiology")
        if epidemiology_section:
            prev_match = re.search(r"prevalence[:\s]+([^\.]+)", epidemiology_section, re.I)
            if prev_match:
                prevalence = prev_match.group(1).strip()
            inc_match = re.search(r"incidence[:\s]+([^\.]+)", epidemiology_section, re.I)
            if inc_match:
                incidence = inc_match.group(1).strip()

        # Extract differential
        diff_section = self._extract_section(content, "Differential|Key Findings")
        differential = []
        if diff_section:
            items = self._extract_list_items(diff_section)
            for item in items:
                differential.append({"diagnosis": item})

        # Extract red flags
        red_flags_section = self._extract_section(content, "Red Flags|Critical|Urgent")
        red_flags = self._extract_list_items(red_flags_section) if red_flags_section else []

        # Extract etiologies
        etiology_section = self._extract_section(content, "Etiology|Causes|Pathology")
        etiologies = self._extract_list_items(etiology_section) if etiology_section else []

        sources = self._extract_sources(content)

        return FoundationFindings(
            source_app=self.app,
            complaint_name=complaint.complaint,
            prevalence=prevalence,
            incidence=incidence,
            common_etiologies=etiologies,
            differential_diagnoses=differential,
            red_flags=red_flags,
            pathophysiology_summary=exec_summary[:500] if exec_summary else None,
            sources=sources,
            raw_content=content,
        )

    def _parse_demographics_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[DemographicsFindings]:
        """Parse demographics from synthesized report.

        Claude's synthesized report may contain demographics data,
        but this is NOT the primary source - openai_deep_research is.
        """
        file_path = self._get_file_path(output_dir, complaint, "_research_report.md")
        content = self._read_file(file_path)
        if not content:
            return None

        age_findings: dict[str, list[DemographicFinding]] = {}
        sex_findings: dict[str, list[DemographicFinding]] = {}
        special_pop_findings: dict[str, list[DemographicFinding]] = {}
        created_modifiers: list[str] = []

        # Look for age-related sections
        age_section = self._extract_section(content, "Age|Demographics|Population")
        if age_section:
            # Parse any age-specific findings
            for age_keyword, age_group in [
                ("pediatric|child", AgeGroup.SCHOOL_AGE),
                ("adolescent|teen", AgeGroup.ADOLESCENT),
                ("adult", AgeGroup.YOUNG_ADULT),
                ("elderly|geriatric|older", AgeGroup.GERIATRIC),
            ]:
                pattern = rf"(?:{age_keyword})[:\s]+([^\.]+\.)"
                matches = re.findall(pattern, age_section, re.I)
                if matches:
                    findings = [
                        DemographicFinding(
                            age_group=age_group,
                            finding_type="general",
                            content=m.strip(),
                        )
                        for m in matches
                    ]
                    age_findings[age_group.value] = findings

        # Look for sex-related findings
        sex_section = self._extract_section(content, "Sex|Gender")
        if sex_section:
            for sex_keyword, sex_enum in [("male", Sex.MALE), ("female", Sex.FEMALE)]:
                pattern = rf"{sex_keyword}s?[:\s]+([^\.]+\.)"
                matches = re.findall(pattern, sex_section, re.I)
                if matches:
                    findings = [
                        DemographicFinding(
                            sex=sex_enum,
                            finding_type="general",
                            content=m.strip(),
                        )
                        for m in matches
                    ]
                    sex_findings[sex_enum.value] = findings

        sources = self._extract_sources(content)

        return DemographicsFindings(
            source_app=self.app,
            complaint_name=complaint.complaint,
            age_findings=age_findings,
            sex_findings=sex_findings,
            special_population_findings=special_pop_findings,
            created_modifiers=created_modifiers,
            sources=sources,
            raw_content=content,
        )

    def _parse_clinical_context_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[ClinicalContextFindings]:
        """Parse clinical context from synthesized report."""
        file_path = self._get_file_path(output_dir, complaint, "_research_report.md")
        content = self._read_file(file_path)
        if not content:
            return None

        findings = ClinicalContextFindings(
            source_app=self.app,
            complaint_name=complaint.complaint,
            raw_content=content,
        )

        # Extract available clinical context
        section_mappings = [
            ("Diagnostic|Diagnosis|Workup", "diagnostic"),
            ("Risk|Stratification|Scoring", "risk_stratification"),
            ("Management|Approach", "management"),
            ("Testing|Labs|Imaging", "testing"),
            ("Treatment|Therapy|Medication", "treatment"),
            ("Decision|Clinical Tools|Calculators", "decision_support"),
            ("Documentation|Legal|Liability", "medicolegal"),
        ]

        for section_pattern, attr_name in section_mappings:
            section = self._extract_section(content, section_pattern)
            if section:
                items = [
                    ClinicalContextItem(
                        category=attr_name,
                        title=item[:50],
                        content=item,
                    )
                    for item in self._extract_list_items(section)
                ]
                setattr(findings, attr_name, items)

        findings.sources = self._extract_sources(content)
        return findings

    def _parse_synonyms_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[SynonymFindings]:
        """Parse synonyms from synthesized report.

        Note: Claude's report may not have dedicated synonym section.
        Returns minimal findings if present.
        """
        file_path = self._get_file_path(output_dir, complaint, "_research_report.md")
        content = self._read_file(file_path)
        if not content:
            return None

        findings = SynonymFindings(
            source_app=self.app,
            complaint_name=complaint.complaint,
            raw_content=content,
        )

        # Look for synonym/terminology section
        synonym_section = self._extract_section(content, "Synonym|Terminology|Also Known As")
        if synonym_section:
            items = self._extract_list_items(synonym_section)
            findings.medical_synonyms = [
                SynonymEntry(term=item, term_type="medical_synonym", confidence=0.6)
                for item in items
            ]

        findings.sources = self._extract_sources(content)
        return findings

    def extract_synthesis_summary(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[str]:
        """Extract the synthesis summary for aggregation.

        This is the primary value from claude-deep-research -
        the synthesized overview and gap analysis.
        """
        file_path = self._get_file_path(output_dir, complaint, "_research_report.md")
        content = self._read_file(file_path)
        if not content:
            return None

        # Get executive summary or conclusions
        summary = self._extract_section(content, "Executive Summary|Conclusions|Summary")
        if summary:
            return summary

        # Fallback: return first 1000 chars
        return content[:1000] if content else None

    def extract_identified_gaps(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> list[str]:
        """Extract identified gaps or limitations from the report."""
        file_path = self._get_file_path(output_dir, complaint, "_research_report.md")
        content = self._read_file(file_path)
        if not content:
            return []

        gaps = []

        # Look for gaps/limitations section
        gaps_section = self._extract_section(content, "Gaps|Limitations|Future|Considerations")
        if gaps_section:
            gaps = self._extract_list_items(gaps_section)

        return gaps

    def get_metadata(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[dict[str, Any]]:
        """Get execution metadata."""
        metadata_path = self._get_file_path(output_dir, complaint, "_metadata.json")
        return self._read_json(metadata_path)
