"""
Coordinator Agent - Orchestrates the workflow of processing transcripts.
"""

import os
import time
import random
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from agents.base_agent import BaseAgent
from agents.document_reader_agent import DocumentReaderAgent
from agents.secretary_agent import SecretaryAgent
from agents.output_writer_agent import OutputWriterAgent
from agents.quality_evaluator import QualityEvaluator
from agents.metrics import MetricsCollector, TranscriptMetrics
from config import Configuration, CredentialRefreshError


class CoordinatorAgent(BaseAgent):
    """Agent that orchestrates the workflow of processing transcripts"""
    
    def __init__(self, config: Configuration):
        super().__init__("Coordinator")
        self.config = config
        
        # Initialize subagents
        self.reader_agent = DocumentReaderAgent()
        self.secretary_agent = SecretaryAgent(config)
        self.writer_agent = OutputWriterAgent()
        self.quality_evaluator = QualityEvaluator(config)
        
        # Thread-safe print lock for parallel processing
        self.print_lock = Lock()
        
        # Metrics collector
        self.metrics_collector = MetricsCollector()
        
        # Quality evaluation tracking for batch processing
        self.batch_file_count = 0
        self.files_evaluated = 0
        
        # Load quality evaluation settings
        self.eval_enabled = getattr(config, 'quality_eval_enabled', True)
        self.claude_enabled = getattr(config, 'claude_eval_enabled', True)
    
    def execute(self, file_path: str) -> Optional[Dict[str, str]]:
        """
        Process a single transcript file through the agent pipeline.
        
        Args:
            file_path: Path to the transcript file
            
        Returns:
            Dictionary with file_name and summary, or None if error
        """
        file_name = os.path.basename(file_path)
        start_time = time.time()
        error_message = None
        
        self.log(f"Coordinating processing for: {file_name}")
        
        # Step 1: Read document
        content = self.reader_agent.execute(file_path)
        if content is None:
            error_message = "Failed to read file"
            self.log(f"Failed to read {file_path}", "ERROR")
            
            # Record failed metric
            processing_time = time.time() - start_time
            metric = TranscriptMetrics(
                file_name=file_name,
                processing_time=processing_time,
                word_count=0,
                action_items_count=0,
                issues_count=0,
                success=False,
                error_message=error_message
            )
            self.metrics_collector.add_metric(metric)
            return None
        
        # Step 2: Process with AI
        summary = self.secretary_agent.execute(content)
        if summary is None:
            error_message = "AI processing failed"
            self.log(f"Failed to process {file_path}", "ERROR")
            
            # Record failed metric
            processing_time = time.time() - start_time
            metric = TranscriptMetrics(
                file_name=file_name,
                processing_time=processing_time,
                word_count=0,
                action_items_count=0,
                issues_count=0,
                success=False,
                error_message=error_message
            )
            self.metrics_collector.add_metric(metric)
            return None
        
        # Step 3: Analyze summary and record metrics
        processing_time = time.time() - start_time
        quality_metrics = MetricsCollector.analyze_summary(summary)
        
        # Step 4: Quality evaluation (if enabled)
        quality_result = None
        if self.config.quality_eval_enabled:
            quality_result = self.quality_evaluator.evaluate(content, summary)
        
        # Create metric with quality scores
        metric = TranscriptMetrics(
            file_name=file_name,
            processing_time=processing_time,
            word_count=quality_metrics['word_count'],
            action_items_count=quality_metrics['action_items_count'],
            issues_count=quality_metrics['issues_count'],
            success=True
        )
        
        # Add quality scores to metric
        if quality_result:
            metric.quality_score = quality_result.get('overall_quality')
            metric.keyword_coverage = quality_result.get('keyword_coverage')
            
            if quality_result.get('claude_scores'):
                claude = quality_result['claude_scores']
                metric.completeness_score = claude.get('completeness_score')
                metric.accuracy_score = claude.get('accuracy_score')
                metric.relevance_score = claude.get('relevance_score')
            
            metric.quality_warnings = quality_result.get('warnings', [])
        
        self.metrics_collector.add_metric(metric)
        
        # Return result
        result = {
            "file_name": file_name,
            "summary": summary
        }
        
        self.log(f"✓ Completed processing: {file_name} ({processing_time:.2f}s)")
        return result
    
    def execute_batch(self, file_paths: List[str]) -> List[Dict[str, str]]:
        """
        Process multiple transcript files in parallel.
        
        Args:
            file_paths: List of file paths to process
            
        Returns:
            List of result dictionaries
        """
        # Start metrics collection
        self.metrics_collector = MetricsCollector()
        self.metrics_collector.start_batch()
        
        max_workers = self.config.max_parallel_workers
        
        if max_workers <= 1:
            # Sequential processing (original behavior)
            self.log(f"Starting sequential processing of {len(file_paths)} files")
            results = self._execute_batch_sequential(file_paths)
        else:
            # Parallel processing
            self.log(f"Starting parallel processing of {len(file_paths)} files (max {max_workers} workers)")
            print("="*60)
            
            results = []
            halt_reason: Optional[str] = None
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_file = {
                    executor.submit(self._process_file_safe, file_path): file_path
                    for file_path in file_paths
                }

                # Process completed tasks as they finish
                completed = 0
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    completed += 1

                    if halt_reason:
                        future.cancel()
                        continue

                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                            with self.print_lock:
                                print(f"[{completed}/{len(file_paths)}] ✓ Completed: {os.path.basename(file_path)}")
                                print(f"Progress: {completed}/{len(file_paths)} files complete")
                        else:
                            with self.print_lock:
                                print(f"[{completed}/{len(file_paths)}] ✗ Failed: {os.path.basename(file_path)}")
                                print(f"Progress: {completed}/{len(file_paths)} files complete")
                    except CredentialRefreshError as e:
                        halt_reason = str(e)
                        with self.print_lock:
                            print()
                            print("=" * 60)
                            print(f"Batch halted: AWS credentials cannot be refreshed.")
                            print(f"  {halt_reason}")
                            print("=" * 60)
                            print()
                        # Cancel any not-yet-started futures
                        for pending in future_to_file:
                            pending.cancel()
                    except Exception as e:
                        if self.config.is_expired_credentials_error(e):
                            halt_reason = (
                                "AWS credentials expired during processing and "
                                "auto-refresh did not recover."
                            )
                            with self.print_lock:
                                print()
                                print("=" * 60)
                                print(f"Batch halted: {halt_reason}")
                                print(f"  Underlying error: {e}")
                                print("=" * 60)
                                print()
                            for pending in future_to_file:
                                pending.cancel()
                            continue
                        with self.print_lock:
                            print(f"[{completed}/{len(file_paths)}] ✗ Error processing {os.path.basename(file_path)}: {str(e)}")
                            print(f"Progress: {completed}/{len(file_paths)} files complete")

                    with self.print_lock:
                        print()  # Blank line between status updates

            print("="*60)
            if halt_reason:
                self.log(
                    f"Batch halted after {len(results)}/{len(file_paths)} files: {halt_reason}",
                    "ERROR",
                )
            else:
                self.log(f"Batch complete: {len(results)}/{len(file_paths)} files processed successfully")
        
        # End metrics collection and print summary
        self.metrics_collector.end_batch()
        batch_metrics = self.metrics_collector.get_batch_metrics()
        batch_metrics.print_summary()
        
        return results
    
    def _execute_batch_sequential(self, file_paths: List[str]) -> List[Dict[str, str]]:
        """
        Process multiple transcript files sequentially (original implementation).
        
        Args:
            file_paths: List of file paths to process
            
        Returns:
            List of result dictionaries
        """
        print("="*60)

        results = []
        halt_reason: Optional[str] = None
        for index, file_path in enumerate(file_paths, start=1):
            try:
                result = self.execute(file_path)
            except CredentialRefreshError as e:
                halt_reason = str(e)
                print()
                print("=" * 60)
                print("Batch halted: AWS credentials cannot be refreshed.")
                print(f"  {halt_reason}")
                print("=" * 60)
                print()
                break
            except Exception as e:
                if self.config.is_expired_credentials_error(e):
                    halt_reason = (
                        "AWS credentials expired during processing and "
                        "auto-refresh did not recover."
                    )
                    print()
                    print("=" * 60)
                    print(f"Batch halted: {halt_reason}")
                    print(f"  Underlying error: {e}")
                    print("=" * 60)
                    print()
                    break
                raise

            if result:
                results.append(result)
            print(f"Progress: {index}/{len(file_paths)} files complete")
            print()  # Blank line between files

        print("="*60)
        if halt_reason:
            self.log(
                f"Batch halted after {len(results)}/{len(file_paths)} files: {halt_reason}",
                "ERROR",
            )
        else:
            self.log(f"Batch complete: {len(results)}/{len(file_paths)} files processed successfully")

        return results
    
    def _process_file_safe(self, file_path: str) -> Optional[Dict[str, str]]:
        """
        Thread-safe wrapper for processing a single file with metrics tracking.
        
        Args:
            file_path: Path to the transcript file
            
        Returns:
            Dictionary with file_name and summary, or None if error
        """
        file_name = os.path.basename(file_path)
        start_time = time.time()
        error_message = None
        
        try:
            with self.print_lock:
                self.log(f"Processing: {file_name}")
            
            # Step 1: Read document
            content = self.reader_agent.execute(file_path)
            if content is None:
                error_message = "Failed to read file"
                with self.print_lock:
                    self.log(f"Failed to read {file_path}", "ERROR")
                
                # Record failed metric
                processing_time = time.time() - start_time
                metric = TranscriptMetrics(
                    file_name=file_name,
                    processing_time=processing_time,
                    word_count=0,
                    action_items_count=0,
                    issues_count=0,
                    success=False,
                    error_message=error_message
                )
                self.metrics_collector.add_metric(metric)
                return None
            
            # Step 2: Process with AI
            summary = self.secretary_agent.execute(content)
            if summary is None:
                error_message = "AI processing failed"
                with self.print_lock:
                    self.log(f"Failed to process {file_path}", "ERROR")
                
                # Record failed metric
                processing_time = time.time() - start_time
                metric = TranscriptMetrics(
                    file_name=file_name,
                    processing_time=processing_time,
                    word_count=0,
                    action_items_count=0,
                    issues_count=0,
                    success=False,
                    error_message=error_message
                )
                self.metrics_collector.add_metric(metric)
                return None
            
            # Step 3: Analyze summary and record metrics
            processing_time = time.time() - start_time
            quality_metrics = MetricsCollector.analyze_summary(summary)
            
            # Step 4: Quality evaluation (if enabled and should evaluate this file)
            should_evaluate = self._should_evaluate_quality()
            quality_result = None
            
            if self.config.quality_eval_enabled and should_evaluate:
                quality_result = self.quality_evaluator.evaluate(content, summary)
                with self.print_lock:
                    self.files_evaluated += 1
            
            # Create metric with quality scores
            metric = TranscriptMetrics(
                file_name=file_name,
                processing_time=processing_time,
                word_count=quality_metrics['word_count'],
                action_items_count=quality_metrics['action_items_count'],
                issues_count=quality_metrics['issues_count'],
                success=True
            )
            
            # Add quality scores to metric
            if quality_result:
                metric.quality_score = quality_result.get('overall_quality')
                metric.keyword_coverage = quality_result.get('keyword_coverage')
                
                if quality_result.get('claude_scores'):
                    claude = quality_result['claude_scores']
                    metric.completeness_score = claude.get('completeness_score')
                    metric.accuracy_score = claude.get('accuracy_score')
                    metric.relevance_score = claude.get('relevance_score')
                
                metric.quality_warnings = quality_result.get('warnings', [])
            
            self.metrics_collector.add_metric(metric)
            
            # Return result
            result = {
                "file_name": file_name,
                "summary": summary
            }
            
            return result
            
        except CredentialRefreshError:
            # Propagate so the batch can halt cleanly rather than logging
            # an opaque per-file failure for every remaining worker.
            raise
        except Exception as e:
            if self.config.is_expired_credentials_error(e):
                # Auth failure auto-refresh could not recover from — halt batch.
                raise
            error_message = str(e)
            with self.print_lock:
                self.log(f"Exception processing {file_path}: {error_message}", "ERROR")

            # Record failed metric
            processing_time = time.time() - start_time
            metric = TranscriptMetrics(
                file_name=file_name,
                processing_time=processing_time,
                word_count=0,
                action_items_count=0,
                issues_count=0,
                success=False,
                error_message=error_message
            )
            self.metrics_collector.add_metric(metric)
            return None
    
    def _should_evaluate_quality(self) -> bool:
        """
        Determine if quality evaluation should run for current file based on batch mode.
        
        Batch modes:
        - "all": Evaluate every file (most accurate, highest cost)
        - "sample": Randomly sample files based on sample_rate (balanced)
        - "first": Only evaluate first N files (quick testing)
        
        Returns:
            bool: True if quality evaluation should run
        """
        if not self.eval_enabled or not self.claude_enabled:
            return False
        
        batch_mode = getattr(self.config, 'claude_batch_mode', 'all')
        
        if batch_mode == 'all':
            return True
        elif batch_mode == 'first':
            first_n = getattr(self.config, 'claude_first_n', 5)
            return self.files_evaluated < first_n
        elif batch_mode == 'sample':
            sample_rate = getattr(self.config, 'claude_sample_rate', 0.2)
            return random.random() < sample_rate
        
        return True
