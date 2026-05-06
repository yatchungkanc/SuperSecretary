# Meeting Super Secretary

An agent-based Python application that converts meeting transcripts (`.docx`) into structured meeting minutes using AWS Bedrock Claude. It supports single-file and batch folder processing, parallel execution, automatic AWS SSO credential renewal, and summary quality evaluation.

## Requirements

- Python 3.10+
- AWS account with Bedrock access and Claude enabled in your region

## Setup

### 1. Create a virtual environment

**macOS / Linux**
```bash
bash setup_venv.sh
```

**Windows**
```bat
setup_venv.bat
```

### 2. Install dependencies

```bash
source venv/bin/activate  # macOS/Linux, when using setup_venv.sh with venv
pip install -r requirements.txt
```

### 3. Configure AWS credentials

Recommended: use the automatic AWS SSO flow. You do not need to run `go-aws-sso` manually before launching the processor.

When you run `python super_secretary.py`, the app first validates the input path, then initializes configuration and verifies AWS credentials with STS. If credentials are missing or expired, it automatically runs the configured renewal command:

```bash
go-aws-sso --persist
```

By default, credentials are reloaded from the selected AWS profile in `~/.aws/credentials` after `go-aws-sso` completes. Set `aws.profile` in `config.yaml` or `AWS_PROFILE` if you need a non-default profile; the app appends that profile to the SSO command when the command does not already include `--profile` or `-p`.

Only create a `.env` file if you prefer to supply credentials directly. Do not copy `.env.example` unless you immediately replace the placeholder values; placeholder AWS keys will stop startup before the automatic SSO flow can run.

```bash
cp .env.example .env
```

```ini
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_access_key_here
AWS_SESSION_TOKEN=your_session_token_here   # Required for temporary credentials
AWS_REGION=us-east-1                        # Optional, defaults to us-east-1
```

> **Never commit `.env` to version control.**

### 4. Customize application settings

```bash
cp config.example.yaml config.yaml
```

`config.yaml` is included in this repository as a working local config. If you are setting up a fresh copy or resetting local values, copy from `config.example.yaml`.

### 5. Customize AI prompts and domain assignments

```bash
cp prompts.example.yaml prompts.yaml
```

`prompts.yaml` is also included as a working prompt file. Edit it to match your organization, domains, and meeting-minute style.

## Usage

```bash
# Process all .docx files in the default transcripts/ folder
python super_secretary.py

# Process all .docx files in a specific folder
python super_secretary.py path/to/folder

# Process a single file
python super_secretary.py path/to/transcript.docx
```

Outputs are written to the `output/` folder:

- Single-file output: `output/Minutes_<transcript-name>_<YYYY-MM-DD>.docx`
- Batch output: `output/Meeting_Minutes_Summary_<YYYY-MM-DD>.docx` by default

The batch base name and single-file prefix are configurable in `config.yaml`.

## Configuration

Settings are layered in this precedence order (highest to lowest):

| Layer | File | Notes |
|---|---|---|
| 1 | Environment variables | Useful for CI/CD overrides |
| 2 | `config.yaml` | Primary application settings |
| 3 | In-code defaults | Fallback when YAML is absent |

AWS credentials are loaded from environment variables first, then from the selected shared AWS credentials profile. The app never reads AWS secrets from `config.yaml`.

### `config.yaml` options

```yaml
aws:
  region: "us-east-1"
  profile:
  sso_renew_command: "go-aws-sso --persist"

model:
  model_id: "global.anthropic.claude-sonnet-4-6"
  temperature: 0.3          # 0.0 = deterministic, 1.0 = creative

parallel_processing:
  max_workers: 3            # Set to 1 for sequential; mind Bedrock rate limits

output:
  default_filename: "Meeting_Minutes_Summary.docx"
  file_prefix: "Minutes_"

quality_evaluation:
  enabled: true
  method: "both"          # "keyword", "claude", or "both"
  keyword:
    min_coverage: 50
    extract_method: "frequency"
    top_keywords: 30
  claude:
    enabled: true
    min_overall_score: 70
    min_completeness: 75
    min_accuracy: 80
    min_relevance: 75
    batch_mode: "all"    # "all", "sample", or "first"
    sample_rate: 0.2
    first_n: 3
```

`aws.profile` selects the shared AWS credentials profile. Leave it empty to use `default`. `aws.sso_renew_command` is the command run when AWS credentials are missing or expired. The default uses the interactive `go-aws-sso` flow so the browser authorization page can open. If a profile is set, the app appends it to the SSO command when the command does not already include `--profile` or `-p`.

Optional environment variable overrides (see `.env.example`):

