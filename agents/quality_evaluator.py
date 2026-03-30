"""
Quality Evaluator - Measures how well summaries capture transcript content.

Supports two evaluation methods:
1. Keyword Coverage: Fast, free, frequency-based relevance scoring
2. Claude Evaluation: AI-powered deep analysis of completeness, accuracy, and relevance
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from collections import Counter
from math import log

from config import Configuration, PromptLibrary


class QualityEvaluator:
    """Evaluates the quality of transcript summaries"""
    
    def __init__(self, config: Configuration):
        self.name = "QualityEvaluator"
        self.config = config
        self.client = config.create_bedrock_client()
        self.prompt_library = PromptLibrary()
        
        # Load quality evaluation settings
        self.eval_enabled = getattr(config, 'quality_eval_enabled', True)
        self.eval_method = getattr(config, 'quality_eval_method', 'both')
        self.keyword_min_coverage = getattr(config, 'keyword_min_coverage', 50)
        self.keyword_extract_method = getattr(config, 'keyword_extract_method', 'frequency')
        self.keyword_top_n = getattr(config, 'keyword_top_n', 30)
        self.claude_enabled = getattr(config, 'claude_eval_enabled', True)
    
    def log(self, message: str, level: str = "INFO"):
        """Simple logging method"""
        print(f"[{self.name}] {level}: {message}")
    
    def evaluate(self, transcript: str, summary: str) -> Dict[str, any]:
        """
        Evaluate summary quality against transcript.
        
        Args:
            transcript: Original transcript content
            summary: Generated summary
            
        Returns:
            Dictionary with quality scores and metrics
        """
        if not self.eval_enabled:
            return self._empty_result()
        
        result = {
            'method': self.eval_method,
            'keyword_coverage': None,
            'claude_scores': None,
            'overall_quality': None,
            'meets_threshold': True,
            'warnings': []
        }
        
        # Keyword evaluation (always fast)
        if self.eval_method in ['keyword', 'both']:
            keyword_result = self.evaluate_keyword_coverage(transcript, summary)
            result['keyword_coverage'] = keyword_result['coverage_score']
            
            if keyword_result['coverage_score'] < self.keyword_min_coverage:
                result['meets_threshold'] = False
                result['warnings'].append(
                    f"Low keyword coverage: {keyword_result['coverage_score']:.1f}% "
                    f"(threshold: {self.keyword_min_coverage}%)"
                )
        
        # Claude evaluation (optional, uses API)
        if self.eval_method in ['claude', 'both'] and self.claude_enabled:
            claude_result = self.evaluate_with_claude(transcript, summary)
            if claude_result:
                result['claude_scores'] = claude_result
                
                # Check thresholds
                if claude_result['overall_score'] < getattr(self.config, 'claude_min_overall', 70):
                    result['meets_threshold'] = False
                    result['warnings'].append(
                        f"Low overall quality: {claude_result['overall_score']:.1f}/100"
                    )
        
        # Calculate composite quality score
        result['overall_quality'] = self._calculate_composite_score(result)
        
        return result
    
    def evaluate_keyword_coverage(self, transcript: str, summary: str) -> Dict[str, any]:
        """
        Evaluate summary by measuring keyword coverage.
        
        Args:
            transcript: Original transcript
            summary: Generated summary
            
        Returns:
            Dictionary with coverage score and details
        """
        # Extract important keywords from transcript
        transcript_keywords = self._extract_keywords(transcript, self.keyword_top_n)
        
        # Check which keywords appear in summary
        summary_lower = summary.lower()
        matched_keywords = []
        
        for keyword, score in transcript_keywords:
            # Check if keyword appears in summary (allow partial matches for phrases)
            if keyword in summary_lower:
                matched_keywords.append((keyword, score))
        
        # Calculate coverage score
        if not transcript_keywords:
            coverage_score = 0.0
        else:
            # Weighted by keyword importance
            total_weight = sum(score for _, score in transcript_keywords)
            matched_weight = sum(score for _, score in matched_keywords)
            coverage_score = (matched_weight / total_weight * 100) if total_weight > 0 else 0.0
        
        return {
            'coverage_score': coverage_score,
            'total_keywords': len(transcript_keywords),
            'matched_keywords': len(matched_keywords),
            'top_keywords': [kw for kw, _ in transcript_keywords[:10]],
            'missing_keywords': [kw for kw, _ in transcript_keywords if kw not in [m[0] for m in matched_keywords]][:10]
        }
    
    def _extract_keywords(self, text: str, top_n: int = 30) -> List[Tuple[str, float]]:
        """
        Extract important keywords from text.
        
        Args:
            text: Input text
            top_n: Number of top keywords to return
            
        Returns:
            List of (keyword, score) tuples sorted by importance
        """
        if self.keyword_extract_method == 'tfidf':
            return self._extract_keywords_tfidf(text, top_n)
        else:
            return self._extract_keywords_frequency(text, top_n)
    
    def _extract_keywords_frequency(self, text: str, top_n: int) -> List[Tuple[str, float]]:
        """Extract keywords using frequency analysis"""
        # Clean and tokenize
        text_lower = text.lower()
        
        # Remove common words (simple stopwords)
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'can', 'i', 'you', 'he',
            'she', 'it', 'we', 'they', 'this', 'that', 'these', 'those', 'what',
            'which', 'who', 'when', 'where', 'why', 'how', 'all', 'each', 'every',
            'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
            'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
            'also', 'into', 'about', 'if', 'then', 'there', 'their', 'them'
        }
        
        # Extract words and phrases
        words = re.findall(r'\b[a-z]{3,}\b', text_lower)
        
        # Filter stopwords
        words = [w for w in words if w not in stopwords]
        
        # Count frequency
        word_freq = Counter(words)
        
        # Extract 2-3 word phrases (important for context)
        phrases = re.findall(r'\b[a-z]{3,}(?:\s+[a-z]{3,}){1,2}\b', text_lower)
        phrases = [p for p in phrases if not all(word in stopwords for word in p.split())]
        phrase_freq = Counter(phrases)
        
        # Combine and normalize scores
        all_keywords = {}
        
        # Words
        max_word_freq = max(word_freq.values()) if word_freq else 1
        for word, count in word_freq.most_common(top_n):
            all_keywords[word] = count / max_word_freq
        
        # Phrases (give them bonus weight)
        max_phrase_freq = max(phrase_freq.values()) if phrase_freq else 1
        for phrase, count in phrase_freq.most_common(top_n // 2):
            score = (count / max_phrase_freq) * 1.5  # Bonus for phrases
            if phrase in all_keywords:
                all_keywords[phrase] = max(all_keywords[phrase], score)
            else:
                all_keywords[phrase] = score
        
        # Sort by score
        sorted_keywords = sorted(all_keywords.items(), key=lambda x: x[1], reverse=True)
        return sorted_keywords[:top_n]
    
    def _extract_keywords_tfidf(self, text: str, top_n: int) -> List[Tuple[str, float]]:
        """Extract keywords using TF-IDF (simplified version)"""
        # For simplicity, use frequency-based with length penalty
        # (proper TF-IDF would require a corpus, which we don't have)
        keywords = self._extract_keywords_frequency(text, top_n * 2)
        
        # Apply inverse document frequency approximation
        # Penalize very common words that appear everywhere
        adjusted = []
        for keyword, score in keywords:
            # Penalize short common words more
            length_bonus = min(len(keyword) / 10.0, 1.0)
            adjusted_score = score * length_bonus
            adjusted.append((keyword, adjusted_score))
        
        # Re-sort and return top N
        adjusted.sort(key=lambda x: x[1], reverse=True)
        return adjusted[:top_n]
    
    def evaluate_with_claude(self, transcript: str, summary: str) -> Optional[Dict[str, any]]:
        """
        Evaluate summary using Claude AI.
        
        Args:
            transcript: Original transcript
            summary: Generated summary
            
        Returns:
            Dictionary with quality scores or None if error
        """
        self.log("Evaluating quality with Claude...")
        
        try:
            # Create evaluation prompt
            prompt = self.prompt_library.QUALITY_EVALUATION_PROMPT.format(
                transcript=transcript[:10000],  # Limit transcript size
                summary=summary
            )
            
            # Prepare messages
            messages = [{
                "role": "user",
                "content": [{"text": prompt}]
            }]
            
            # Call Claude API
            response = self.client.converse(
                modelId=self.config.model_id,
                messages=messages,
                inferenceConfig={"temperature": 0.1}  # Low temperature for consistent eval
            )
            
            response_text = response["output"]["message"]["content"][0]["text"]
            
            # Log raw response for debugging
            self.log(f"Raw Claude response (first 300 chars): {response_text[:300]}")
            
            # Parse JSON response
            # Remove markdown code blocks if present
            response_text = re.sub(r'```json\s*|\s*```', '', response_text)
            response_text = response_text.strip()
            
            # Try to extract JSON if it's embedded in other text
            # Look for a JSON object with better pattern
            json_match = re.search(r'\{[\s\S]*?\}(?=\s*$|\s*\n\s*$)', response_text)
            if json_match:
                json_text = json_match.group(0)
                self.log(f"Extracted JSON (first 200 chars): {json_text[:200]}")
            else:
                json_text = response_text
                self.log("Using full response text as JSON")
            
            # Parse JSON
            scores = json.loads(json_text)
            
            # Validate required fields
            required_fields = ['completeness_score', 'accuracy_score', 'relevance_score', 'overall_score']
            missing_fields = [f for f in required_fields if f not in scores]
            if missing_fields:
                self.log(f"Missing required fields in response: {missing_fields}", "ERROR")
                self.log(f"Parsed scores: {scores}", "ERROR")
                return None
            
            self.log(f"Claude evaluation: Overall {scores['overall_score']:.1f}/100")
            return scores
            
        except json.JSONDecodeError as e:
            self.log(f"JSON parsing failed: {str(e)}", "ERROR")
            self.log(f"Full response text: {response_text if 'response_text' in locals() else 'N/A'}", "ERROR")
            return None
        except Exception as e:
            self.log(f"Error during Claude evaluation: {type(e).__name__}: {str(e)}", "ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", "ERROR")
            return None
    
    def _calculate_composite_score(self, result: Dict) -> float:
        """Calculate overall quality score from multiple metrics"""
        scores = []
        weights = []
        
        # Keyword coverage
        if result['keyword_coverage'] is not None:
            scores.append(result['keyword_coverage'])
            weights.append(0.3 if result['claude_scores'] else 1.0)
        
        # Claude scores
        if result['claude_scores']:
            scores.append(result['claude_scores']['overall_score'])
            weights.append(0.7)
        
        if not scores:
            return 0.0
        
        # Weighted average
        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _empty_result(self) -> Dict[str, any]:
        """Return empty result when evaluation is disabled"""
        return {
            'method': 'none',
            'keyword_coverage': None,
            'claude_scores': None,
            'overall_quality': None,
            'meets_threshold': True,
            'warnings': []
        }
