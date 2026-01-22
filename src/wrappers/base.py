"""Base wrapper class for research application subprocess management."""

import asyncio
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

from ..models import (
    AppExecutionResult,
    ComplaintInput,
    PipelineConfig,
    ResearchApp,
    ResearchAppStatus,
)

logger = logging.getLogger(__name__)
console = Console()


class ToolWrapper(ABC):
    """Base class for wrapping research application CLIs."""

    def __init__(self, config: PipelineConfig):
        """Initialize the wrapper with pipeline configuration.

        Args:
            config: Pipeline configuration containing app paths and settings
        """
        self.config = config
        self._app_dir: Optional[Path] = None

    @property
    @abstractmethod
    def app(self) -> ResearchApp:
        """Return the ResearchApp enum for this wrapper."""
        ...

    @property
    @abstractmethod
    def app_dir(self) -> Path:
        """Return the application directory path."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Return human-readable name for logging."""
        ...

    @abstractmethod
    def build_command(self, complaint: ComplaintInput) -> list[str]:
        """Build the command to execute for the given complaint.

        Args:
            complaint: The complaint to research

        Returns:
            Command as list of strings (for subprocess)
        """
        ...

    @abstractmethod
    def find_output_directory(self, complaint: ComplaintInput) -> Optional[Path]:
        """Find the output directory for a completed research run.

        Args:
            complaint: The complaint that was researched

        Returns:
            Path to output directory, or None if not found
        """
        ...

    @abstractmethod
    def list_output_files(self, output_dir: Path) -> list[str]:
        """List the output files in the research output directory.

        Args:
            output_dir: Path to the output directory

        Returns:
            List of output filenames
        """
        ...

    def check_availability(self) -> tuple[bool, str]:
        """Check if the research app is available and properly configured.

        Returns:
            Tuple of (is_available, message)
        """
        if not self.app_dir.exists():
            return False, f"App directory not found: {self.app_dir}"

        # Check for justfile (common across all apps)
        justfile = self.app_dir / "justfile"
        if not justfile.exists():
            return False, f"justfile not found in {self.app_dir}"

        return True, f"{self.display_name} is available"

    async def execute(
        self,
        complaint: ComplaintInput,
        timeout: Optional[int] = None,
    ) -> AppExecutionResult:
        """Execute the research application for the given complaint.

        Args:
            complaint: The complaint to research
            timeout: Optional timeout in seconds (uses config default if not specified)

        Returns:
            AppExecutionResult with status and output information
        """
        timeout = timeout or self.config.timeout_seconds
        start_time = datetime.now()

        # Check availability first
        available, message = self.check_availability()
        if not available:
            return AppExecutionResult(
                app=self.app,
                status=ResearchAppStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                error_message=message,
            )

        # Build the command
        command = self.build_command(complaint)
        logger.info(f"[{self.display_name}] Executing: {' '.join(command)}")
        console.print(f"[cyan]{self.display_name}[/cyan] Starting research for: {complaint.complaint}")

        try:
            # Run the command
            result = await self._run_subprocess(command, timeout)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            if result.returncode == 0:
                # Find output directory
                output_dir = self.find_output_directory(complaint)
                output_files = self.list_output_files(output_dir) if output_dir else []

                console.print(
                    f"[green]{self.display_name}[/green] Completed in {duration:.1f}s "
                    f"({len(output_files)} files)"
                )

                return AppExecutionResult(
                    app=self.app,
                    status=ResearchAppStatus.COMPLETED,
                    output_dir=output_dir,
                    output_files=output_files,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                    exit_code=result.returncode,
                )
            else:
                error_msg = result.stderr or f"Process exited with code {result.returncode}"
                console.print(f"[red]{self.display_name}[/red] Failed: {error_msg[:100]}")

                return AppExecutionResult(
                    app=self.app,
                    status=ResearchAppStatus.FAILED,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                    error_message=error_msg,
                    exit_code=result.returncode,
                )

        except asyncio.TimeoutError:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            error_msg = f"Execution timed out after {timeout} seconds"
            console.print(f"[red]{self.display_name}[/red] {error_msg}")

            return AppExecutionResult(
                app=self.app,
                status=ResearchAppStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error_message=error_msg,
            )

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(f"[{self.display_name}] {error_msg}")
            console.print(f"[red]{self.display_name}[/red] {error_msg}")

            return AppExecutionResult(
                app=self.app,
                status=ResearchAppStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error_message=error_msg,
            )

    async def _run_subprocess(
        self,
        command: list[str],
        timeout: int,
    ) -> subprocess.CompletedProcess:
        """Run a subprocess with timeout.

        Args:
            command: Command to execute
            timeout: Timeout in seconds

        Returns:
            CompletedProcess result
        """
        # Prepare environment with the app directory
        env = os.environ.copy()

        # Create the subprocess
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.app_dir,
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            return subprocess.CompletedProcess(
                args=command,
                returncode=process.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
                stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
            )

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise

    def _find_latest_output_dir(
        self,
        base_dir: Path,
        prefix: str,
    ) -> Optional[Path]:
        """Find the most recent output directory with the given prefix.

        Args:
            base_dir: Directory to search in
            prefix: Prefix for directory names (complaint name)

        Returns:
            Path to most recent directory, or None if not found
        """
        if not base_dir.exists():
            return None

        matching_dirs = [
            d for d in base_dir.iterdir()
            if d.is_dir() and d.name.startswith(prefix)
        ]

        if not matching_dirs:
            return None

        # Sort by modification time (most recent first)
        matching_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        return matching_dirs[0]
