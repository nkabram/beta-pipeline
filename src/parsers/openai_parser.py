"""Parser for openai_deep_research outputs."""

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


class OpenAIDeepResearchParser(BaseParser):
    """Parser for openai_deep_research output files.

    Parses:
    - Phase 1: {complaint}_phase1_foundation_clinical.md
    - Phase 2: {complaint}_phase2_demographics.md
    - Phase 3: {complaint}_phase3_synonyms.md
    - Metadata: {complaint}_metadata.json
    """

    @property
    def app(self) -> ResearchApp:
        return ResearchApp.OPENAI_DEEP_RESEARCH

    def _get_file_path(self, output_dir: Path, complaint: ComplaintInput, suffix: str) -> Path:
        """Construct file path for a given output type."""
        return output_dir / f"{complaint.normalized_name}{suffix}"

    def _parse_foundation_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[FoundationFindings]:
        """Parse Phase 1: Foundation + Clinical."""
        file_path = self._get_file_path(
            output_dir, complaint, "_phase1_foundation_clinical.md"
        )
        content = self._read_file(file_path)
        if not content:
            return None

        # Also try to read metadata for additional context
        metadata_path = self._get_file_path(output_dir, complaint, "_metadata.json")
        metadata = self._read_json(metadata_path) or {}

        # Extract epidemiology
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

        # Extract differential diagnosis
        diff_section = self._extract_section(content, "Differential Diagnosis")
        differential = []
        if diff_section:
            items = self._extract_list_items(diff_section)
            for item in items:
                differential.append({"diagnosis": item})

        # Extract red flags
        red_flags_section = self._extract_section(content, "Red Flags|Critical Findings")
        red_flags = self._extract_list_items(red_flags_section) if red_flags_section else []

        # Extract etiologies
        etiology_section = self._extract_section(content, "Etiology|Causes")
        etiologies = self._extract_list_items(etiology_section) if etiology_section else []

        # Extract pathophysiology
        patho_section = self._extract_section(content, "Pathophysiology")
        pathophysiology = patho_section[:500] if patho_section else None

        sources = self._extract_sources(content)

        return FoundationFindings(
            source_app=self.app,
            complaint_name=complaint.complaint,
            prevalence=prevalence,
            incidence=incidence,
            common_etiologies=etiologies,
            differential_diagnoses=differential,
            red_flags=red_flags,
            pathophysiology_summary=pathophysiology,
            sources=sources,
            raw_content=content,
        )

    def _parse_demographics_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[DemographicsFindings]:
        """Parse Phase 2: Demographics Analysis.

        This is the PRIMARY demographics source in the pipeline.
        """
        file_path = self._get_file_path(
            output_dir, complaint, "_phase2_demographics.md"
        )
        content = self._read_file(file_path)
        if not content:
            return None

        age_findings: dict[str, list[DemographicFinding]] = {}
        sex_findings: dict[str, list[DemographicFinding]] = {}
        special_pop_findings: dict[str, list[DemographicFinding]] = {}
        created_modifiers: list[str] = []

        # Parse Part A: Age-Stratified Analysis
        age_section = self._extract_section(content, "Part A|Age-Stratified|Age Groups")
        if age_section:
            age_findings, age_modifiers = self._parse_age_stratified_section(age_section)
            created_modifiers.extend(age_modifiers)

        # Parse Part B: Sex-Based Analysis
        sex_section = self._extract_section(content, "Part B|Sex-Based|Sex Differences")
        if sex_section:
            sex_findings, sex_modifiers = self._parse_sex_based_section(sex_section)
            created_modifiers.extend(sex_modifiers)

        # Parse Part C: Special Populations
        special_section = self._extract_section(content, "Part C|Special Populations")
        if special_section:
            special_pop_findings, pop_modifiers = self._parse_special_populations_section(
                special_section
            )
            created_modifiers.extend(pop_modifiers)

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

    def _parse_age_stratified_section(
        self, content: str
    ) -> tuple[dict[str, list[DemographicFinding]], list[str]]:
        """Parse age-stratified section into findings."""
        findings: dict[str, list[DemographicFinding]] = {}
        modifiers: list[str] = []

        age_patterns = [
            (r"Neonatal|0-28\s*days", AgeGroup.NEONATAL),
            (r"Infant|1-12\s*months", AgeGroup.INFANT),
            (r"Toddler|Preschool|1-5\s*years", AgeGroup.TODDLER_PRESCHOOL),
            (r"School\s*Age|6-11\s*years", AgeGroup.SCHOOL_AGE),
            (r"Adolescent|12-17\s*years", AgeGroup.ADOLESCENT),
            (r"Young\s*Adult|18-39\s*years", AgeGroup.YOUNG_ADULT),
            (r"Middle\s*Age|40-64\s*years", AgeGroup.MIDDLE_AGE),
            (r"Older\s*Adult|65-79\s*years", AgeGroup.OLDER_ADULT),
            (r"Geriatric|80\+|Elderly", AgeGroup.GERIATRIC),
        ]

        for pattern, age_group in age_patterns:
            # Find section for this age group
            section_pattern = rf"#{2,4}\s+.*(?:{pattern}).*?\n(.*?)(?=#{2,4}|\Z)"
            match = re.search(section_pattern, content, re.I | re.DOTALL)
            if match:
                subsection = match.group(1)
                group_findings = self._extract_findings_from_subsection(
                    subsection, age_group=age_group
                )
                if group_findings:
                    findings[age_group.value] = group_findings

                # Check for modifier creation
                if re.search(r"modifier\s+(created|CREATED)", subsection, re.I):
                    modifiers.append(age_group.value)

        return findings, modifiers

    def _parse_sex_based_section(
        self, content: str
    ) -> tuple[dict[str, list[DemographicFinding]], list[str]]:
        """Parse sex-based section into findings."""
        findings: dict[str, list[DemographicFinding]] = {}
        modifiers: list[str] = []

        for sex_keyword, sex_enum in [("male", Sex.MALE), ("female", Sex.FEMALE)]:
            pattern = rf"#{2,4}\s+.*{sex_keyword}.*?\n(.*?)(?=#{2,4}|\Z)"
            match = re.search(pattern, content, re.I | re.DOTALL)
            if match:
                subsection = match.group(1)
                sex_findings = self._extract_findings_from_subsection(subsection, sex=sex_enum)
                if sex_findings:
                    findings[sex_enum.value] = sex_findings

                if re.search(r"modifier\s+(created|CREATED)", subsection, re.I):
                    modifiers.append(sex_enum.value)

        return findings, modifiers

    def _parse_special_populations_section(
        self, content: str
    ) -> tuple[dict[str, list[DemographicFinding]], list[str]]:
        """Parse special populations section into findings."""
        findings: dict[str, list[DemographicFinding]] = {}
        modifiers: list[str] = []

        pop_patterns = [
            (r"Pregnan", SpecialPopulation.PREGNANCY),
            (r"Postpartum", SpecialPopulation.POSTPARTUM),
            (r"Immunocompromised|HIV|Transplant", SpecialPopulation.IMMUNOCOMPROMISED),
            (r"Chronic Disease|Diabetes|CKD|COPD|CHF", SpecialPopulation.CHRONIC_DISEASE),
            (r"Substance|Drug|Alcohol", SpecialPopulation.SUBSTANCE_USE),
            (r"Psychiatric|Mental Health", SpecialPopulation.PSYCHIATRIC_COMORBIDITY),
            (r"Homeless|Social Determinants", SpecialPopulation.SOCIAL_DETERMINANTS),
        ]

        for pattern, pop_enum in pop_patterns:
            section_pattern = rf"#{2,4}\s+.*(?:{pattern}).*?\n(.*?)(?=#{2,4}|\Z)"
            match = re.search(section_pattern, content, re.I | re.DOTALL)
            if match:
                subsection = match.group(1)
                pop_findings = self._extract_findings_from_subsection(
                    subsection, special_population=pop_enum
                )
                if pop_findings:
                    findings[pop_enum.value] = pop_findings

                if re.search(r"modifier\s+(created|CREATED)", subsection, re.I):
                    modifiers.append(pop_enum.value)

        return findings, modifiers

    def _extract_findings_from_subsection(
        self,
        content: str,
        age_group: Optional[AgeGroup] = None,
        sex: Optional[Sex] = None,
        special_population: Optional[SpecialPopulation] = None,
    ) -> list[DemographicFinding]:
        """Extract findings from a demographic subsection."""
        findings = []
        items = self._extract_list_items(content)

        for item in items:
            finding_type = self._classify_finding_type(item)
            priority_score = self._extract_priority_score(content)

            findings.append(
                DemographicFinding(
                    age_group=age_group,
                    sex=sex,
                    special_population=special_population,
                    finding_type=finding_type,
                    content=item,
                    priority_score=priority_score,
                )
            )

        return findings

    def _classify_finding_type(self, text: str) -> str:
        """Classify the type of finding based on content."""
        text_lower = text.lower()
        if any(word in text_lower for word in ["diagnos", "etiology", "cause", "differential"]):
            return "differential"
        elif any(word in text_lower for word in ["present", "symptom", "sign", "manifest"]):
            return "presentation"
        elif any(word in text_lower for word in ["treat", "medication", "dose", "therapy"]):
            return "treatment"
        elif any(word in text_lower for word in ["risk", "prognos", "complication"]):
            return "risk"
        return "general"

    def _extract_priority_score(self, content: str) -> Optional[int]:
        """Extract priority score if present."""
        match = re.search(r"priority\s*(?:score)?[:\s]+(\d+)", content, re.I)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    def _parse_clinical_context_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[ClinicalContextFindings]:
        """Parse clinical context from Phase 1."""
        file_path = self._get_file_path(
            output_dir, complaint, "_phase1_foundation_clinical.md"
        )
        content = self._read_file(file_path)
        if not content:
            return None

        findings = ClinicalContextFindings(
            source_app=self.app,
            complaint_name=complaint.complaint,
            raw_content=content,
        )

        # Parse clinical context categories
        for section_name, attr_name in [
            ("Diagnostic", "diagnostic"),
            ("Risk Stratification", "risk_stratification"),
            ("Management", "management"),
            ("Testing|Laboratory|Imaging", "testing"),
            ("Treatment|Therapy", "treatment"),
            ("Decision Support|Clinical Tools", "decision_support"),
            ("Medicolegal|Documentation", "medicolegal"),
        ]:
            section = self._extract_section(content, section_name)
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
        """Parse Phase 3: Synonyms."""
        file_path = self._get_file_path(
            output_dir, complaint, "_phase3_synonyms.md"
        )
        content = self._read_file(file_path)
        if not content:
            return None

        findings = SynonymFindings(
            source_app=self.app,
            complaint_name=complaint.complaint,
            raw_content=content,
        )

        # Parse synonym sections
        sections = {
            "Medical Synonyms": ("medical_synonyms", "medical_synonym"),
            "Abbreviations": ("abbreviations", "abbreviation"),
            "Lay Terms|Patient Language": ("lay_terms", "lay_term"),
            "Regional Variations": ("regional_variations", "regional_variation"),
            "Pediatric|Parent Terms": ("pediatric_terms", "pediatric_term"),
        }

        for section_pattern, (attr_name, term_type) in sections.items():
            section = self._extract_section(content, section_pattern)
            if section:
                entries = self._parse_synonym_section(section, term_type)
                setattr(findings, attr_name, entries)

        findings.sources = self._extract_sources(content)
        return findings

    def _parse_synonym_section(self, content: str, term_type: str) -> list[SynonymEntry]:
        """Parse a synonym section into entries."""
        entries = []
        items = self._extract_list_items(content)

        for item in items:
            # Extract confidence if present
            confidence = 0.7
            conf_match = re.search(r"\(([0-9.]+)\)", item)
            if conf_match:
                try:
                    confidence = float(conf_match.group(1))
                except ValueError:
                    pass

            term = re.sub(r"\s*\([0-9.]+\)\s*", "", item).strip()
            if term:
                entries.append(
                    SynonymEntry(
                        term=term,
                        term_type=term_type,
                        confidence=min(1.0, max(0.0, confidence)),
                    )
                )

        return entries
