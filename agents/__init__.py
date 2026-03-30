"""
Agents package for Meeting Transcript Processor.

This package contains all agent classes organized by responsibility:
- BaseAgent: Abstract base class for all agents
- DocumentReaderAgent: Reads and parses document files
- SecretaryAgent: AI agent that processes transcripts
- OutputWriterAgent: Saves and formats output documents
- CoordinatorAgent: Orchestrates the workflow
- MetricsCollector: Tracks performance and quality metrics
"""

from agents.base_agent import BaseAgent
from agents.document_reader_agent import DocumentReaderAgent
from agents.secretary_agent import SecretaryAgent
from agents.output_writer_agent import OutputWriterAgent
from agents.coordinator_agent import CoordinatorAgent
from agents.quality_evaluator import QualityEvaluator
from agents.metrics import MetricsCollector, TranscriptMetrics, BatchMetrics

__all__ = [
    'BaseAgent',
    'DocumentReaderAgent',
    'SecretaryAgent',
    'OutputWriterAgent',
    'CoordinatorAgent',
    'QualityEvaluator',
    'MetricsCollector',
    'TranscriptMetrics',
    'BatchMetrics',
]

