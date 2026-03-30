#!/usr/bin/env python3
# Quick script to add missing method to coordinator_agent.py

filepath = '/Users/yatchungkanc/Documents/TechnicaTraining/ClaudewithAmazonBedrock/agents/coordinator_agent.py'

# Read file
with open(filepath, 'r') as f:
    content = f.read()

# Check if method exists
if 'def _should_evaluate_quality' not in content:
    # Add method at the end
    method_code = '''
    
    def _should_evaluate_quality(self) -> bool:
        """Determine if quality evaluation should run for current file in batch."""
        if not self.config.quality_eval_enabled:
            return False
        if not self.config.claude_eval_enabled:
            return True
        batch_mode = self.config.claude_batch_mode
        if batch_mode == "all":
            return True
        elif batch_mode == "first":
            return self.files_evaluated < self.config.claude_first_n
        elif batch_mode == "sample":
            return random.random() < self.config.claude_sample_rate
        return True
'''
    
    with open(filepath, 'a') as f:
        f.write(method_code)
    
    print("✓ Added _should_evaluate_quality method")
else:
    print("✓ Method already exists")
