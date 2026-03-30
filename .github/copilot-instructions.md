# Project Guidelines

## Code Style
- Use Python 3.10+ and follow existing style in this repo: simple classes, type hints for public methods, and concise docstrings.
- Keep agent interfaces stable: each agent class should expose `execute(...)` and return `None` on recoverable failure instead of throwing where current code expects graceful handling.
- Prefer small, focused changes that preserve current console logging patterns (`self.log(...)`).

## Architecture
- Entry point: `process_transcript.py` orchestrates single-file and folder processing.
- Core coordination: `CoordinatorAgent` in `agents/coordinator_agent.py` controls the pipeline and parallel execution.
- Pipeline stages:
  - `DocumentReaderAgent`: reads `.docx` transcript content.
  - `SecretaryAgent`: sends prompts to Bedrock Claude and returns summary text.
  - `QualityEvaluator`: computes keyword and optional Claude-based quality metrics.
  - `OutputWriterAgent`: writes meeting minutes to `.docx`.
- Shared configuration and prompts are loaded by `Configuration` and `PromptLibrary` in `config.py`.

## Build and Test
- Environment setup (macOS/Linux): `bash setup_venv.sh`
- Environment setup (Windows): `setup_venv.bat`
- Install dependencies: `pip install -r requirements.txt`
- Run processor (default `transcripts/`): `python process_transcript.py`
- Run on folder: `python process_transcript.py path/to/folder`
- Run on file: `python process_transcript.py path/to/file.docx`
- Quick syntax validation (no test suite present): `python -m compileall .`

## Conventions
- Credentials are environment-only: keep AWS keys in `.env`; do not move secrets into YAML files.
- Config precedence is intentional and should be preserved:
  1. Environment variables
  2. `config.yaml`
  3. In-code defaults in `Configuration._load_config_file`
- Prompt customization is data-driven via `prompts.yaml`; avoid hardcoding prompt text in agents.
- Input format is `.docx` only. Folder mode scans `*.docx` and skips other formats.
- Batch outputs rely on `{"file_name": ..., "summary": ...}` objects; maintain these keys for compatibility across coordinator/writer/metrics.
- Parallel behavior is controlled by `max_parallel_workers`; keep thread-safe printing when modifying batch flow.
