"""Orchestration graph for the deep research pipeline.

Executes research apps in parallel, parses outputs, aggregates context,
and optionally calls beta_research for template generation.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..models import (
    AggregatedResearchContext,
    AppExecutionResult,
    ComplaintInput,
    PipelineConfig,
    PipelinePhase,
    PipelineState,
    ResearchApp,
    ResearchAppStatus,
)
from ..utils.aggregator import ContextAggregator
from ..wrappers import (
    ClaudeDeepResearchWrapper,
    OpenDeepResearchWrapper,
    OpenAIDeepResearchWrapper,
    ToolWrapper,
)

logger = logging.getLogger(__name__)
console = Console()


class ResearchPipeline:
    """Orchestration pipeline for deep research across multiple apps."""

    def __init__(self, config: PipelineConfig):
        """Initialize the pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config
        self.aggregator = ContextAggregator(config)

        # Initialize wrappers
        self.wrappers: dict[ResearchApp, ToolWrapper] = {
            ResearchApp.OPEN_DEEP_RESEARCH: OpenDeepResearchWrapper(config),
            ResearchApp.OPENAI_DEEP_RESEARCH: OpenAIDeepResearchWrapper(config),
            ResearchApp.CLAUDE_DEEP_RESEARCH: ClaudeDeepResearchWrapper(config),
        }

    def check_availability(self) -> dict[ResearchApp, tuple[bool, str]]:
        """Check availability of all research apps.

        Returns:
            Dict mapping app to (is_available, message)
        """
        results = {}
        for app, wrapper in self.wrappers.items():
            results[app] = wrapper.check_availability()
        return results

    async def run(self, complaint: ComplaintInput) -> PipelineState:
        """Run the full research pipeline for a complaint.

        Args:
            complaint: The complaint to research

        Returns:
            PipelineState with results
        """
        # Initialize state
        state = PipelineState(complaint=complaint)
        state.mark_phase(PipelinePhase.INITIALIZATION)

        console.print(f"\n[bold cyan]Starting Research Pipeline[/bold cyan]")
        console.print(f"Complaint: [yellow]{complaint.complaint}[/yellow]")
        console.print(f"Type: {complaint.complaint_type.value}")

        # Check availability
        availability = self.check_availability()
        available_apps = [app for app, (avail, _) in availability.items() if avail]

        if not available_apps:
            state.add_error("No research apps available")
            state.mark_phase(PipelinePhase.FAILED)
            console.print("[red]No research apps available. Check app configurations.[/red]")
            return state

        console.print(f"Available apps: {', '.join(app.value for app in available_apps)}")

        # Phase 1: Execute research apps
        state.mark_phase(PipelinePhase.RESEARCH_EXECUTION)
        await self._execute_research_apps(state, available_apps)

        # Check if any succeeded
        if not state.successful_apps:
            state.add_error("All research apps failed")
            state.mark_phase(PipelinePhase.FAILED)
            console.print("[red]All research apps failed[/red]")
            return state

        # Phase 2: Parse outputs
        state.mark_phase(PipelinePhase.OUTPUT_PARSING)
        console.print("\n[cyan]Parsing research outputs...[/cyan]")

        # Phase 3: Aggregate context
        state.mark_phase(PipelinePhase.CONTEXT_AGGREGATION)
        console.print("[cyan]Aggregating context from all sources...[/cyan]")

        aggregated_context = self.aggregator.aggregate(state)
        state.aggregated_context = aggregated_context.model_dump()

        # Create output directory
        output_dir = self._create_output_directory(complaint)
        state.output_directory = output_dir

        # Write aggregated context
        resources_dir = self.aggregator.write_beta_research_context(
            aggregated_context, output_dir
        )

        # Copy individual app outputs to organized structure
        await self._organize_outputs(state, output_dir)

        # Phase 4: Template generation (optional)
        if self.config.run_beta_research:
            state.mark_phase(PipelinePhase.TEMPLATE_GENERATION)
            console.print("\n[cyan]Running beta_research for template generation...[/cyan]")
            # Note: beta_research integration would go here
            # For now, we just mark the context as ready for manual beta_research run
            console.print(
                f"[green]Context ready for beta_research at:[/green] {resources_dir}"
            )

        # Complete
        state.mark_phase(PipelinePhase.COMPLETED)

        # Print summary
        self._print_summary(state, aggregated_context)

        return state

    async def _execute_research_apps(
        self,
        state: PipelineState,
        available_apps: list[ResearchApp],
    ) -> None:
        """Execute research apps in parallel.

        Args:
            state: Pipeline state to update
            available_apps: List of available apps to run
        """
        console.print("\n[cyan]Executing research apps in parallel...[/cyan]")

        if self.config.parallel_execution:
            # Run apps in parallel
            tasks = []
            for app in available_apps:
                wrapper = self.wrappers[app]
                tasks.append(self._execute_single_app(wrapper, state.complaint, app))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for app, result in zip(available_apps, results):
                if isinstance(result, Exception):
                    state.app_results[app] = AppExecutionResult(
                        app=app,
                        status=ResearchAppStatus.FAILED,
                        error_message=str(result),
                    )
                    state.add_error(f"{app.value}: {result}")
                else:
                    state.app_results[app] = result
        else:
            # Run sequentially
            for app in available_apps:
                wrapper = self.wrappers[app]
                try:
                    result = await wrapper.execute(state.complaint)
                    state.app_results[app] = result
                except Exception as e:
                    state.app_results[app] = AppExecutionResult(
                        app=app,
                        status=ResearchAppStatus.FAILED,
                        error_message=str(e),
                    )
                    state.add_error(f"{app.value}: {e}")

    async def _execute_single_app(
        self,
        wrapper: ToolWrapper,
        complaint: ComplaintInput,
        app: ResearchApp,
    ) -> AppExecutionResult:
        """Execute a single research app.

        Args:
            wrapper: Tool wrapper for the app
            complaint: Complaint to research
            app: App identifier

        Returns:
            Execution result
        """
        return await wrapper.execute(complaint)

    def _create_output_directory(self, complaint: ComplaintInput) -> Path:
        """Create the output directory for this research run.

        Args:
            complaint: The complaint being researched

        Returns:
            Path to the output directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"{complaint.normalized_name}_{timestamp}"
        output_dir = self.config.base_output_dir / dir_name
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    async def _organize_outputs(
        self,
        state: PipelineState,
        output_dir: Path,
    ) -> None:
        """Organize outputs from individual apps into structured directories.

        Args:
            state: Pipeline state with app results
            output_dir: Base output directory
        """
        import shutil

        for app, result in state.app_results.items():
            if result.is_success and result.output_dir:
                # Create app-specific subdirectory
                app_subdir = output_dir / app.value
                app_subdir.mkdir(exist_ok=True)

                # Copy output files
                for filename in result.output_files:
                    src = result.output_dir / filename
                    if src.exists():
                        shutil.copy2(src, app_subdir / filename)

    def _print_summary(
        self,
        state: PipelineState,
        context: AggregatedResearchContext,
    ) -> None:
        """Print a summary of the pipeline execution.

        Args:
            state: Final pipeline state
            context: Aggregated research context
        """
        console.print("\n" + "=" * 60)
        console.print(f"[bold green]Pipeline Complete: {state.complaint.complaint}[/bold green]")
        console.print("=" * 60)

        # App results
        console.print("\n[bold]Research App Results:[/bold]")
        for app, result in state.app_results.items():
            status_color = "green" if result.is_success else "red"
            duration = f"{result.duration_seconds:.1f}s" if result.duration_seconds else "N/A"
            files = len(result.output_files) if result.output_files else 0
            console.print(
                f"  [{status_color}]{result.status.value:10}[/{status_color}] "
                f"{app.value:25} ({duration}, {files} files)"
            )

        # Context summary
        console.print("\n[bold]Aggregated Context:[/bold]")
        console.print(f"  Foundation: {context.foundation.source_app.value}")
        console.print(f"  Demographics: {context.demographics.source_app.value}")
        console.print(f"  Clinical Context: {context.clinical_context.source_app.value}")
        console.print(f"  Synonyms: {context.synonyms.source_app.value}")
        console.print(f"  Total Sources: {context.total_sources}")

        if context.demographics.created_modifiers:
            console.print(
                f"  Modifiers Created: {', '.join(context.demographics.created_modifiers)}"
            )

        # Output location
        console.print(f"\n[bold]Output Directory:[/bold] {state.output_directory}")

        # Duration
        if state.duration_seconds:
            console.print(f"[bold]Total Duration:[/bold] {state.duration_seconds:.1f} seconds")

        console.print("=" * 60 + "\n")


async def run_pipeline(
    complaint: ComplaintInput,
    config: Optional[PipelineConfig] = None,
) -> PipelineState:
    """Convenience function to run the pipeline.

    Args:
        complaint: Complaint to research
        config: Optional pipeline configuration

    Returns:
        Pipeline state with results
    """
    config = config or PipelineConfig()
    pipeline = ResearchPipeline(config)
    return await pipeline.run(complaint)
