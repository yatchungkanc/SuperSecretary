"""
Base agent abstract class for all agents in the system.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger_prefix = f"[{name}]"
    
    def log(self, message: str, level: str = "INFO"):
        """Simple logging method"""
        print(f"{self.logger_prefix} {level}: {message}")
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Main execution method - must be implemented by subclasses"""
        pass
