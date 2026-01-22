# Deep Research Pipeline

An orchestration pipeline that coordinates multiple AI-powered deep research tools to generate comprehensive medical documentation. The pipeline runs research across three specialized engines in parallel, aggregates their findings, and prepares context for template generation.

## Overview

This pipeline addresses the challenge of combining research from multiple AI tools without redundant effort. Instead of having each tool research all aspects of a medical complaint, the pipeline **specializes each tool** for what it does best:

| Research App | Primary Role | Output |
|--------------|--------------|--------|
| **open_deep_research** (LangChain) | Foundation + Clinical Context + Synonyms | 3 markdown reports |
| **openai_deep_research** (OpenAI) | Demographics Analysis (PRIMARY) | 3 phase reports + JSON |
| **claude-deep-research** (Anthropic) | Synthesis & Gap Analysis | Synthesized report |

The aggregated context is then passed to **beta_research** for generating demographic-stratified templates (18 for medical, 8 for trauma).

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ PARALLEL RESEARCH EXECUTION                                     │
├─────────────────────────────────────────────────────────────────┤
│ open_deep_research    → Foundation + Clinical Context           │
│ openai_deep_research  → Demographics (9 ages × 2 sexes)         │
│ claude-deep-research  → Synthesis & Gap Detection               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ CONTEXT AGGREGATION                                             │
│ • Parse outputs from each app                                   │
│ • Select best source per category (Foundation, Demographics)    │
│ • Combine into unified context                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ TEMPLATE GENERATION (beta_research)                             │
│ • Medical: 18 templates (9 ages × 2 sexes)                      │
│ • Trauma: 8 templates (4 groups × 2 sexes)                      │
└─────────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Clone/navigate to the project
cd D:/research/deep-research-pipeline

# Install dependencies with uv
uv sync

# Verify all research apps are available
just check
```

## Quick Start

```bash
# Research a single medical complaint
just research "chest pain"

# Research a trauma complaint
just trauma "fall"

# Run in sequential mode (not parallel)
just sequential "headache"

# Batch process multiple complaints
just batch complaints.txt

# Show all available commands
just
```

## CLI Commands

### `check` - Verify App Availability

```bash
uv run python main.py check -v
```

Checks that all three research applications are properly configured and accessible.

### `research` - Run Pipeline for Single Complaint

```bash
uv run python main.py research "chest pain" [OPTIONS]

Options:
  --type, -t          Complaint type: 'medical' or 'trauma' (default: medical)
  --category, -c      Clinical category (optional)
  --output, -o        Output directory (default: reports)
  --parallel/--sequential  Run apps in parallel or sequentially
  --timeout           Timeout per app in seconds (default: 3600)
  --skip-beta         Skip beta_research template generation
  --log-level, -l     Logging level (default: INFO)
```

### `batch` - Process Multiple Complaints

```bash
uv run python main.py batch complaints.txt [OPTIONS]

Options:
  --output, -o        Output directory (default: reports)
  --parallel-apps     Run apps in parallel (default: true)
  --max-concurrent    Max concurrent complaints (default: 1)
  --log-level, -l     Logging level
```

The complaints file can be:
- Plain text (one complaint per line)
- JSON array of strings
- JSON array of objects with `complaint`, `category`, `type` fields

### `list-complaints` - Show Available Complaints

```bash
uv run python main.py list-complaints --app open_deep_research
```

## Output Structure

Each research run creates a timestamped directory:

```
reports/
└── chest_pain_20260120_143022/
    ├── open_deep_research/
    │   ├── chest_pain_foundation_clinical_context.md
    │   ├── chest_pain_demographics_analysis.md
    │   └── chest_pain_synonym_terminology.md
    ├── openai_deep_research/
    │   ├── chest_pain_phase1_foundation_clinical.md
    │   ├── chest_pain_phase2_demographics.md
    │   ├── chest_pain_phase3_synonyms.md
    │   └── chest_pain_metadata.json
    ├── claude_deep_research/
    │   ├── chest_pain_research_report.md
    │   └── chest_pain_metadata.json
    └── chest_pain_resources/
        ├── aggregated_context.json    # For beta_research
        └── research_summary.md        # Human-readable summary
