"""Base parser class for extracting structured data from research outputs."""

import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from ..models import (
    ClinicalContextFindings,
    ClinicalContextItem,
    ComplaintInput,
    DemographicFinding,
    DemographicsFindings,
    FoundationFindings,
    ResearchApp,
    SourceReference,
    SynonymEntry,
    SynonymFindings,
)

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Base class for parsing research application outputs."""

    @property
    @abstractmethod
    def app(self) -> ResearchApp:
        """Return the ResearchApp enum for this parser."""
        ...

    def parse_foundation(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[FoundationFindings]:
        """Parse foundation/epidemiology findings.

        Args:
            output_dir: Directory containing output files
            complaint: The complaint that was researched

        Returns:
            FoundationFindings or None if not found/parseable
        """
        try:
            return self._parse_foundation_impl(output_dir, complaint)
        except Exception as e:
            logger.error(f"Error parsing foundation from {self.app}: {e}")
            return None

    def parse_demographics(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[DemographicsFindings]:
        """Parse demographics analysis findings.

        Args:
            output_dir: Directory containing output files
            complaint: The complaint that was researched

        Returns:
            DemographicsFindings or None if not found/parseable
        """
        try:
            return self._parse_demographics_impl(output_dir, complaint)
        except Exception as e:
            logger.error(f"Error parsing demographics from {self.app}: {e}")
            return None

    def parse_clinical_context(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[ClinicalContextFindings]:
        """Parse clinical context findings.

        Args:
            output_dir: Directory containing output files
            complaint: The complaint that was researched

        Returns:
            ClinicalContextFindings or None if not found/parseable
        """
        try:
            return self._parse_clinical_context_impl(output_dir, complaint)
        except Exception as e:
            logger.error(f"Error parsing clinical context from {self.app}: {e}")
            return None

    def parse_synonyms(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[SynonymFindings]:
        """Parse synonym/terminology findings.

        Args:
            output_dir: Directory containing output files
            complaint: The complaint that was researched

        Returns:
            SynonymFindings or None if not found/parseable
        """
        try:
            return self._parse_synonyms_impl(output_dir, complaint)
        except Exception as e:
            logger.error(f"Error parsing synonyms from {self.app}: {e}")
            return None

    @abstractmethod
    def _parse_foundation_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[FoundationFindings]:
        """Implementation of foundation parsing."""
        ...

    @abstractmethod
    def _parse_demographics_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[DemographicsFindings]:
        """Implementation of demographics parsing."""
        ...

    @abstractmethod
    def _parse_clinical_context_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[ClinicalContextFindings]:
        """Implementation of clinical context parsing."""
        ...

    @abstractmethod
    def _parse_synonyms_impl(
        self,
        output_dir: Path,
        complaint: ComplaintInput,
    ) -> Optional[SynonymFindings]:
        """Implementation of synonyms parsing."""
        ...

    # Helper methods for markdown parsing

    def _read_file(self, file_path: Path) -> Optional[str]:
        """Read a file and return its content."""
        if not file_path.exists():
            return None
        return file_path.read_text(encoding="utf-8")

    def _read_json(self, file_path: Path) -> Optional[dict[str, Any]]:
        """Read a JSON file and return its content."""
        content = self._read_file(file_path)
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {file_path}")
            return None

    def _extract_section(
        self,
        content: str,
        section_header: str,
        next_section_pattern: str = r"^#{1,3}\s+",
    ) -> Optional[str]:
        """Extract a section from markdown content.

        Args:
            content: Full markdown content
            section_header: Header to look for (without #)
            next_section_pattern: Regex pattern for next section start

        Returns:
            Section content or None if not found
        """
        # Find the section header
        pattern = rf"^#{1,3}\s+{re.escape(section_header)}\s*$"
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)

        if not match:
            return None

        start = match.end()

        # Find the next section header
        next_match = re.search(next_section_pattern, content[start:], re.MULTILINE)

        if next_match:
            end = start + next_match.start()
        else:
            end = len(content)

        return content[start:end].strip()

    def _extract_list_items(self, content: str) -> list[str]:
        """Extract list items from markdown content.

        Args:
            content: Markdown content with list items

        Returns:
            List of item texts
        """
        pattern = r"^[\-\*]\s+(.+)$"
        matches = re.findall(pattern, content, re.MULTILINE)
        return [m.strip() for m in matches]

    def _extract_sources(self, content: str) -> list[SourceReference]:
        """Extract source references from markdown content.

        Looks for patterns like:
        - [Title](URL)
        - Source: Title (URL)
        - https://domain.com/path
        """
        sources = []

        # Pattern 1: Markdown links [Title](URL)
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        for match in re.finditer(link_pattern, content):
            title = match.group(1)
            url = match.group(2)
            domain = self._extract_domain(url)
            sources.append(SourceReference(title=title, url=url, domain=domain))

        # Pattern 2: Bare URLs
        url_pattern = r"https?://[^\s\)>\]\"']+"
        for match in re.finditer(url_pattern, content):
            url = match.group(0)
            # Skip if already captured as markdown link
            if not any(s.url == url for s in sources):
                domain = self._extract_domain(url)
                sources.append(SourceReference(title=domain or url, url=url, domain=domain))

        return sources

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        match = re.search(r"https?://([^/]+)", url)
        return match.group(1) if match else None

    def _parse_table(self, content: str) -> list[dict[str, str]]:
        """Parse a markdown table into list of dicts.

        Args:
            content: Markdown content containing a table

        Returns:
            List of row dicts with column headers as keys
        """
        lines = content.strip().split("\n")
        rows = []

        # Find table start (header row with |)
        header_idx = None
        for i, line in enumerate(lines):
            if "|" in line and not line.strip().startswith("|-"):
                header_idx = i
                break

        if header_idx is None:
            return rows

        # Parse header
        header_line = lines[header_idx]
        headers = [h.strip() for h in header_line.split("|") if h.strip()]

        # Parse data rows (skip separator line)
        for line in lines[header_idx + 2:]:
            if "|" not in line:
                break
            values = [v.strip() for v in line.split("|") if v.strip()]
            if len(values) == len(headers):
                rows.append(dict(zip(headers, values)))

        return rows
