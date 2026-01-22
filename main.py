"""CLI entry point for the Deep Research Pipeline."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.models import ComplaintInput, ComplaintType, PipelineConfig
from src.graph import ResearchPipeline, run_pipeline

app = typer.Typer(
    name="pipeline",
    help="Deep Research Pipeline - Orchestrate medical research across multiple AI tools",
    add_completion=False,
)
console = Console()


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging with rich output."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )


@app.command()
def check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed status"),
) -> None:
    """Check availability of all research applications."""
    setup_logging("INFO" if verbose else "WARNING")

    config = PipelineConfig()
    pipeline = ResearchPipeline(config)
    results = pipeline.check_availability()

    table = Table(title="Research App Availability")
    table.add_column("Application", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Message")

    all_available = True
    for app, (available, message) in results.items():
        status = "[green]Available[/green]" if available else "[red]Unavailable[/red]"
        if not available:
            all_available = False
        table.add_row(app.value, status, message)

    console.print(table)

    if all_available:
        console.print("\n[green]All research apps are available![/green]")
        raise typer.Exit(0)
    else:
        console.print("\n[yellow]Some apps are unavailable. Check configurations.[/yellow]")
        raise typer.Exit(1)


@app.command()
def research(
    complaint: str = typer.Argument(..., help="Medical complaint to research (e.g., 'chest pain')"),
    complaint_type: str = typer.Option(
        "medical",
        "--type", "-t",
        help="Complaint type: 'medical' or 'trauma'"
    ),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Clinical category"),
    output_dir: Path = typer.Option(
        Path("reports"),
        "--output", "-o",
        help="Output directory for results"
    ),
    parallel: bool = typer.Option(True, "--parallel/--sequential", help="Run apps in parallel"),
    timeout: int = typer.Option(3600, "--timeout", help="Timeout per app in seconds"),
    skip_beta: bool = typer.Option(False, "--skip-beta", help="Skip beta_research template generation"),
    log_level: str = typer.Option("INFO", "--log-level", "-l", help="Logging level"),
) -> None:
    """Run the deep research pipeline for a medical complaint.

    Executes research across multiple AI tools in parallel:
    - open_deep_research (LangChain): Foundation + Clinical Context
    - openai_deep_research (OpenAI): Demographics Analysis (PRIMARY)
    - claude-deep-research (Anthropic): Synthesis & Gap Analysis

    Results are aggregated and prepared for beta_research template generation.
    """
    setup_logging(log_level)

    # Parse complaint type
    try:
        ctype = ComplaintType(complaint_type.lower())
    except ValueError:
        console.print(f"[red]Invalid complaint type: {complaint_type}[/red]")
        console.print("Valid types: medical, trauma")
        raise typer.Exit(1)

    # Create complaint input
    complaint_input = ComplaintInput(
        complaint=complaint,
        category=category,
        complaint_type=ctype,
    )

    # Create config
    config = PipelineConfig(
        base_output_dir=output_dir,
        parallel_execution=parallel,
        timeout_seconds=timeout,
        run_beta_research=not skip_beta,
    )

    # Run pipeline
    console.print(f"\n[bold]Deep Research Pipeline[/bold]")
    console.print(f"Complaint: {complaint}")
    console.print(f"Type: {ctype.value}")
    console.print(f"Output: {output_dir}")
    console.print(f"Mode: {'Parallel' if parallel else 'Sequential'}")

    try:
        state = asyncio.run(run_pipeline(complaint_input, config))

        if state.current_phase.value == "completed":
            console.print("\n[green]Pipeline completed successfully![/green]")
            raise typer.Exit(0)
        else:
            console.print(f"\n[red]Pipeline failed in phase: {state.current_phase.value}[/red]")
            if state.errors:
                console.print("Errors:")
                for error in state.errors:
                    console.print(f"  - {error}")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[red]Pipeline error: {e}[/red]")
        logging.exception("Pipeline error")
        raise typer.Exit(1)


@app.command()
def batch(
    complaints_file: Path = typer.Argument(
        ...,
        help="File with complaints (one per line, or JSON array)",
        exists=True,
    ),
    output_dir: Path = typer.Option(
        Path("reports"),
        "--output", "-o",
        help="Output directory for results"
    ),
    parallel_apps: bool = typer.Option(True, "--parallel-apps/--sequential-apps"),
    max_concurrent: int = typer.Option(1, "--max-concurrent", "-n", help="Max concurrent complaints"),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
) -> None:
    """Run the pipeline for multiple complaints from a file.

    The file can contain:
    - One complaint per line (plain text)
    - JSON array of complaint strings
    - JSON array of objects with 'complaint', 'category', 'type' fields
    """
    import json

    setup_logging(log_level)

    # Parse complaints file
    content = complaints_file.read_text()
    complaints: list[ComplaintInput] = []

    try:
        # Try JSON first
        data = json.loads(content)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    complaints.append(ComplaintInput(complaint=item))
                elif isinstance(item, dict):
                    ctype = ComplaintType(item.get("type", "medical").lower())
                    complaints.append(
                        ComplaintInput(
                            complaint=item["complaint"],
                            category=item.get("category"),
                            complaint_type=ctype,
                        )
                    )
    except json.JSONDecodeError:
        # Plain text, one per line
        for line in content.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                complaints.append(ComplaintInput(complaint=line))

    if not complaints:
        console.print("[red]No complaints found in file[/red]")
        raise typer.Exit(1)

    console.print(f"Found {len(complaints)} complaints to process")

    # Process complaints
    config = PipelineConfig(
        base_output_dir=output_dir,
        parallel_execution=parallel_apps,
    )

    results = []
    for i, complaint in enumerate(complaints, 1):
        console.print(f"\n[bold]Processing {i}/{len(complaints)}: {complaint.complaint}[/bold]")
        try:
            state = asyncio.run(run_pipeline(complaint, config))
            results.append((complaint.complaint, state.current_phase.value))
        except Exception as e:
            results.append((complaint.complaint, f"error: {e}"))

    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold]Batch Processing Complete[/bold]")
    console.print("=" * 60)

    success_count = sum(1 for _, status in results if status == "completed")
    console.print(f"Successful: {success_count}/{len(results)}")

    for complaint, status in results:
        color = "green" if status == "completed" else "red"
        console.print(f"  [{color}]{status:15}[/{color}] {complaint}")


@app.command()
def list_complaints(
    app_name: str = typer.Option(
        "open_deep_research",
        "--app", "-a",
        help="App to list complaints from"
    ),
) -> None:
    """List available complaint JSON files from a research app."""
    config = PipelineConfig()

    app_dirs = {
        "open_deep_research": config.open_deep_research_dir,
        "openai_deep_research": config.openai_deep_research_dir,
    }

    if app_name not in app_dirs:
        console.print(f"[red]Unknown app: {app_name}[/red]")
        raise typer.Exit(1)

    complaints_dir = app_dirs[app_name] / "complaints"

    if not complaints_dir.exists():
        console.print(f"[red]Complaints directory not found: {complaints_dir}[/red]")
        raise typer.Exit(1)

    json_files = list(complaints_dir.glob("*.json"))
    console.print(f"Found {len(json_files)} complaints in {app_name}:\n")

    for f in sorted(json_files):
        console.print(f"  {f.stem}")


if __name__ == "__main__":
    app()
