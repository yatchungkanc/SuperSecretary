"""
Configuration and prompt management for the Meeting Transcript Processor.
"""

import os
import sys
import yaml
import boto3
from botocore.config import Config as BotocoreConfig
from dotenv import load_dotenv
from pathlib import Path


class Configuration:
    """Central configuration management - loads from config.yaml and .env"""
    
    def __init__(self, config_file: str = "config.yaml"):
        # Load environment variables from .env
        load_dotenv()
        
        # Load configuration from YAML file
        self._load_config_file(config_file)
        
        # AWS Credentials (from environment variables only - never in config file)
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_session_token = os.getenv("AWS_SESSION_TOKEN")
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        
        # Validate credentials
        self._validate_credentials()
    
    def _load_config_file(self, config_file: str):
        """Load configuration from YAML file with fallback to defaults"""
        config_path = Path(config_file)
        
        # Default configuration (fallback if file doesn't exist)
        defaults = {
            'model': {
                'model_id': 'global.anthropic.claude-sonnet-4-6',
                'temperature': 0.3
            },
            'parallel_processing': {
                'max_workers': 3
            },
            'output': {
                'default_filename': 'Meeting_Minutes_Summary.docx',
                'file_prefix': 'Minutes_'
            }
        }
        
        # Try to load from YAML file
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
                print(f"✓ Loaded configuration from {config_file}")
            except Exception as e:
                print(f"Warning: Could not parse {config_file}: {e}")
                print("Using default configuration values")
                config = {}
        else:
            print(f"Note: {config_file} not found, using default configuration")
            print(f"You can copy {config_file}.example to {config_file} to customize settings")
            config = {}
        
        # Merge with defaults (config file values override defaults)
        def deep_merge(default, override):
            """Recursively merge override into default"""
            result = default.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result
        
        config = deep_merge(defaults, config)
        
        # Model settings (environment variables can override config file)
        self.model_id = os.getenv("MODEL_ID", config['model']['model_id'])
        self.temperature = float(os.getenv("TEMPERATURE", config['model']['temperature']))
        
        # Parallel processing settings (environment variable overrides config file)
        self.max_parallel_workers = int(
            os.getenv("MAX_PARALLEL_WORKERS", config['parallel_processing']['max_workers'])
        )
        
        # Output settings
        self.default_output_filename = config['output']['default_filename']
        self.output_file_prefix = config['output']['file_prefix']
        
        # Quality evaluation settings
        if 'quality_evaluation' in config:
            qe = config['quality_evaluation']
            self.quality_eval_enabled = qe.get('enabled', True)
            self.quality_eval_method = qe.get('method', 'both')
            
            # Keyword settings
            if 'keyword' in qe:
                self.keyword_min_coverage = qe['keyword'].get('min_coverage', 50)
                self.keyword_extract_method = qe['keyword'].get('extract_method', 'frequency')
                self.keyword_top_n = qe['keyword'].get('top_keywords', 30)
            else:
                self.keyword_min_coverage = 50
                self.keyword_extract_method = 'frequency'
                self.keyword_top_n = 30
            
            # Claude evaluation settings
            if 'claude' in qe:
                self.claude_eval_enabled = qe['claude'].get('enabled', True)
                self.claude_min_overall = qe['claude'].get('min_overall_score', 70)
                self.claude_min_completeness = qe['claude'].get('min_completeness', 75)
                self.claude_min_accuracy = qe['claude'].get('min_accuracy', 80)
                self.claude_min_relevance = qe['claude'].get('min_relevance', 75)
                self.claude_batch_mode = qe['claude'].get('batch_mode', 'all')
                self.claude_sample_rate = qe['claude'].get('sample_rate', 0.2)
                self.claude_first_n = qe['claude'].get('first_n', 3)
            else:
                self.claude_eval_enabled = True
                self.claude_min_overall = 70
                self.claude_min_completeness = 75
                self.claude_min_accuracy = 80
                self.claude_min_relevance = 75
                self.claude_batch_mode = 'all'
                self.claude_sample_rate = 0.2
                self.claude_first_n = 3
        else:
            # Defaults if quality_evaluation section missing
            self.quality_eval_enabled = False
            self.quality_eval_method = 'keyword'
            self.keyword_min_coverage = 50
            self.keyword_extract_method = 'frequency'
            self.keyword_top_n = 30
            self.claude_eval_enabled = False
    
    def _validate_credentials(self):
        """Validate that required credentials are present and not placeholder values"""
        _PLACEHOLDERS = ("your_", "_here", "example", "replace_me")

        def _is_placeholder(value: str) -> bool:
            return any(p in value.lower() for p in _PLACEHOLDERS)

        missing = not all([self.aws_access_key_id, self.aws_secret_access_key])
        placeholder = not missing and any(
            _is_placeholder(v)
            for v in [self.aws_access_key_id, self.aws_secret_access_key]
        )

        if missing or placeholder:
            if placeholder:
                print("Error: AWS credentials still contain placeholder values!")
                print("Edit your .env file and replace the placeholder values with real credentials.")
            else:
                print("Error: Missing required AWS credentials!")
                print("Please create a .env file with the following variables:")
            print("  AWS_ACCESS_KEY_ID=your_access_key")
            print("  AWS_SECRET_ACCESS_KEY=your_secret_key")
            print("  AWS_SESSION_TOKEN=your_session_token (if using temporary credentials)")
            print("  AWS_REGION=us-east-1 (optional, defaults to us-east-1)")
            sys.exit(1)
    
    def create_bedrock_client(self):
        """Create and return AWS Bedrock client"""
        return boto3.client(
            "bedrock-runtime",
            region_name=self.aws_region,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            config=BotocoreConfig(
                read_timeout=300,
                connect_timeout=30,
                retries={"max_attempts": 3, "mode": "adaptive"}
            )
        )


