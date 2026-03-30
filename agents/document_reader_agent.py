"""
Document Reader Agent - Handles reading and parsing document files.
"""

import os
from typing import Optional
from docx import Document

from agents.base_agent import BaseAgent


class DocumentReaderAgent(BaseAgent):
    """Agent responsible for reading and parsing document files"""
    
    def __init__(self):
        super().__init__("DocumentReader")
    
    def execute(self, file_path: str) -> Optional[str]:
        """
        Read content from a Word document.
        
        Args:
            file_path: Path to the docx file
            
        Returns:
            Text content of the document or None if error
        """
        try:
            self.log(f"Reading document: {os.path.basename(file_path)}")
            doc = Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            content = '\n'.join(full_text)
            self.log(f"Successfully read {len(content)} characters")
            return content
        except Exception as e:
            self.log(f"Error reading {file_path}: {e}", "ERROR")
            return None
