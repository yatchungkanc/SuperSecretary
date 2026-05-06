"""
Main entry point for Meeting Super Secretary.

Agent-based architecture for processing meeting transcripts using AWS Bedrock Claude.

Architecture:
    - BaseAgent: Abstract base class for all agents
    - DocumentReaderAgent: Handles reading and parsing documents
    - SecretaryAgent: AI agent that processes transcripts using Claude
    - OutputWriterAgent: Handles saving and formatting output documents
    - CoordinatorAgent: Orchestrates the workflow and manages batch processing
    - MetricsCollector: Tracks processing time and output quality metrics
    - TranscriptProcessorOrchestrator: Main entry point that coordinates all agents

Setup:
    1. Install dependencies: pip install -r requirements.txt
    2. Create a .env file with your AWS credentials (see .env.example)
    3. (Optional) Copy config.example.yaml to config.yaml to customize settings
    4. (Optional) Copy prompts.example.yaml to prompts.yaml to customize AI prompts
    5. Create a 'transcripts' folder with your .docx files

Usage:
    # Process all files in transcripts folder (default)
    python super_secretary.py
    
    # Process all files in a specific folder
    python super_secretary.py path/to/folder
    
    # Process a single file
    python super_secretary.py path/to/transcript.docx

Configuration:
    Application settings are managed through three files:
    - .env: AWS credentials and sensitive data (never commit to git)
    - config.yaml: Application parameters (model settings, parallel processing, etc.)
    - prompts.yaml: AI prompts and domain assignments (safe to commit)
    
    Environment variables can override config.yaml settings:
    - MAX_PARALLEL_WORKERS: Max concurrent transcript processing
    - MODEL_ID: AWS Bedrock model to use
    - TEMPERATURE: AI temperature setting (0.0-1.0)
"""

import os
import sys
import glob
from datetime import datetime

from config import Configuration
from agents import CoordinatorAgent, OutputWriterAgent


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

class TranscriptProcessorOrchestrator:
    """Main orchestrator that manages the entire transcript processing workflow"""
    
    def __init__(self):
        self.config = Configuration()
        self.config.verify_aws_credentials()
        print("✓ Credential verification complete. Processing setup started.\n")
        self.coordinator = CoordinatorAgent(self.config)
        self.writer = OutputWriterAgent()

    def _add_generation_date_to_filename(self, filename: str) -> str:
        """Append the generation date before the file extension."""
        base_name, extension = os.path.splitext(filename)
        generation_date = datetime.now().strftime("%Y-%m-%d")
        return f"{base_name}_{generation_date}{extension}"
    
    def process_single_file(self, file_path: str) -> bool:
        """
        Process a single transcript file.
        
        Args:
            file_path: Path to the transcript file
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return False
        
        # Initialize metrics for single file
        self.coordinator.metrics_collector.start_batch()
        print("Progress: 0/1 files complete")
        
        result = self.coordinator.execute(file_path)
        
        if result:
            print("Progress: 1/1 files complete")
            # Display summary
            print("\n" + "="*60)
            print(f"Summary for: {result['file_name']}")
            print("="*60)
            print(result['summary'])
            
            # Save to individual file
            os.makedirs("output", exist_ok=True)
            output_filename = self._add_generation_date_to_filename(
                f"{self.config.output_file_prefix}{result['file_name']}"
            )
            output_filename = os.path.join("output", output_filename)
            self.writer.execute([result], output_filename)
            
            # Show metrics
            self.coordinator.metrics_collector.end_batch()
            batch_metrics = self.coordinator.metrics_collector.get_batch_metrics()
            batch_metrics.print_summary()
            
            return True
        else:
            print("Progress: 1/1 files complete")
            print("Failed to process transcript.")
            
            # Show metrics even for failed processing
            self.coordinator.metrics_collector.end_batch()
            batch_metrics = self.coordinator.metrics_collector.get_batch_metrics()
            batch_metrics.print_summary()
            
            return False
    
    def process_folder(self, folder_path: str, output_file: str = None) -> bool:
        """
        Process all docx transcripts in a folder.
        
        Args:
            folder_path: Path to folder containing transcript files
            output_file: Name of the output Word document (uses config default if None)
            
        Returns:
            True if at least one file was processed, False otherwise
        """
        # Use config default if no output file specified
        if output_file is None:
            output_file = self.config.default_output_filename
        
        # Validate folder
        if not os.path.exists(folder_path):
            print(f"Error: Folder '{folder_path}' not found!")
            print(f"Please create the folder and add your transcript files.")
            return False
        
        if not os.path.isdir(folder_path):
            print(f"Error: '{folder_path}' is not a folder!")
            return False
        
        # Get all docx files
        transcript_files = glob.glob(os.path.join(folder_path, "*.docx"))
        
        if not transcript_files:
            print(f"No .docx files found in '{folder_path}' folder!")
            return False
        
        print(f"Found {len(transcript_files)} transcript(s) to process.\n")
        print(f"Progress: 0/{len(transcript_files)} files complete")
        
        # Process batch
        results = self.coordinator.execute_batch(transcript_files)
        
        if results:
            # Save combined results
            os.makedirs("output", exist_ok=True)
            output_file = self._add_generation_date_to_filename(os.path.basename(output_file))
            output_file = os.path.join("output", output_file)
            self.writer.execute(results, output_file)
            
            # Display preview
            print(f"\n✓ Successfully processed {len(results)} file(s)")
            if results:
                print("\n" + "="*60)
                print("PREVIEW - First Summary:")
                print("="*60)
                preview = results[0]["summary"]
                print(preview[:500] + "..." if len(preview) > 500 else preview)
            
            return True
        else:
            print("No files were processed.")
            return False


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main execution function"""
    print("Meeting Super Secretary (Agent-based Architecture)")
    print("="*60 + "\n")
    
    # Determine what to process based on command line arguments
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        input_path = "transcripts"
        print(f"No path specified. Using default folder: {input_path}")
        print("\nUsage:")
        print("  Process folder:      python super_secretary.py path/to/folder")
        print("  Process single file: python super_secretary.py path/to/file.docx\n")

    if not os.path.isdir(input_path) and not os.path.isfile(input_path):
        print(f"Error: '{input_path}' is neither a file nor a directory!")
        print("\nPlease provide:")
        print("  - A folder path containing .docx transcript files, or")
        print("  - A path to a single .docx transcript file")
        sys.exit(1)

    # Create orchestrator after input validation so credential verification happens
    # immediately before real processing starts.
    try:
        orchestrator = TranscriptProcessorOrchestrator()
    except Exception as e:
        print(f"Error: Failed to initialize processor: {e}")
        sys.exit(1)
    
    # Check if input is a directory or a file
    if os.path.isdir(input_path):
        # Process all files in the directory
        print(f"Processing all .docx files in folder: {input_path}\n")
        success = orchestrator.process_folder(input_path)
        sys.exit(0 if success else 1)
            
    elif os.path.isfile(input_path):
        # Process single file
        print(f"Processing single file: {input_path}\n")
        success = orchestrator.process_single_file(input_path)
        sys.exit(0 if success else 1)
            
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