```

## Configuration

Edit `config/pipeline_config.yaml` to customize:

```yaml
# App directories
app_directories:
  open_deep_research: "D:/research/open_deep_research"
  openai_deep_research: "D:/research/openai_deep_research"
  claude_deep_research: "D:/research/claude-deep-research"

# Execution settings
execution:
  timeout_seconds: 3600
  parallel_execution: true

# Specialization (which app handles what)
specialization:
  foundation_app: "open_deep_research"
  demographics_app: "openai_deep_research"
  synthesis_app: "claude_deep_research"
```

## Project Structure

```
deep-research-pipeline/
├── src/
│   ├── models/           # Pydantic data models
│   │   ├── complaint.py  # ComplaintInput, AgeGroup, Sex, etc.
│   │   ├── state.py      # PipelineState, PipelineConfig
│   │   └── outputs.py    # Normalized findings models
│   ├── wrappers/         # Subprocess wrappers for each app
│   │   ├── base.py       # ToolWrapper base class
│   │   ├── open_deep.py
│   │   ├── openai_deep.py
│   │   └── claude_deep.py
│   ├── parsers/          # Output parsing for each app
│   │   ├── base.py       # BaseParser with utilities
│   │   ├── open_deep_parser.py
│   │   ├── openai_parser.py
│   │   └── claude_parser.py
│   ├── graph/            # Orchestration logic
│   │   └── pipeline_graph.py
│   └── utils/
│       └── aggregator.py # Context aggregation
├── config/
│   └── pipeline_config.yaml
├── reports/              # Pipeline output (created at runtime)
├── main.py               # CLI entry point
├── justfile              # Just command shortcuts
├── pyproject.toml
├── README.md
└── IMPLEMENTATION.md     # Detailed implementation guide
```

## Demographic Coverage

### Medical Complaints (9 Age Bands × 2 Sexes = 18 Templates)

| Age Band | Range | Notes |
|----------|-------|-------|
| Neonatal | 0-28 days | High-risk, unique presentations |
| Infant | 1-12 months | Non-verbal, vital sign differences |
| Toddler/Preschool | 1-5 years | Limited history, developmental |
| School Age | 6-11 years | Can provide history |
| Adolescent | 12-17 years | Confidentiality, risk behaviors |
| Young Adult | 18-39 years | Baseline reference |
| Middle Age | 40-64 years | Chronic disease onset |
| Older Adult | 65-79 years | Polypharmacy, comorbidities |
| Geriatric | 80+ years | Atypical presentations, frailty |

### Trauma Complaints (4 Consolidated Groups × 2 Sexes = 8 Templates)

| Group | Constituent Ages | Key Considerations |
|-------|------------------|-------------------|
| Pre-Mobile Pediatric | Neonatal, Infant, Toddler <3y | NAT screening, falls |
| Active Pediatric | Toddler 3-5y, School Age, Adolescent | Sports, playground |
| Working Adult | Young Adult, Middle Age | MVC, occupational |
| Fragile Adult | Older Adult, Geriatric | Falls, anticoagulation |

## Development Status

### ✅ Completed (Milestone 1)
- Project structure and dependencies
- Pydantic models for complaints, demographics, state
- Tool wrappers for all three research apps
- Output parsers for each app's format
- Orchestration pipeline with parallel execution
- Context aggregator with smart source selection
- CLI with check, research, batch commands

### 🔄 In Progress (Milestone 2-3)
- Refine parsers based on actual output testing
- Beta research integration
- Error recovery and retry logic

### 📋 Planned (Milestone 4-5)
- LLM-based output validation
- Performance benchmarking
- Demographic input support (future enhancement)

## Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- [just](https://github.com/casey/just) command runner
- Access to research app directories:
  - `D:/research/open_deep_research`
  - `D:/research/openai_deep_research`
  - `D:/research/claude-deep-research`
  - `D:/research/beta_research`

## Related Projects

- **open_deep_research**: LangChain-based research with LangGraph server
- **openai_deep_research**: OpenAI deep research models (o4-mini-deep-research)
- **claude-deep-research**: Anthropic orchestrator-worker pattern
- **beta_research**: Template generation with Pydantic AI Graph

## License

Internal research project.
