---
description: "Use when creating or editing Python files in this repository, especially transcript pipeline agents, orchestration flow, config loading, and quality evaluation logic. Enforces agent interface stability, config precedence, and output compatibility."
name: "Python File Scope"
applyTo: "**/*.py"
---
# Python File Scope Guidelines

- Keep agent interfaces stable:
  - Agent classes should expose `execute(...)`.
  - On recoverable errors, return `None` where existing flow expects graceful failure handling.
  - Preserve existing `self.log(...)` logging style and error-level patterns.

- Preserve pipeline compatibility:
  - Do not change the cross-stage result object shape used in batch/single-file flow.
  - Keep output payload keys compatible with coordinator and writer (`{"file_name": ..., "summary": ...}`).
  - Maintain `.docx` input assumptions unless a task explicitly broadens supported formats.

- Keep configuration behavior intact:
  - Preserve precedence: environment variables > `config.yaml` > in-code defaults.
  - Keep AWS credentials environment-only (`.env`), not in YAML config.
  - Keep prompt text data-driven via `prompts.yaml`/`PromptLibrary`; avoid hardcoding prompts in agents.

- Be careful in parallel processing paths:
  - Keep thread-safe console output in parallel sections (`print_lock` usage).
  - Avoid introducing shared mutable state across workers without synchronization.

- Prefer focused, minimal diffs:
  - Keep public behavior and CLI usage in `super_secretary.py` stable unless change is explicitly requested.
  - Add brief type hints and concise docstrings for new public methods.
