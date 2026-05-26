"""
Configuration and prompt management for the Meeting Super Secretary.
"""

import os
import shlex
import subprocess
import sys
import threading
import yaml
import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from dotenv import load_dotenv
from pathlib import Path


_AWS_CREDENTIAL_REFRESH_LOCK = threading.Lock()


class CredentialRefreshError(RuntimeError):
    """Raised when AWS SSO credential refresh fails non-recoverably for this run."""
    pass


class Configuration:
    """Central configuration management - loads from config.yaml and .env"""
    
    def __init__(self, config_file: str = "config.yaml"):
        # Load environment variables from .env
        load_dotenv()
        
        # Load configuration from YAML file
        self._load_config_file(config_file)
        
        # AWS Credentials (from environment variables only - never in config file)
        self._load_aws_credentials()
        self._credential_refresh_count = 0
        self._credential_refresh_failed = False
        
        # Validate credential shape. Missing values are allowed here because
        # verify_aws_credentials can launch the configured SSO flow.
        self._validate_credentials(allow_missing=True)
    
    def _load_config_file(self, config_file: str):
        """Load configuration from YAML file with fallback to defaults"""
        config_path = Path(config_file)
        
        # Default configuration (fallback if file doesn't exist)
        defaults = {
            'aws': {
                'region': 'us-east-1',
                'profile': None,
                'sso_renew_command': 'go-aws-sso --persist'
            },
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
        self.sso_renew_command = config.get('aws', {}).get(
            'sso_renew_command',
            defaults['aws']['sso_renew_command']
        )
        self.aws_region = os.getenv(
            "AWS_REGION",
            config.get('aws', {}).get('region', defaults['aws']['region'])
        )
        self.aws_profile = os.getenv("AWS_PROFILE", config.get('aws', {}).get('profile'))
        
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
    
    def _load_aws_credentials(self):
        """Load AWS credentials from the current environment."""
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_session_token = os.getenv("AWS_SESSION_TOKEN")
        self.aws_region = os.getenv("AWS_REGION", self.aws_region)

        if self._credentials_missing() or self._credentials_placeholder():
            try:
                self._load_credentials_from_aws_profile()
            except (BotoCoreError, ClientError, OSError) as e:
                print(f"Warning: Could not load AWS profile credentials: {e}")

    def _credentials_missing(self) -> bool:
        """Return True if required AWS credential values are absent."""
        return not all([self.aws_access_key_id, self.aws_secret_access_key])

    def _credentials_placeholder(self) -> bool:
        """Return True if AWS credential values are still template placeholders."""
        if self._credentials_missing():
            return False

        placeholders = ("your_", "_here", "example", "replace_me")
        return any(
            any(placeholder in value.lower() for placeholder in placeholders)
            for value in [self.aws_access_key_id, self.aws_secret_access_key]
        )

    def _validate_credentials(self, allow_missing: bool = False):
        """Validate that required credentials are present and not placeholder values"""
        missing = self._credentials_missing()
        placeholder = self._credentials_placeholder()

        if missing and allow_missing:
            return

        if missing or placeholder:
            if placeholder:
                print("Error: AWS credentials still contain placeholder values!")
                print("Edit or remove your .env file, or use a valid AWS profile.")
            else:
                print("Error: Missing required AWS credentials!")
                print("Run go-aws-sso, configure an AWS profile, or create a .env file with:")
            print("  AWS_ACCESS_KEY_ID=your_access_key (if using .env)")
            print("  AWS_SECRET_ACCESS_KEY=your_secret_key (if using .env)")
            print("  AWS_SESSION_TOKEN=your_session_token (if using temporary .env credentials)")
            print("  AWS_REGION=us-east-1 (optional; can also be set in config.yaml)")
            sys.exit(1)

    def _get_go_aws_sso_command(self):
        """Return the interactive go-aws-sso renewal command."""
        if isinstance(self.sso_renew_command, list):
            command = [str(part) for part in self.sso_renew_command]
        else:
            command = shlex.split(str(self.sso_renew_command))

        if not command:
            command = shlex.split("go-aws-sso --persist")

        aws_profile = os.getenv("AWS_PROFILE") or self.aws_profile
        if aws_profile and "--profile" not in command and "-p" not in command:
            command.extend(["--profile", aws_profile])
        return command

    def _profile_from_sso_command(self):
        """Extract --profile/-p from the configured SSO command, if present."""
        command = self._get_go_aws_sso_command()
        for index, part in enumerate(command):
            if part in {"--profile", "-p"} and index + 1 < len(command):
                return command[index + 1]
            if part.startswith("--profile="):
                return part.split("=", 1)[1]
        return None

    def _load_credentials_from_aws_profile(self):
        """Load persisted AWS credentials from the selected shared credentials profile."""
        profile_name = self.aws_profile or self._profile_from_sso_command() or "default"
        session = boto3.Session(profile_name=profile_name)
        credentials = session.get_credentials()

        if credentials is None:
            return False

        frozen_credentials = credentials.get_frozen_credentials()
        self.aws_access_key_id = frozen_credentials.access_key
        self.aws_secret_access_key = frozen_credentials.secret_key
        self.aws_session_token = frozen_credentials.token
        self.aws_region = (
            os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or self.aws_region
            or session.region_name
            or "us-east-1"
        )
        return True

    def refresh_aws_credentials(self, refresh_count_at_error: int = None):
        """
        Renew AWS SSO credentials and reload this configuration's credential values.

        The default flow uses interactive go-aws-sso authorization, because
        `go-aws-sso refresh` cannot recover when the cached SSO session itself
        is invalid. Override `aws.sso_renew_command` in config.yaml if your local
        flow differs.

        Raises CredentialRefreshError if the renewal command fails or is missing.
        Once a refresh has failed in this run, subsequent calls raise immediately
        so parallel workers do not stampede a known-broken refresh.
        """
        with _AWS_CREDENTIAL_REFRESH_LOCK:
            if self._credential_refresh_failed:
                raise CredentialRefreshError(
                    "AWS SSO refresh already failed in this run. "
                    "Exit, run your SSO command manually, then re-launch the app."
                )

            if (
                refresh_count_at_error is not None
                and self._credential_refresh_count > refresh_count_at_error
            ):
                return

            command = self._get_go_aws_sso_command()
            print()
            print("=" * 60)
            print("AWS SSO session expired or missing.")
            print(f"Running: {' '.join(command)}")
            print("A browser window may open for SSO authentication.")
            print("The app is waiting — complete authorization to continue.")
            print("=" * 60)

            try:
                subprocess.run(command, check=True)
            except FileNotFoundError as e:
                self._credential_refresh_failed = True
                raise CredentialRefreshError(
                    f"SSO refresh command '{command[0]}' not found on PATH. "
                    f"Install it, or set aws.sso_renew_command in config.yaml."
                ) from e
            except subprocess.CalledProcessError as e:
                self._credential_refresh_failed = True
                raise CredentialRefreshError(
                    f"SSO refresh exited with code {e.returncode}. "
                    f"Was browser authorization cancelled? Re-launch the app to retry."
                ) from e

            # go-aws-sso normally writes ~/.aws/credentials; reloading .env first
            # also supports teams that sync fresh credentials there.
            load_dotenv(override=True)
            self._load_aws_credentials()

            try:
                self._load_credentials_from_aws_profile()
            except (BotoCoreError, ClientError, OSError) as e:
                print(f"Warning: Could not load AWS profile credentials after refresh: {e}")

            self._validate_credentials()
            self._credential_refresh_count += 1
            print("✓ AWS credentials refreshed.")
            print()

    def verify_aws_credentials(self):
        """Verify current AWS credentials, renewing once if they are expired.

        Probes both STS and Bedrock so a credentials gap is caught at startup
        rather than masquerading as per-file processing failures during batch.
        """
        try:
            identity = self._create_aws_client("sts").get_caller_identity()
        except Exception as e:
            missing = self._credentials_missing() or isinstance(e, NoCredentialsError)
            if not missing and not self.is_expired_credentials_error(e):
                raise

            self.refresh_aws_credentials(self._credential_refresh_count)
            identity = self._create_aws_client("sts").get_caller_identity()

        account = identity.get("Account", "unknown")
        arn = identity.get("Arn", "unknown")
        print(f"✓ AWS credentials verified for account {account}")
        print(f"  Identity: {arn}")

        # Bedrock probe — boto3's default chain can mask staleness at STS while
        # the snapshot we hand to the Bedrock client is rejected. Probing here
        # surfaces the gap before batch processing starts.
        self._probe_bedrock_access()
        return identity

    def _probe_bedrock_access(self):
        """Verify Bedrock accepts current credentials; refresh once if not."""
        def _call_probe():
            self._create_aws_client("bedrock").list_foundation_models()

        try:
            _call_probe()
        except Exception as e:
            if self.is_expired_credentials_error(e):
                self.refresh_aws_credentials(self._credential_refresh_count)
                try:
                    _call_probe()
                except Exception as retry_e:
                    if self.is_expired_credentials_error(retry_e):
                        raise CredentialRefreshError(
                            "Bedrock still rejects credentials after SSO refresh. "
                            "Verify your AWS profile has bedrock access in this region."
                        ) from retry_e
                    # Non-credential error (e.g., AccessDenied on ListFoundationModels)
                    # is acceptable — InvokeModel permission may still be granted.
                    print(f"  Note: Bedrock probe non-blocking error: {retry_e}")
                    return
                print("✓ Bedrock access verified.")
            else:
                # AccessDenied on ListFoundationModels is OK — user may only have
                # InvokeModel. Surface as a note rather than failing startup.
                print(f"  Note: Bedrock probe non-blocking error: {e}")
                return
        else:
            print("✓ Bedrock access verified.")

    @staticmethod
    def is_expired_credentials_error(error: Exception) -> bool:
        """Return True when an AWS error indicates expired/invalid credentials."""
        expired_codes = {
            "ExpiredToken",
            "ExpiredTokenException",
            "RequestExpired",
        }
        # These codes are ambiguous on their own — they only count as
        # expired-credentials when paired with a token-expired message marker.
        possible_expired_codes = {
            "UnauthorizedException",
            "UnrecognizedClientException",
            "InvalidSignatureException",
            "InvalidClientTokenId",
            "AccessDeniedException",
            "ValidationException",
        }
        # botocore SSO exception class names (not ClientError subclasses)
        sso_error_names = {
            "UnauthorizedSSOTokenError",
            "SSOTokenLoadError",
            "TokenRetrievalError",
        }
        expired_markers = (
            "expired token",
            "token has expired",
            "token is expired",
            "security token included in the request is expired",
            "security token included in the request is invalid",
            "invalid security token",
            "expired credentials",
            "credentials have expired",
            "session token has expired",
            "signature has expired",
            "sso session associated with this profile has expired",
            "sso session has expired",
        )

        current = error
        seen = set()
        while current and id(current) not in seen:
            seen.add(id(current))

            if type(current).__name__ in sso_error_names:
                return True

            if isinstance(current, ClientError):
                aws_error = current.response.get("Error", {})
                code = aws_error.get("Code", "")
                message = aws_error.get("Message", "")
                if code in expired_codes:
                    return True
                if code in possible_expired_codes and any(
                    marker in message.lower() for marker in expired_markers
                ):
                    return True

            text = str(current).lower()
            if any(marker in text for marker in expired_markers):
                return True

            current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)

        return False

    def converse_with_auto_refresh(self, client, **kwargs):
        """Call Bedrock Converse, renewing expired SSO credentials once if needed.

        Propagates CredentialRefreshError if refresh has irrecoverably failed —
        the caller should let this propagate so the batch can halt cleanly
        instead of every file logging an opaque per-file error.
        """
        client_refresh_count = getattr(
            client,
            "_secretary_credential_refresh_count",
            self._credential_refresh_count,
        )
        try:
            return client.converse(**kwargs), client
        except Exception as e:
            if not self.is_expired_credentials_error(e):
                raise

            if client_refresh_count >= self._credential_refresh_count:
                self.refresh_aws_credentials(client_refresh_count)
            refreshed_client = self.create_bedrock_client()
            return refreshed_client.converse(**kwargs), refreshed_client
    
    def create_bedrock_client(self):
        """Create and return AWS Bedrock client"""
        client = self._create_aws_client(
            "bedrock-runtime",
            config=BotocoreConfig(
                read_timeout=300,
                connect_timeout=30,
                retries={"max_attempts": 3, "mode": "adaptive"}
            )
        )
        client._secretary_credential_refresh_count = self._credential_refresh_count
        return client

    def _create_aws_client(self, service_name: str, **kwargs):
        """Create an AWS client using this configuration's current credentials."""
        return boto3.client(
            service_name,
            region_name=self.aws_region,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            **kwargs
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