| Variable | Overrides |
|---|---|
| `AWS_REGION` | `aws.region` |
| `AWS_PROFILE` | `aws.profile` |
| `MAX_PARALLEL_WORKERS` | `parallel_processing.max_workers` |
| `MODEL_ID` | `model.model_id` |
| `TEMPERATURE` | `model.temperature` |

### `prompts.yaml` options

| Key | Purpose |
|---|---|
| `secretary_role` | System prompt that defines the AI's persona |
| `domain_assignments` | Maps team member names to responsibility domains, injected into the summary prompt |
| `transcript_summary_prompt` | Main summarization template; use `{transcript}` and `{domain_list}` placeholders |
| `quality_evaluation_prompt` | Evaluation template; use `{transcript}` and `{summary}` placeholders |

When editing `quality_evaluation_prompt`, double literal JSON braces as `{{` and `}}` because the template is rendered with Python `str.format`.

## Architecture

```
super_secretary.py             ← Entry point and CLI handling
├── TranscriptProcessorOrchestrator
│   ├── CoordinatorAgent       ← Orchestrates pipeline, manages parallel execution
│   │   ├── DocumentReaderAgent   ← Reads .docx transcript content
│   │   ├── SecretaryAgent        ← Calls Bedrock Claude to generate meeting minutes
│   │   ├── QualityEvaluator      ← Scores output against source transcript
│   │   └── OutputWriterAgent     ← Writes final .docx output
│   └── MetricsCollector       ← Tracks per-file and batch processing metrics
config.py                      ← Configuration and PromptLibrary loaders
```

### Agent contract

Every agent exposes a single `execute(...)` method and returns `None` on recoverable failure. Callers check for `None` rather than catching exceptions.

### Batch result object

All pipeline stages share this dict shape:

```python
{"file_name": str, "summary": str}
```

## Quality Evaluation

Quality evaluation is configured in `config.yaml` under `quality_evaluation`:

| Method | Description |
|---|---|
| `keyword` | Fast, free — checks keyword coverage between transcript and summary |
| `claude` | AI-powered — scores completeness, accuracy, and relevance via a second Bedrock call |
| `both` | Runs both; composite score weights Claude at 70% and keyword at 30% |

Claude scores are weighted: `overall = (completeness × 0.4) + (accuracy × 0.4) + (relevance × 0.2)`.

For batch processing, `quality_evaluation.claude.batch_mode` controls how often Claude evaluation runs:

| Mode | Behavior |
|---|---|
| `all` | Evaluate every processed transcript |
| `sample` | Evaluate a random percentage set by `sample_rate` |
| `first` | Evaluate only the first `first_n` processed transcripts |

## Output metrics

After each run the processor prints a summary including:

- Per-file processing time, word count, action item count, issue count
- Quality scores (keyword coverage, completeness, accuracy, relevance) where enabled
- Batch totals: total files, success/failure count, total processing time

## Project structure

```
.
├── super_secretary.py          # Entry point
├── config.py                   # Configuration and prompt management
├── config.yaml                 # Working application settings
├── prompts.yaml                # Working AI prompts and domain assignments
├── requirements.txt            # Python dependencies
├── setup_venv.sh               # macOS/Linux venv setup
├── setup_venv.bat              # Windows venv setup
├── .env.example                # Credential template
├── config.example.yaml         # Config template
├── prompts.example.yaml        # Prompts template
├── agents/
│   ├── base_agent.py           # Abstract base class
│   ├── coordinator_agent.py    # Pipeline orchestration
│   ├── document_reader_agent.py
│   ├── secretary_agent.py
│   ├── output_writer_agent.py
│   ├── quality_evaluator.py
│   └── metrics.py
└── transcripts/                # Drop .docx files here
```

## Dependencies

| Package | Purpose |
|---|---|
| `boto3` | AWS SDK — Bedrock client |
| `python-docx` | Read and write `.docx` files |
| `python-dotenv` | Load `.env` credentials |
| `PyYAML` | Parse `config.yaml` and `prompts.yaml` |

## Troubleshooting

| Symptom | What to check |
|---|---|
| `transcripts` folder not found | Create `transcripts/` or pass a file/folder path on the command line |
| Missing or expired AWS credentials | The app should launch `go-aws-sso --persist` automatically. Confirm `go-aws-sso` is installed, set `AWS_PROFILE` or `aws.profile` if needed, and remove placeholder `.env` values. |
| Bedrock model errors | Confirm the configured model is available in `aws.region` and enabled for your AWS account |
| Slow batch processing | Lower `parallel_processing.max_workers`, disable Claude quality evaluation, or set `batch_mode` to `sample` or `first` |
