# Deep Research Pipeline: Implementation Guide

This document provides detailed technical guidance for completing and extending the deep research pipeline.

---

## Table of Contents

1. [Current Implementation Status](#current-implementation-status)
2. [Architecture Deep Dive](#architecture-deep-dive)
3. [Milestone 2: Output Parsing Refinement](#milestone-2-output-parsing-refinement)
4. [Milestone 3: Smart Orchestration](#milestone-3-smart-orchestration)
5. [Milestone 4: Beta Research Integration](#milestone-4-beta-research-integration)
6. [Milestone 5: Verification & Testing](#milestone-5-verification--testing)
7. [Future Enhancements](#future-enhancements)
8. [Troubleshooting Guide](#troubleshooting-guide)

---

## Current Implementation Status

### Completed Components

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| Complaint Models | `src/models/complaint.py` | ✅ Complete | 9 age bands, 4 trauma groups, 8 special populations |
| State Models | `src/models/state.py` | ✅ Complete | PipelineState, PipelineConfig, AppExecutionResult |
| Output Models | `src/models/outputs.py` | ✅ Complete | Normalized findings for all categories |
| Base Wrapper | `src/wrappers/base.py` | ✅ Complete | Async subprocess with timeout |
| Open Deep Wrapper | `src/wrappers/open_deep.py` | ✅ Complete | `just go` command |
| OpenAI Wrapper | `src/wrappers/openai_deep.py` | ✅ Complete | `just research` command |
| Claude Wrapper | `src/wrappers/claude_deep.py` | ✅ Complete | `just medical` command |
| Base Parser | `src/parsers/base.py` | ✅ Complete | Markdown/JSON utilities |
| Open Deep Parser | `src/parsers/open_deep_parser.py` | 🔄 Needs Testing | Pattern matching for Phase A/B/C |
| OpenAI Parser | `src/parsers/openai_parser.py` | 🔄 Needs Testing | Pattern matching for Phase 1/2/3 |
| Claude Parser | `src/parsers/claude_parser.py` | 🔄 Needs Testing | Synthesized report parsing |
| Pipeline Graph | `src/graph/pipeline_graph.py` | ✅ Complete | Parallel execution, error handling |
| Context Aggregator | `src/utils/aggregator.py` | ✅ Complete | Smart source selection |
| CLI | `main.py` | ✅ Complete | check, research, batch commands |

### Test Status

```bash
# Run this to verify current state
just check  # Should show all 3 apps available

# Syntax verification
uv run python -c "from src.models import *; from src.wrappers import *; print('OK')"
```

---

## Architecture Deep Dive

### Data Flow

```
ComplaintInput
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ PipelineState (initialized)                                     │
│   complaint: ComplaintInput                                     │
│   current_phase: INITIALIZATION                                 │
│   app_results: {}                                               │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼ [RESEARCH_EXECUTION phase]
┌─────────────────────────────────────────────────────────────────┐
│ Parallel App Execution (asyncio.gather)                         │
│                                                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │ OpenDeep    │  │ OpenAI      │  │ Claude      │            │
│   │ Wrapper     │  │ Wrapper     │  │ Wrapper     │            │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│          │                │                │                    │
│          ▼                ▼                ▼                    │
│   AppExecutionResult AppExecutionResult AppExecutionResult      │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼ [OUTPUT_PARSING phase]
┌─────────────────────────────────────────────────────────────────┐
│ Output Parsing                                                  │
│                                                                 │
│   OpenDeepParser.parse_* → FoundationFindings, Demographics...  │
│   OpenAIParser.parse_*   → FoundationFindings, Demographics...  │
│   ClaudeParser.parse_*   → FoundationFindings, synthesis...     │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼ [CONTEXT_AGGREGATION phase]
┌─────────────────────────────────────────────────────────────────┐
│ ContextAggregator.aggregate()                                   │
│                                                                 │
│   Foundation     ← prefer open_deep_research                    │
│   Demographics   ← prefer openai_deep_research (PRIMARY)        │
│   Clinical       ← prefer open_deep_research                    │
│   Synonyms       ← prefer open_deep_research                    │
│   Synthesis      ← claude-deep-research only                    │
│                                                                 │
│   → AggregatedResearchContext                                   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼ [TEMPLATE_GENERATION phase]
┌─────────────────────────────────────────────────────────────────┐
│ Beta Research Integration (TODO)                                │
│                                                                 │
│   Write context to: {complaint}_resources/aggregated_context.json│
│   Call: beta_research research {complaint} --include-local      │
│   Output: 18 demographic templates                              │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
PipelineState (completed)
    output_directory: Path
    generated_templates: list[str]
```

### Key Classes

#### `ToolWrapper` (base.py)

Abstract base class for subprocess management:

```python
class ToolWrapper(ABC):
    @abstractmethod
    def build_command(self, complaint: ComplaintInput) -> list[str]:
        """Build shell command for the research app."""
        ...

    async def execute(self, complaint: ComplaintInput) -> AppExecutionResult:
        """Execute with timeout and error handling."""
        ...

    def find_output_directory(self, complaint: ComplaintInput) -> Optional[Path]:
        """Locate the output directory after execution."""
        ...
```

#### `BaseParser` (base.py)

Abstract base class for output parsing:

```python
class BaseParser(ABC):
    def parse_foundation(self, output_dir, complaint) -> Optional[FoundationFindings]:
        ...
    def parse_demographics(self, output_dir, complaint) -> Optional[DemographicsFindings]:
        ...
    def parse_clinical_context(self, output_dir, complaint) -> Optional[ClinicalContextFindings]:
        ...
    def parse_synonyms(self, output_dir, complaint) -> Optional[SynonymFindings]:
        ...

    # Utility methods
    def _extract_section(self, content, section_header) -> Optional[str]:
        """Extract markdown section by header."""
    def _extract_list_items(self, content) -> list[str]:
        """Extract bullet points from markdown."""
    def _extract_sources(self, content) -> list[SourceReference]:
        """Extract URLs and citations."""
```

#### `ContextAggregator` (aggregator.py)

Combines outputs with smart source selection:

```python
class ContextAggregator:
    def aggregate(self, state: PipelineState) -> AggregatedResearchContext:
        """Aggregate from all successful apps."""
        ...

    def _get_best_foundation(self, complaint, output_dirs) -> FoundationFindings:
        """Priority: open_deep → openai → claude"""
        ...

    def _get_best_demographics(self, complaint, output_dirs) -> DemographicsFindings:
        """Priority: openai (PRIMARY) → open_deep → claude"""
        ...

    def write_beta_research_context(self, context, output_dir) -> Path:
        """Write JSON for beta_research consumption."""
        ...
```

---

## Milestone 2: Output Parsing Refinement

### Goal
Refine parsers based on actual output from each research app.

### Step 2.1: Collect Sample Outputs

Run each app manually and save outputs for parser development:

```bash
# Open Deep Research
cd D:/research/open_deep_research
just go "chest pain"
# Save: outputs/chest_pain_*/

# OpenAI Deep Research
cd D:/research/openai_deep_research
just research "chest pain"
# Save: output/chest_pain_*/

# Claude Deep Research
cd D:/research/claude-deep-research
just medical "chest pain"
# Save: output/chest_pain_*/
```

### Step 2.2: Analyze Output Formats

For each app, document:

1. **File naming conventions**
   - Exact filename patterns
   - Timestamp formats
   - Directory structure

2. **Markdown structure**
   - Section headers (exact text)
   - Subsection hierarchy
   - List formats (bullets, numbered)
   - Table formats

3. **Demographics section patterns**
   - How age groups are labeled
   - Where modifiers are indicated
   - Priority score formats

### Step 2.3: Update Parser Regex Patterns

Example refinement for `open_deep_parser.py`:

```python
# Current (generic)
age_group_mapping = {
    "neonatal": AgeGroup.NEONATAL,
    "infant": AgeGroup.INFANT,
    ...
}

# Refined (based on actual output)
AGE_SECTION_PATTERNS = {
    # Actual headers from open_deep_research Phase B
    r"#{2,3}\s+Neonatal\s*\(0-28\s*days?\)": AgeGroup.NEONATAL,
    r"#{2,3}\s+Infant\s*\(1-12\s*months?\)": AgeGroup.INFANT,
    r"#{2,3}\s+Toddler/Preschool\s*\(1-5\s*years?\)": AgeGroup.TODDLER_PRESCHOOL,
    ...
}
```

### Step 2.4: Add Unit Tests

Create `tests/test_parsers.py`:

```python
import pytest
from pathlib import Path
from src.parsers import OpenDeepResearchParser
from src.models import ComplaintInput

# Use saved sample outputs
SAMPLE_OUTPUT_DIR = Path("tests/fixtures/open_deep_research/chest_pain_20260120_120000")

def test_parse_foundation():
    parser = OpenDeepResearchParser()
    complaint = ComplaintInput(complaint="chest pain")

    findings = parser.parse_foundation(SAMPLE_OUTPUT_DIR, complaint)

    assert findings is not None
    assert findings.complaint_name == "chest pain"
    assert len(findings.differential_diagnoses) > 0
    assert len(findings.red_flags) > 0

def test_parse_demographics():
    parser = OpenDeepResearchParser()
    complaint = ComplaintInput(complaint="chest pain")

    findings = parser.parse_demographics(SAMPLE_OUTPUT_DIR, complaint)

    assert findings is not None
    assert len(findings.age_findings) >= 5  # At least 5 age groups
    assert "geriatric" in findings.age_findings
```

---

## Milestone 3: Smart Orchestration

### Goal
Implement app specialization to avoid redundant research.

### Option A: Post-hoc Selection (Current Implementation)

Currently, all apps run in parallel and the aggregator selects the best output per category. This works but wastes API calls on redundant research.

### Option B: Prompt Modification (Recommended)

Modify the prompts/protocols sent to each app to focus on their specialty.

#### Step 3.1: Create Focused Protocols

Create modified protocol files in `config/protocols/`:

```
config/protocols/
├── open_deep_foundation_only.md    # Skip Phase B (demographics)
├── openai_demographics_focus.md    # Prioritize Phase 2
└── claude_synthesis_mode.md        # Gap analysis focus
```

#### Step 3.2: Update Wrappers to Use Custom Protocols

```python
# src/wrappers/open_deep.py

def build_command(self, complaint: ComplaintInput, focus: str = "full") -> list[str]:
    if focus == "foundation":
        # Use modified protocol that skips demographics
        return ["just", "go-foundation", complaint.complaint]
    return ["just", "go", complaint.complaint]
```

#### Step 3.3: Add Just Commands to Each App

In `open_deep_research/justfile`:

```just
# Foundation-only mode (skip Phase B)
go-foundation complaint:
    uv run python cli_research.py --complaint "{{complaint}}" --skip-demographics
```

### Option C: Parallel with Deduplication

Keep current parallel execution but have the aggregator detect and merge duplicate findings.

---

## Milestone 4: Beta Research Integration

### Goal
Automatically call beta_research with aggregated context for template generation.

### Step 4.1: Create Beta Research Wrapper

```python
# src/wrappers/beta_research.py

class BetaResearchWrapper(ToolWrapper):
    @property
    def app(self) -> ResearchApp:
        return ResearchApp.BETA_RESEARCH  # Add to enum

    def build_command(self, complaint: ComplaintInput) -> list[str]:
        return [
            "uv", "run", "python", "cli.py", "research",
            complaint.complaint,
            "--include-local",
            "--output-dir", str(self.output_dir),
        ]

    def build_command_with_context(
        self,
        complaint: ComplaintInput,
        context_dir: Path,
    ) -> list[str]:
        """Build command with pre-aggregated context."""
        return [
            "uv", "run", "python", "cli.py", "research",
            complaint.complaint,
            "--include-local",
            "--local-resources", str(context_dir),
            "--output-dir", str(self.output_dir),
        ]
```

### Step 4.2: Update Pipeline Graph

```python
# src/graph/pipeline_graph.py

async def run(self, complaint: ComplaintInput) -> PipelineState:
    ...

    # After context aggregation
    if self.config.run_beta_research:
        state.mark_phase(PipelinePhase.TEMPLATE_GENERATION)

        # Write context for beta_research
        resources_dir = self.aggregator.write_beta_research_context(
            aggregated_context, output_dir
        )

        # Execute beta_research
        beta_wrapper = BetaResearchWrapper(self.config)
        beta_result = await beta_wrapper.execute_with_context(
            complaint, resources_dir
        )

        if beta_result.is_success:
            state.generated_templates = beta_result.output_files
        else:
            state.add_error(f"beta_research failed: {beta_result.error_message}")

    state.mark_phase(PipelinePhase.COMPLETED)
    return state
```

### Step 4.3: Handle Template Output

Parse beta_research output to track generated templates:

```python
def list_generated_templates(self, output_dir: Path) -> list[str]:
    """List generated template files from beta_research."""
    templates_dir = output_dir / "templates"
    if not templates_dir.exists():
        return []

    templates = []

    # Age/sex templates
    age_sex_dir = templates_dir / "age_sex"
    if age_sex_dir.exists():
        for d in age_sex_dir.iterdir():
            if d.is_dir() and (d / "template.json").exists():
                templates.append(f"age_sex/{d.name}")

    # Special population templates
    special_dir = templates_dir / "special_populations"
    if special_dir.exists():
        for d in special_dir.iterdir():
            if d.is_dir() and (d / "template.json").exists():
                templates.append(f"special_populations/{d.name}")

    return templates
```

---

## Milestone 5: Verification & Testing

### Goal
Validate end-to-end pipeline with real complaints and verify output quality.

### Step 5.1: Smoke Tests

Create `tests/test_e2e.py`:

```python
import pytest
import asyncio
from src.models import ComplaintInput, ComplaintType, PipelineConfig
from src.graph import run_pipeline

@pytest.mark.asyncio
async def test_medical_complaint_e2e():
    """End-to-end test with a medical complaint."""
    complaint = ComplaintInput(
        complaint="chest pain",
        complaint_type=ComplaintType.MEDICAL,
    )
    config = PipelineConfig(
        timeout_seconds=1800,  # 30 min for test
    )

    state = await run_pipeline(complaint, config)

    assert state.current_phase.value == "completed"
    assert len(state.successful_apps) >= 2  # At least 2 apps succeeded
    assert state.output_directory.exists()

@pytest.mark.asyncio
async def test_trauma_complaint_e2e():
    """End-to-end test with a trauma complaint."""
    complaint = ComplaintInput(
        complaint="fall",
        complaint_type=ComplaintType.TRAUMA,
    )

    state = await run_pipeline(complaint)

    assert state.current_phase.value == "completed"
```

### Step 5.2: Output Validation

Create `src/utils/validator.py`:

```python
class OutputValidator:
    """Validates pipeline output quality using LLM."""

    async def validate_aggregated_context(
        self,
        context: AggregatedResearchContext,
    ) -> ValidationResult:
        """Check that aggregated context is complete and consistent."""
        issues = []

        # Check foundation completeness
        if not context.foundation.differential_diagnoses:
            issues.append("Missing differential diagnoses")
        if not context.foundation.red_flags:
            issues.append("Missing red flags")

        # Check demographics completeness
        if len(context.demographics.age_findings) < 5:
            issues.append(f"Only {len(context.demographics.age_findings)} age groups (expected 9)")

        # Check for content consistency
        # ... LLM-based validation ...

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
        )
```

### Step 5.3: Performance Benchmarking

Track execution metrics:

```python
# Add to PipelineState
class PipelineMetrics(BaseModel):
    total_duration_seconds: float
    app_durations: dict[str, float]
    total_api_calls: int
    estimated_cost_usd: float

    # Per-phase timing
    research_phase_seconds: float
    parsing_phase_seconds: float
    aggregation_phase_seconds: float
    template_phase_seconds: Optional[float]
```

---

## Future Enhancements

### Enhancement 1: Direct Demographic Input

Allow specifying a demographic combination to research specifically:

```bash
# Future CLI
just research "chest pain" --demographic geriatric_female
```

Implementation:

```python
# Add to ComplaintInput
class ComplaintInput(BaseModel):
    complaint: str
    demographic: Optional[DemographicCombination] = None

# Modify pipeline to skip full demographic research
if complaint.demographic:
    # Only research this specific demographic
    # Skip phases that research all demographics
    pass
```

### Enhancement 2: Incremental Updates

Support updating specific demographics without full re-run:

```bash
just update "chest pain" --demographic pregnancy
```

### Enhancement 3: Caching Layer

Cache research results to avoid re-running unchanged complaints:

```python
class ResearchCache:
    def get(self, complaint: str, app: ResearchApp) -> Optional[AppExecutionResult]:
        ...
    def set(self, complaint: str, app: ResearchApp, result: AppExecutionResult):
        ...
    def invalidate(self, complaint: str):
        ...
```

### Enhancement 4: Web Dashboard

Create a web interface for monitoring pipeline progress:

```
dashboard/
├── app.py           # FastAPI backend
├── templates/       # Jinja2 templates
└── static/          # CSS/JS
```

---

## Troubleshooting Guide

### Common Issues

#### "App directory not found"

```
Error: App directory not found: D:/research/open_deep_research
```

**Fix**: Update `config/pipeline_config.yaml` with correct paths.

#### "justfile not found"

```
Error: justfile not found in D:/research/open_deep_research
```

**Fix**: Ensure the research app has a justfile with expected commands.

#### "Execution timed out"

```
Error: Execution timed out after 3600 seconds
```

**Fix**:
1. Increase timeout: `--timeout 7200`
2. Check if app is stuck (view logs)
3. Run apps individually to identify slow one

#### "No research apps available"

```
All research apps are unavailable. Check configurations.
```

**Fix**:
1. Run `just check -v` to see which apps are missing
2. Verify each app directory exists
3. Check each app can run independently

#### Parser returns empty findings

```
Warning: No foundation findings from open_deep_research
```

**Fix**:
1. Check if output files exist in expected location
2. Verify file naming matches parser expectations
3. Run parser in debug mode to see what patterns fail

### Debug Mode

Enable verbose logging:

```bash
just debug "chest pain"
# Or
uv run python main.py research "chest pain" --log-level DEBUG
```

### Manual Testing

Test each component individually:

```bash
# Test wrapper
uv run python -c "
from src.wrappers import OpenDeepResearchWrapper
from src.models import PipelineConfig, ComplaintInput

wrapper = OpenDeepResearchWrapper(PipelineConfig())
print(wrapper.check_availability())
print(wrapper.build_command(ComplaintInput(complaint='test')))
"

# Test parser
uv run python -c "
from pathlib import Path
from src.parsers import OpenDeepResearchParser
from src.models import ComplaintInput

parser = OpenDeepResearchParser()
complaint = ComplaintInput(complaint='chest_pain')
output_dir = Path('D:/research/open_deep_research/outputs/chest_pain_20260120_120000')
findings = parser.parse_foundation(output_dir, complaint)
print(findings)
"
```

---

## Appendix: File Reference

### Models

| File | Classes | Purpose |
|------|---------|---------|
| `complaint.py` | `AgeGroup`, `Sex`, `SpecialPopulation`, `ComplaintInput`, `DemographicCombination` | Input data models |
| `state.py` | `PipelineState`, `PipelineConfig`, `AppExecutionResult`, `ResearchAppStatus` | Pipeline state tracking |
| `outputs.py` | `FoundationFindings`, `DemographicsFindings`, `ClinicalContextFindings`, `SynonymFindings`, `AggregatedResearchContext` | Normalized output models |

### Wrappers

| File | Class | App | Command |
|------|-------|-----|---------|
| `open_deep.py` | `OpenDeepResearchWrapper` | open_deep_research | `just go` |
| `openai_deep.py` | `OpenAIDeepResearchWrapper` | openai_deep_research | `just research` |
| `claude_deep.py` | `ClaudeDeepResearchWrapper` | claude-deep-research | `just medical` |

### Parsers

| File | Class | Input Files |
|------|-------|-------------|
| `open_deep_parser.py` | `OpenDeepResearchParser` | `*_foundation_clinical_context.md`, `*_demographics_analysis.md`, `*_synonym_terminology.md` |
| `openai_parser.py` | `OpenAIDeepResearchParser` | `*_phase1_foundation_clinical.md`, `*_phase2_demographics.md`, `*_phase3_synonyms.md` |
| `claude_parser.py` | `ClaudeDeepResearchParser` | `*_research_report.md` |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-01-20 | Initial implementation - Milestone 1 complete |
