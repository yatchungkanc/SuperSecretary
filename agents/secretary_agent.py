"""
Secretary Agent - AI agent that processes transcripts using Claude.
"""

from typing import Optional

from agents.base_agent import BaseAgent
from config import Configuration, PromptLibrary


class SecretaryAgent(BaseAgent):
    """AI agent that processes transcripts using Claude"""
    
    def __init__(self, config: Configuration):
        super().__init__("SecretaryAI")
        self.config = config
        self.client = config.create_bedrock_client()
        self.prompt_library = PromptLibrary()
    
    def execute(self, transcript_content: str) -> Optional[str]:
        """
        Process transcript content and generate meeting minutes.
        
        Args:
            transcript_content: Raw transcript text
            
        Returns:
            Generated meeting minutes or None if error
        """
        self.log("Processing transcript with AI...")
        
        # Create prompt
        prompt = self.prompt_library.TRANSCRIPT_SUMMARY_PROMPT.format(
            transcript=transcript_content
        )
        
        # Prepare messages
        messages = [{
            "role": "user",
            "content": [{"text": prompt}]
        }]
        
        try:
            # Call Claude API
            response, self.client = self.config.converse_with_auto_refresh(
                self.client,
                modelId=self.config.model_id,
                messages=messages,
                system=[{"text": self.prompt_library.SECRETARY_ROLE}],
                inferenceConfig={"temperature": self.config.temperature}
            )
            
            summary = response["output"]["message"]["content"][0]["text"]
            self.log("Successfully generated meeting minutes")
            return summary
            
        except Exception as e:
            self.log(f"Error during AI processing: {e}", "ERROR")
            return None
