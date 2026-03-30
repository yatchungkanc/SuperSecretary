"""
Metrics collection and reporting for transcript processing.
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import timedelta


@dataclass
class TranscriptMetrics:
    """Metrics for a single transcript processing"""
    file_name: str
    processing_time: float  # seconds
    word_count: int
    action_items_count: int
    issues_count: int
    success: bool
    error_message: Optional[str] = None
    
    # Quality metrics
    quality_score: Optional[float] = None  # Overall quality 0-100
    keyword_coverage: Optional[float] = None  # Keyword coverage 0-100
    completeness_score: Optional[float] = None  # Claude completeness 0-100
    accuracy_score: Optional[float] = None  # Claude accuracy 0-100
    relevance_score: Optional[float] = None  # Claude relevance 0-100
    quality_warnings: List[str] = field(default_factory=list)  # Quality issues
    
    def to_dict(self) -> Dict:
        """Convert metrics to dictionary"""
        result = {
            'file_name': self.file_name,
            'processing_time': f"{self.processing_time:.2f}s",
            'word_count': self.word_count,
            'action_items': self.action_items_count,
            'issues': self.issues_count,
            'success': self.success,
            'error': self.error_message
        }
        
        # Add quality metrics if available
        if self.quality_score is not None:
            result['quality_score'] = f"{self.quality_score:.1f}/100"
        if self.keyword_coverage is not None:
            result['keyword_coverage'] = f"{self.keyword_coverage:.1f}%"
        if self.completeness_score is not None:
            result['completeness'] = f"{self.completeness_score:.1f}/100"
        if self.accuracy_score is not None:
            result['accuracy'] = f"{self.accuracy_score:.1f}/100"
        if self.relevance_score is not None:
            result['relevance'] = f"{self.relevance_score:.1f}/100"
        if self.quality_warnings:
            result['quality_warnings'] = self.quality_warnings
        
        return result


@dataclass
class BatchMetrics:
    """Aggregated metrics for batch processing"""
    total_files: int
    successful_files: int
    failed_files: int
    total_time: float  # seconds
    average_time: float  # seconds
    total_words: int
    total_action_items: int
    total_issues: int
    individual_metrics: List[TranscriptMetrics] = field(default_factory=list)
    
    # Quality metrics (averages across successful files)
    avg_quality_score: Optional[float] = None
    avg_keyword_coverage: Optional[float] = None
    avg_completeness: Optional[float] = None
    avg_accuracy: Optional[float] = None
    avg_relevance: Optional[float] = None
    files_below_threshold: int = 0
    quality_warnings_count: int = 0
    
    def to_dict(self) -> Dict:
        """Convert batch metrics to dictionary"""
        return {
            'summary': {
                'total_files': self.total_files,
                'successful': self.successful_files,
                'failed': self.failed_files,
                'success_rate': f"{(self.successful_files/self.total_files*100) if self.total_files > 0 else 0:.1f}%",
                'total_time': self._format_time(self.total_time),
                'average_time_per_file': self._format_time(self.average_time),
                'total_words_generated': self.total_words,
                'total_action_items': self.total_action_items,
                'total_issues': self.total_issues
            },
            'individual_files': [m.to_dict() for m in self.individual_metrics]
        }
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format time duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.2f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours}h {minutes}m {secs:.1f}s"
    
    def print_summary(self):
        """Print formatted metrics summary"""
        print("\n" + "="*70)
        print("PROCESSING METRICS SUMMARY")
        print("="*70)
        
        # Overall statistics
        print(f"\n📊 Overall Statistics:")
        print(f"  Total Files:        {self.total_files}")
        print(f"  ✓ Successful:       {self.successful_files}")
        print(f"  ✗ Failed:           {self.failed_files}")
        success_rate = (self.successful_files/self.total_files*100) if self.total_files > 0 else 0
        print(f"  Success Rate:       {success_rate:.1f}%")
        
        # Time statistics
        print(f"\n⏱️  Time Statistics:")
        print(f"  Total Time:         {self._format_time(self.total_time)}")
        print(f"  Average per File:   {self._format_time(self.average_time)}")
        
        if self.successful_files > 0:
            # Calculate stats only for successful files
            successful_metrics = [m for m in self.individual_metrics if m.success]
            if successful_metrics:
                min_time = min(m.processing_time for m in successful_metrics)
                max_time = max(m.processing_time for m in successful_metrics)
                print(f"  Fastest:            {self._format_time(min_time)}")
                print(f"  Slowest:            {self._format_time(max_time)}")
        
        # Output quality statistics
        print(f"\n📝 Output Quality:")
        print(f"  Total Words:        {self.total_words:,}")
        print(f"  Action Items:       {self.total_action_items}")
        print(f"  Issues Discussed:   {self.total_issues}")
        
        if self.successful_files > 0:
            print(f"  Avg Words/File:     {self.total_words // self.successful_files:,}")
            print(f"  Avg Actions/File:   {self.total_action_items / self.successful_files:.1f}")
            print(f"  Avg Issues/File:    {self.total_issues / self.successful_files:.1f}")
        
        # Quality evaluation statistics (if available)
        has_quality = any([
            self.avg_quality_score is not None,
            self.avg_keyword_coverage is not None,
            self.avg_completeness is not None
        ])
        
        if has_quality and self.successful_files > 0:
            print(f"\n🎯 Summary Quality Metrics:")
            
            if self.avg_quality_score is not None:
                print(f"  Overall Quality:    {self.avg_quality_score:.1f}/100")
            
            if self.avg_keyword_coverage is not None:
                print(f"  Keyword Coverage:   {self.avg_keyword_coverage:.1f}%")
            
            if self.avg_completeness is not None:
                print(f"  Completeness:       {self.avg_completeness:.1f}/100")
            
            if self.avg_accuracy is not None:
                print(f"  Accuracy:           {self.avg_accuracy:.1f}/100")
            
            if self.avg_relevance is not None:
                print(f"  Relevance:          {self.avg_relevance:.1f}/100")
            
            if self.files_below_threshold > 0:
                print(f"  ⚠️  Below Threshold:  {self.files_below_threshold} file(s)")
            
            if self.quality_warnings_count > 0:
                print(f"  ⚠️  Quality Warnings: {self.quality_warnings_count}")
        
        # Individual file details
        if self.individual_metrics:
            print(f"\n📄 Individual File Details:")
            
            # Adjust header based on whether quality metrics are present
            if has_quality:
                print(f"  {'File Name':<35} {'Time':<12} {'Words':<8} {'Quality':<10} {'Status'}")
                print(f"  {'-'*35} {'-'*12} {'-'*8} {'-'*10} {'-'*10}")
            else:
                print(f"  {'File Name':<40} {'Time':<12} {'Words':<8} {'Actions':<8} {'Status'}")
                print(f"  {'-'*40} {'-'*12} {'-'*8} {'-'*8} {'-'*10}")
            
            for m in self.individual_metrics:
                status = "✓ Success" if m.success else "✗ Failed"
                time_str = self._format_time(m.processing_time)
                
                if has_quality and m.quality_score is not None:
                    quality_str = f"{m.quality_score:.1f}/100"
                    print(f"  {m.file_name:<35} {time_str:<12} {m.word_count:<8} {quality_str:<10} {status}")
                else:
                    print(f"  {m.file_name:<40} {time_str:<12} {m.word_count:<8} {m.action_items_count:<8} {status}")
                
                if not m.success and m.error_message:
                    print(f"    Error: {m.error_message}")
                
                if m.quality_warnings:
                    for warning in m.quality_warnings:
                        print(f"    ⚠️  {warning}")
        
        print("="*70 + "\n")


class MetricsCollector:
    """Collects and analyzes metrics during processing"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.metrics: List[TranscriptMetrics] = []
    
    def start_batch(self):
        """Start timing batch processing"""
        self.start_time = time.time()
    
    def end_batch(self):
        """End timing batch processing"""
        self.end_time = time.time()
    
    def add_metric(self, metric: TranscriptMetrics):
        """Add a transcript metric"""
        self.metrics.append(metric)
    
    def get_batch_metrics(self) -> BatchMetrics:
        """Calculate and return batch-level metrics"""
        if not self.metrics:
            return BatchMetrics(
                total_files=0,
                successful_files=0,
                failed_files=0,
                total_time=0,
                average_time=0,
                total_words=0,
                total_action_items=0,
                total_issues=0
            )
        
        successful = [m for m in self.metrics if m.success]
        failed = [m for m in self.metrics if not m.success]
        
        total_time = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        # Calculate quality metrics (only for successful files with quality data)
        quality_metrics = [m for m in successful if m.quality_score is not None]
        
        avg_quality = None
        avg_keyword_cov = None
        avg_complete = None
        avg_accuracy = None
        avg_relevance = None
        below_threshold = 0
        warnings_count = 0
        
        if quality_metrics:
            avg_quality = sum(m.quality_score for m in quality_metrics) / len(quality_metrics)
            
            # Keyword coverage
            kw_metrics = [m for m in quality_metrics if m.keyword_coverage is not None]
            if kw_metrics:
                avg_keyword_cov = sum(m.keyword_coverage for m in kw_metrics) / len(kw_metrics)
            
            # Claude scores
            claude_metrics = [m for m in quality_metrics if m.completeness_score is not None]
            if claude_metrics:
                avg_complete = sum(m.completeness_score for m in claude_metrics) / len(claude_metrics)
                avg_accuracy = sum(m.accuracy_score for m in claude_metrics) / len(claude_metrics)
                avg_relevance = sum(m.relevance_score for m in claude_metrics) / len(claude_metrics)
            
            # Count files below threshold
            below_threshold = sum(1 for m in quality_metrics if m.quality_warnings)
            warnings_count = sum(len(m.quality_warnings) for m in quality_metrics)
        
        return BatchMetrics(
            total_files=len(self.metrics),
            successful_files=len(successful),
            failed_files=len(failed),
            total_time=total_time,
            average_time=sum(m.processing_time for m in self.metrics) / len(self.metrics),
            total_words=sum(m.word_count for m in successful),
            total_action_items=sum(m.action_items_count for m in successful),
            total_issues=sum(m.issues_count for m in successful),
            individual_metrics=self.metrics,
            avg_quality_score=avg_quality,
            avg_keyword_coverage=avg_keyword_cov,
            avg_completeness=avg_complete,
            avg_accuracy=avg_accuracy,
            avg_relevance=avg_relevance,
            files_below_threshold=below_threshold,
            quality_warnings_count=warnings_count
        )
    
    @staticmethod
    def analyze_summary(summary: str) -> Dict[str, int]:
        """
        Analyze summary content for quality metrics.
        
        Returns:
            Dictionary with word_count, action_items_count, issues_count
        """
        if not summary:
            return {'word_count': 0, 'action_items_count': 0, 'issues_count': 0}
        
        # Word count
        word_count = len(summary.split())
        
        # Count action items (lines in action items section)
        action_items_count = 0
        issues_count = 0
        
        # Simple heuristic: count bullet points or numbered items in relevant sections
        lines = summary.split('\n')
        in_action_section = False
        in_issues_section = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Detect section headers
            if 'action item' in line_lower:
                in_action_section = True
                in_issues_section = False
                continue
            elif 'issues discussed' in line_lower or 'discussion' in line_lower:
                in_issues_section = True
                in_action_section = False
                continue
            elif line_lower.startswith('#') or (line_lower and line_lower[0].isupper() and ':' in line_lower):
                # New section header
                in_action_section = False
                in_issues_section = False
            
            # Count items in sections
            if line.strip():
                if in_action_section and ('|' in line or line.strip().startswith(('-', '*', '•'))):
                    action_items_count += 1
                elif in_issues_section and line.strip().startswith(('-', '*', '•')):
                    issues_count += 1
        
        return {
            'word_count': word_count,
            'action_items_count': max(0, action_items_count - 1),  # Subtract header row if table
            'issues_count': issues_count
        }
