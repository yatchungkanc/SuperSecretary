# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Environment setup (macOS/Linux)
bash setup_venv.sh && source venv/bin/activate

# Environment setup (Windows)
setup_venv.bat

# Install dependencies
pip install -r requirements.txt

# Run on default transcripts/ folder
python super_secretary.py

# Run on a specific folder or single .docx file
python super_secretary.py path/to/folder
python super_secretary.py path/to/file.docx

# Syntax validation (no test suite)
python -m compileall .
```

Outputs land in `output/` with a date stamp: `Minutes_<name>_<YYYY-MM-DD>.docx` for single-file runs, `Meeting_Minutes_Summary_<YYYY-MM-DD>.docx` for batch.

### Environment variable overrides

| Var | Overrides |
| --- | --- |
| `AWS_REGION` / `AWS_PROFILE` | `aws.region` / `aws.profile` |
| `MAX_PARALLEL_WORKERS` | `parallel_processing.max_workers` |
| `MODEL_ID` / `TEMPERATURE` | `model.model_id` / `model.temperature` |

## Architecture

SuperSecretary converts meeting transcripts (`.docx`) into structured meeting minutes using AWS Bedrock Claude.

**Entry point:** `super_secretary.py` parses CLI args and delegates to `CoordinatorAgent`.

**Pipeline (in order):**
1. `DocumentReaderAgent` — reads `.docx` transcript content
2. `SecretaryAgent` — sends prompts to Bedrock Claude (`converse()` API) and returns summary text
3. `QualityEvaluator` — computes keyword coverage and/or Claude-based quality scores
4. `OutputWriterAgent` — writes meeting minutes to a `.docx` file

**Configuration:** `config.py` loads `Configuration` (from `config.yaml` + env vars) and `PromptLibrary` (from `prompts.yaml`). Precedence: env vars → `config.yaml` → in-code defaults.

**Batch processing:** `CoordinatorAgent` runs files in parallel via `ThreadPoolExecutor` (configurable with `max_parallel_workers`). Results use the shape `{"file_name": str, "summary": str}` — maintain these keys across all coordinator/writer/metrics code.

**Bedrock calls:** Always route through `self.config.converse_with_auto_refresh(self.client, ...)` rather than calling `client.converse(...)` directly. The wrapper returns `(response, client)` and may swap the client when SSO credentials renew mid-run — assign the returned client back to `self.client`.

**AWS credentials:** Loaded from `.env` or AWS profile. Supports SSO renewal via `sso_renew_command` in `config.yaml` (default: `go-aws-sso --persist`). Never put credentials in YAML files.

**Credential expiry handling:** `Configuration.verify_aws_credentials` probes both STS and Bedrock (`_probe_bedrock_access` via `list_foundation_models`) at startup, so a stale token surfaces before batch processing — not as a wall of per-file failures. Mid-run, `converse_with_auto_refresh` catches expired-token errors recognized by `is_expired_credentials_error` and runs the SSO renewal once under a process-wide lock. If the renewal subprocess itself fails (missing command, user cancelled the browser auth), it raises `CredentialRefreshError` and sets a sticky `_credential_refresh_failed` flag so parallel workers do not stampede a known-broken refresh. `CredentialRefreshError` and any expired-creds error must propagate through `SecretaryAgent` → `CoordinatorAgent` so the batch halts cleanly with one banner instead of N opaque per-file errors.

**Quality evaluation:** `quality_evaluation.claude.batch_mode` controls how often the Claude-based evaluator runs in batch:

- `all` — every file
- `sample` — random subset by `sample_rate`
- `first` — only the first `first_n` files

The decision lives in `CoordinatorAgent._should_evaluate_quality`.

## Conventions

- Each agent exposes a single `execute(...)` method and returns `None` on recoverable failure (no exceptions for expected error paths). **Exception:** auth failures (`CredentialRefreshError`, or errors matching `Configuration.is_expired_credentials_error`) must propagate so the coordinator can halt the batch — do not catch broadly and return `None` for those.
- Prompt text lives in `prompts.yaml` only — do not hardcode prompts inside agent classes.
- Input is `.docx` only; folder mode scans `*.docx` and silently skips other formats.
- Use `self.log(...)` for console output to maintain consistent logging patterns.
- Keep thread-safe printing when modifying any batch flow code.
- Python 3.10+, type hints on all public methods.

See [.github/instructions/python-file-scope.instructions.md](.github/instructions/python-file-scope.instructions.md) for the canonical statement of these contracts (agent interface, pipeline shape, config precedence, parallel safety) — keep both files in sync if you change either.
