# Meeting Transcript Processor

An agent-based Python application that converts meeting transcripts (`.docx`) into structured meeting minutes using AWS Bedrock Claude. Supports single-file and batch folder processing with parallel execution and optional quality evaluation.

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
pip install -r requirements.txt
```

### 3. Configure AWS credentials

Copy `.env.example` to `.env` and fill in your credentials:

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

### 4. (Optional) Customize application settings

```bash
cp config.example.yaml config.yaml
```

### 5. (Optional) Customize AI prompts and domain assignments

```bash
cp prompts.example.yaml prompts.yaml
```

## Usage

```bash
# Process all .docx files in the default transcripts/ folder
python process_transcript.py

# Process all .docx files in a specific folder
python process_transcript.py path/to/folder

# Process a single file
python process_transcript.py path/to/transcript.docx
```

- Single-file output: `Minutes_<filename>_<YYYY-MM-DD>.docx`
- Batch output: `Meeting_Minutes_Summary_<YYYY-MM-DD>.docx` (base name configurable in `config.yaml`)

## Configuration

Settings are layered in this precedence order (highest to lowest):

| Layer | File | Notes |
|---|---|---|
| 1 | Environment variables | Useful for CI/CD overrides |
| 2 | `config.yaml` | Primary application settings |
| 3 | In-code defaults | Fallback when YAML is absent |

### `config.yaml` options

```yaml
aws:
  sso_renew_command: "go-aws-sso --persist"

model:
  model_id: "global.anthropic.claude-sonnet-4-6"
  temperature: 0.3          # 0.0 = deterministic, 1.0 = creative

parallel_processing:
  max_workers: 3            # Set to 1 for sequential; mind Bedrock rate limits

output:
  default_filename: "Meeting_Minutes_Summary.docx"
  file_prefix: "Minutes_"
```

`aws.sso_renew_command` is the command run when AWS credentials are expired. The default uses the interactive `go-aws-sso` flow so the browser authorization page can open.

Optional environment variable overrides (see `.env.example`):

| Variable | Overrides |
|---|---|
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

## Architecture

```
process_transcript.py          ← Entry point and CLI handling
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

Two optional evaluation modes (configured in `config.yaml` under `quality_evaluation`):

| Method | Description |
|---|---|
| `keyword` | Fast, free — checks keyword coverage between transcript and summary |
| `claude` | AI-powered — scores completeness, accuracy, and relevance via a second Bedrock call |
| `both` | Runs both; composite score weights Claude at 70% and keyword at 30% |

Claude scores are weighted: `overall = (completeness × 0.4) + (accuracy × 0.4) + (relevance × 0.2)`.

## Output metrics

After each run the processor prints a summary including:

- Per-file processing time, word count, action item count, issue count
- Quality scores (keyword coverage, completeness, accuracy, relevance) where enabled
- Batch totals: total files, success/failure count, total processing time

## Project structure

```
.
├── process_transcript.py       # Entry point
├── config.py                   # Configuration and prompt management
├── config.yaml                 # Application settings (git-ignored example provided)
├── prompts.yaml                # AI prompts and domain assignments
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