class PromptLibrary:
    """Central repository for prompts and roles - loads from prompts.yaml"""
    
    def __init__(self, prompts_file: str = "prompts.yaml"):
        """Initialize prompt library by loading from YAML file"""
        self._load_prompts(prompts_file)
    
    def _load_prompts(self, prompts_file: str):
        """Load prompts from YAML file with fallback to defaults"""
        prompts_path = Path(prompts_file)
        
        # Default prompts (fallback if file doesn't exist)
        defaults = {
            'secretary_role': """You are a professional executive secretary. You are organized, efficient, 
and diplomatic. You help with scheduling, correspondence, and administrative tasks. 
You communicate in a professional yet friendly manner. You excel at summarizing meetings 
and creating clear, actionable meeting minutes.""",
            'domain_assignments': [
                {'name': 'Mahesh', 'domain': 'Document'},
                {'name': 'Pavan', 'domain': 'Sources'},
                {'name': 'Rahul and Karunakar', 'domain': 'Opsbank II'},
                {'name': 'Shankarsh or Varma', 'domain': 'Works'},
                {'name': 'Daniel', 'domain': 'PPE / MARS'},
                {'name': 'Narasimha Reddy', 'domain': 'Consumption'}
            ],
            'transcript_summary_prompt': """Your job is to summarize the essence of a transcript for managers to discuss in management meeting. The people belong to different domains.

{domain_list}

Please summarize the attached meeting transcript into meeting minutes with date and attendees so that:
1. It contains two sections: issues discussed and action items
2. Issues discussed are organized by speakers and in bullet form
3. Action items table has the following columns: Discussion domain | Items | Responsible person | Deadline | Notes

Action items table should already be native in MS Word so no further conversion is needed.

Here is the transcript:

{transcript}""",
            'quality_evaluation_prompt': """You are an expert evaluator assessing the quality of meeting minutes.

Evaluate how well the summary captures key information from the original transcript.

ORIGINAL TRANSCRIPT:
---
{transcript}
---

GENERATED SUMMARY:
---
{summary}
---

Rate on 0-100 scale:
1. COMPLETENESS: Are all important points included?
2. ACCURACY: Any misrepresentations or hallucinations?
3. RELEVANCE: Focus on management-relevant information?

Respond in JSON format:
{{
  "completeness_score": <0-100>,
  "accuracy_score": <0-100>,
  "relevance_score": <0-100>,
  "overall_score": <0-100>,
  "feedback": "<2-3 sentence explanation>"
}}

Overall score = (completeness * 0.4 + accuracy * 0.4 + relevance * 0.2)"""
        }
        
        # Try to load from YAML file
        if prompts_path.exists():
            try:
                with open(prompts_path, 'r') as f:
                    prompts = yaml.safe_load(f) or {}
                print(f"✓ Loaded prompts from {prompts_file}")
            except Exception as e:
                print(f"Warning: Could not parse {prompts_file}: {e}")
                print("Using default prompts")
                prompts = {}
        else:
            print(f"Note: {prompts_file} not found, using default prompts")
            print(f"You can copy {prompts_file}.example to {prompts_file} to customize prompts")
            prompts = {}
        
        # Merge with defaults
        prompts = {**defaults, **prompts}
        
        # Set properties
        self.SECRETARY_ROLE = prompts['secretary_role']
        
        # Build domain list string from domain assignments
        domain_list = self._build_domain_list(prompts['domain_assignments'])
        
        # Create the final transcript summary prompt with domain list
        self.TRANSCRIPT_SUMMARY_PROMPT = prompts['transcript_summary_prompt'].format(
            domain_list=domain_list,
            transcript="{transcript}"  # Keep transcript as a placeholder for later formatting
        )
        
        # Set quality evaluation prompt
        self.QUALITY_EVALUATION_PROMPT = prompts.get(
            'quality_evaluation_prompt',
            defaults['quality_evaluation_prompt']
        )
    
    def _build_domain_list(self, domain_assignments: list) -> str:
        """Build formatted domain list string from assignments"""
        lines = []
        for assignment in domain_assignments:
            lines.append(f"{assignment['name']} - {assignment['domain']}")
        return "\n".join(lines)
