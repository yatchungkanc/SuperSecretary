"""
Output Writer Agent - Handles saving and formatting output documents.
"""

from typing import List, Dict
from docx import Document
from datetime import datetime

from agents.base_agent import BaseAgent


class OutputWriterAgent(BaseAgent):
    """Agent responsible for saving and formatting output documents"""
    
    def __init__(self):
        super().__init__("OutputWriter")
    
    def execute(self, results: List[Dict[str, str]], output_file: str = "Meeting_Minutes_Summary.docx") -> bool:
        """
        Save processed results to a Word document.
        
        Args:
            results: List of dictionaries with 'file_name' and 'summary' keys
            output_file: Name of the output file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.log(f"Writing results to {output_file}...")
            
            doc = Document()
            
            # Add title and metadata
            doc.add_heading('Meeting Minutes Summary', 0)
            doc.add_paragraph(f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            doc.add_paragraph('')
            
            # Add each summary
            for i, result in enumerate(results, 1):
                if i > 1:
                    doc.add_page_break()
                
                doc.add_heading(f'Transcript {i}: {result["file_name"]}', 1)
                
                # Split by lines and add as paragraphs
                summary_lines = result["summary"].split('\n')
                for line in summary_lines:
                    if line.strip():
                        doc.add_paragraph(line)
            
            # Save the document
            doc.save(output_file)
            self.log(f"Successfully saved results to {output_file}")
            return True
            
        except Exception as e:
            self.log(f"Error writing output: {e}", "ERROR")
            return False
