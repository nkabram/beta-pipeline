# Deep Research Pipeline - Just commands
# Run 'just' to see available commands

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Default recipe - show help
default:
    @just --list

# Check availability of all research apps
check:
    uv run python main.py check -v

# Run research for a single complaint
research complaint:
    uv run python main.py research "{{complaint}}"

# Run research for a trauma complaint
trauma complaint:
    uv run python main.py research "{{complaint}}" --type trauma

# Run research sequentially (not in parallel)
sequential complaint:
    uv run python main.py research "{{complaint}}" --sequential

# Run batch processing from a file
batch file:
    uv run python main.py batch "{{file}}"

# List complaints from open_deep_research
list:
    uv run python main.py list-complaints --app open_deep_research

# List complaints from openai_deep_research
list-openai:
    uv run python main.py list-complaints --app openai_deep_research

# Install dependencies
install:
    uv sync

# Run with debug logging
debug complaint:
    uv run python main.py research "{{complaint}}" --log-level DEBUG

# Quick test - check availability only
test:
    uv run python main.py check

# Run research with custom output directory
output complaint dir:
    uv run python main.py research "{{complaint}}" --output "{{dir}}"

# Show help
help:
    uv run python main.py --help

# Show research command help
help-research:
    uv run python main.py research --help
