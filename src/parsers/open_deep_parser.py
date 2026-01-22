"""Parser for open_deep_research outputs."""

import re
from pathlib import Path
from typing import Optional

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


class OpenDeepResearchParser(BaseParser):
    """Parser for open_deep_research (LangChain) output files.

    Parses:
    - Phase A: {complaint}_foundation_clinical_context.md
    - Phase B: {complaint}_demographics_analysis.md
    - Phase C: {complaint}_synonym_terminology.md
    """

    @property
    def app(self) -> ResearchApp:
        return ResearchApp.OPEN_DEEP_RESEARCH

    def _get_file_path(self, output_dir: Path, complaint: ComplaintInput, suffix: str) -> Path:
        """Construct file path for a given output type."""
        return output_dir / f"{complaint.normalized_name}{suffix}"

    def _parse_foundation_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[FoundationFindings]:
        """Parse Phase A: Foundation + Clinical Context."""
        file_path = self._get_file_path(
            output_dir, complaint, "_foundation_clinical_context.md"
        )
        content = self._read_file(file_path)
        if not content:
            return None

        # Extract epidemiology section
        prevalence = None
        incidence = None
        epidemiology_section = self._extract_section(content, "Epidemiology")
        if epidemiology_section:
            # Look for prevalence/incidence patterns
            prev_match = re.search(r"prevalence[:\s]+([^\.]+)", epidemiology_section, re.I)
            if prev_match:
                prevalence = prev_match.group(1).strip()
            inc_match = re.search(r"incidence[:\s]+([^\.]+)", epidemiology_section, re.I)
            if inc_match:
                incidence = inc_match.group(1).strip()

        # Extract etiologies
        etiologies_section = self._extract_section(content, "Etiology|Etiologies|Common Causes")
        etiologies = []
        if etiologies_section:
            etiologies = self._extract_list_items(etiologies_section)

        # Extract differential diagnosis
        diff_section = self._extract_section(content, "Differential Diagnosis|Differential")
        differential = []
        if diff_section:
            items = self._extract_list_items(diff_section)
            for item in items:
                differential.append({"diagnosis": item})

        # Extract red flags
        red_flags_section = self._extract_section(content, "Red Flags|Warning Signs")
        red_flags = []
        if red_flags_section:
            red_flags = self._extract_list_items(red_flags_section)

        # Extract pathophysiology
        patho_section = self._extract_section(content, "Pathophysiology")
        pathophysiology = patho_section[:500] if patho_section else None

        # Extract sources
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
        """Parse Phase B: Demographics Analysis."""
        file_path = self._get_file_path(
            output_dir, complaint, "_demographics_analysis.md"
        )
        content = self._read_file(file_path)
        if not content:
            return None

        age_findings: dict[str, list[DemographicFinding]] = {}
        sex_findings: dict[str, list[DemographicFinding]] = {}
        special_pop_findings: dict[str, list[DemographicFinding]] = {}
        created_modifiers: list[str] = []

        # Map of section headers to age groups
        age_group_mapping = {
            "neonatal": AgeGroup.NEONATAL,
            "infant": AgeGroup.INFANT,
            "toddler": AgeGroup.TODDLER_PRESCHOOL,
            "preschool": AgeGroup.TODDLER_PRESCHOOL,
            "school": AgeGroup.SCHOOL_AGE,
            "adolescent": AgeGroup.ADOLESCENT,
            "young adult": AgeGroup.YOUNG_ADULT,
            "middle age": AgeGroup.MIDDLE_AGE,
            "older adult": AgeGroup.OLDER_ADULT,
            "geriatric": AgeGroup.GERIATRIC,
            "elderly": AgeGroup.GERIATRIC,
        }

        # Parse age-stratified sections
        age_section = self._extract_section(content, "Age-Stratified|Age Stratification|Age Groups")
        if age_section:
            for keyword, age_group in age_group_mapping.items():
                pattern = rf"#{2,4}\s+.*{keyword}.*?\n(.*?)(?=#{2,4}|\Z)"
                match = re.search(pattern, age_section, re.I | re.DOTALL)
                if match:
                    subsection = match.group(1)
                    findings = self._extract_demographic_findings(subsection, age_group=age_group)
                    if findings:
                        age_findings[age_group.value] = findings
                        if self._section_indicates_modifier(subsection):
                            created_modifiers.append(age_group.value)

        # Parse sex-based sections
        sex_section = self._extract_section(content, "Sex-Based|Sex Differences|Gender")
        if sex_section:
            for sex_keyword, sex_enum in [("male", Sex.MALE), ("female", Sex.FEMALE)]:
                pattern = rf"#{2,4}\s+.*{sex_keyword}.*?\n(.*?)(?=#{2,4}|\Z)"
                match = re.search(pattern, sex_section, re.I | re.DOTALL)
                if match:
                    subsection = match.group(1)
                    findings = self._extract_demographic_findings(subsection, sex=sex_enum)
                    if findings:
                        sex_findings[sex_enum.value] = findings
                        if self._section_indicates_modifier(subsection):
                            created_modifiers.append(sex_enum.value)

        # Parse special population sections
        special_section = self._extract_section(content, "Special Populations|Special Groups")
        if special_section:
            pop_mapping = {
                "pregnan": SpecialPopulation.PREGNANCY,
                "postpartum": SpecialPopulation.POSTPARTUM,
                "immunocompromised": SpecialPopulation.IMMUNOCOMPROMISED,
                "chronic disease": SpecialPopulation.CHRONIC_DISEASE,
                "diabetes": SpecialPopulation.CHRONIC_DISEASE,
                "substance": SpecialPopulation.SUBSTANCE_USE,
                "psychiatric": SpecialPopulation.PSYCHIATRIC_COMORBIDITY,
                "homeless": SpecialPopulation.SOCIAL_DETERMINANTS,
            }
            for keyword, pop_enum in pop_mapping.items():
                pattern = rf"#{2,4}\s+.*{keyword}.*?\n(.*?)(?=#{2,4}|\Z)"
                match = re.search(pattern, special_section, re.I | re.DOTALL)
                if match:
                    subsection = match.group(1)
                    findings = self._extract_demographic_findings(
                        subsection, special_population=pop_enum
                    )
                    if findings:
                        special_pop_findings[pop_enum.value] = findings
                        if self._section_indicates_modifier(subsection):
                            created_modifiers.append(pop_enum.value)

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

    def _extract_demographic_findings(
        self,
        content: str,
        age_group: Optional[AgeGroup] = None,
        sex: Optional[Sex] = None,
        special_population: Optional[SpecialPopulation] = None,
    ) -> list[DemographicFinding]:
        """Extract demographic findings from a section."""
        findings = []
        items = self._extract_list_items(content)

        for item in items:
            # Determine finding type from content
            finding_type = "general"
            if any(word in item.lower() for word in ["diagnos", "etiology", "cause"]):
                finding_type = "differential"
            elif any(word in item.lower() for word in ["present", "symptom", "sign"]):
                finding_type = "presentation"
            elif any(word in item.lower() for word in ["treat", "medication", "dose"]):
                finding_type = "treatment"
            elif any(word in item.lower() for word in ["risk", "prognos"]):
                finding_type = "risk"

            findings.append(
                DemographicFinding(
                    age_group=age_group,
                    sex=sex,
                    special_population=special_population,
                    finding_type=finding_type,
                    content=item,
                )
            )

        return findings

    def _section_indicates_modifier(self, content: str) -> bool:
        """Check if section content indicates a modifier should be created."""
        # Look for explicit modifier indicators
        modifier_patterns = [
            r"modifier\s+(created|warranted|recommended)",
            r"clinically\s+significant",
            r"unique\s+(diagnosis|presentation|consideration)",
            r"different\s+(approach|management|treatment)",
        ]
        for pattern in modifier_patterns:
            if re.search(pattern, content, re.I):
                return True
        return False

    def _parse_clinical_context_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[ClinicalContextFindings]:
        """Parse clinical context from Phase A."""
        file_path = self._get_file_path(
            output_dir, complaint, "_foundation_clinical_context.md"
        )
        content = self._read_file(file_path)
        if not content:
            return None

        findings = ClinicalContextFindings(
            source_app=self.app,
            complaint_name=complaint.complaint,
            raw_content=content,
        )

        # Parse each of the 7 clinical context categories
        category_mapping = {
            "Diagnostic": "diagnostic",
            "Risk Stratification": "risk_stratification",
            "Management": "management",
            "Testing": "testing",
            "Treatment": "treatment",
            "Decision Support": "decision_support",
            "Medicolegal": "medicolegal",
        }

        for section_name, attr_name in category_mapping.items():
            section = self._extract_section(content, section_name)
            if section:
                items = self._extract_clinical_context_items(section, section_name.lower())
                setattr(findings, attr_name, items)

        findings.sources = self._extract_sources(content)
        return findings

    def _extract_clinical_context_items(
        self, content: str, category: str
    ) -> list[ClinicalContextItem]:
        """Extract clinical context items from a section."""
        items = []
        list_items = self._extract_list_items(content)

        for item_text in list_items:
            items.append(
                ClinicalContextItem(
                    category=category,
                    title=item_text[:50] if len(item_text) > 50 else item_text,
                    content=item_text,
                )
            )

        return items

    def _parse_synonyms_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[SynonymFindings]:
        """Parse Phase C: Synonym & Terminology."""
        file_path = self._get_file_path(
            output_dir, complaint, "_synonym_terminology.md"
        )
        content = self._read_file(file_path)
        if not content:
            return None

        findings = SynonymFindings(
            source_app=self.app,
            complaint_name=complaint.complaint,
            raw_content=content,
        )

        # Parse each synonym category
        synonym_sections = {
            "Medical Synonyms": ("medical_synonyms", "medical_synonym"),
            "Abbreviations": ("abbreviations", "abbreviation"),
            "Lay Terms": ("lay_terms", "lay_term"),
            "Regional Variations": ("regional_variations", "regional_variation"),
            "Pediatric Terms": ("pediatric_terms", "pediatric_term"),
        }

        for section_name, (attr_name, term_type) in synonym_sections.items():
            section = self._extract_section(content, section_name)
            if section:
                entries = self._extract_synonym_entries(section, term_type)
                setattr(findings, attr_name, entries)

        findings.sources = self._extract_sources(content)
        return findings

    def _extract_synonym_entries(self, content: str, term_type: str) -> list[SynonymEntry]:
        """Extract synonym entries from a section."""
        entries = []
        items = self._extract_list_items(content)

        for item in items:
            # Try to extract confidence if present (e.g., "term (0.85)")
            confidence = 0.7  # default
            conf_match = re.search(r"\(([0-9.]+)\)", item)
            if conf_match:
                try:
                    confidence = float(conf_match.group(1))
                except ValueError:
                    pass

            # Clean the term
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
