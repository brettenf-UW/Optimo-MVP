import pandas as pd
import numpy as np
from itertools import product
import matplotlib.pyplot as plt
from datetime import datetime
import os
import json
from program_for_tuning import SchoolScheduler

class PenaltyTuner:
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_dir = f'../results/tuning_run_{self.timestamp}'
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Define ranges to test for each penalty
        self.penalty_ranges = {
            'missing_course': [1000, 1200, 1500, 2000],
            'section_overload': [50, 100, 150],
            'medical_career': [600, 800, 1000],
            'heroes_teach': [600, 800, 1000],
            'sports_med': [400, 600, 800],
            'science_prep': [300, 400, 500],
            'sped_overload': [200, 250, 300],
            'balance': [25, 50, 75]
        }
        self.results = []

    def evaluate_penalties(self, penalties):
        """Run one iteration with given penalties"""
        scheduler = SchoolScheduler(penalties)
        conflicts = scheduler.run()
        
        # Score the result (lower is better)
        score = (
            len(conflicts['missing_courses']) * 1000 +
            len(conflicts['teacher_conflicts']) * 800 +
            len(conflicts['special_course_issues']) * 600 +
            len(conflicts['overloaded_sections']) * 100
        )
        
        result = {
            'penalties': penalties,
            'score': score,
            'missing_courses': len(conflicts['missing_courses']),
            'teacher_conflicts': len(conflicts['teacher_conflicts']),
            'special_course_issues': len(conflicts['special_course_issues']),
            'overloaded_sections': len(conflicts['overloaded_sections'])
        }
        
        # Save if this is the best result so far
        if not self.results or score < min(r['score'] for r in self.results):
            self.save_best_result(result, scheduler)
            
        return result

    def save_best_result(self, result, scheduler):
        """Save the current best configuration"""
        best_dir = os.path.join(self.results_dir, 'best_configuration')
        os.makedirs(best_dir, exist_ok=True)
        
        # Save penalties
        with open(os.path.join(best_dir, 'penalties.json'), 'w') as f:
            json.dump(result['penalties'], f, indent=4)
        
        # Save metrics
        with open(os.path.join(best_dir, 'metrics.json'), 'w') as f:
            json.dump({k: v for k, v in result.items() if k != 'penalties'}, f, indent=4)
        
        # Save schedules
        scheduler.save_results(best_dir)

    def run_tuning(self):
        """Test different penalty combinations"""
        print(f"Starting penalty tuning... Results will be saved in {self.results_dir}")
        
        # Generate combinations
        keys = list(self.penalty_ranges.keys())
        values = list(self.penalty_ranges.values())
        combinations = list(product(*values))
        
        total = len(combinations)
        print(f"Testing {total} penalty combinations...")
        
        for i, vals in enumerate(combinations):
            penalties = dict(zip(keys, vals))
            result = self.evaluate_penalties(penalties)
            self.results.append(result)
            
            if (i + 1) % 5 == 0:
                print(f"Progress: {i+1}/{total} combinations tested")
        
        self.create_visualizations()
        self.summarize_results()

    def create_visualizations(self):
        """Create analysis plots"""
        results_df = pd.DataFrame(self.results)
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        metrics = ['missing_courses', 'teacher_conflicts', 
                  'special_course_issues', 'overloaded_sections']
        
        for ax, metric in zip(axes.flat, metrics):
            ax.scatter(results_df['penalties'].apply(lambda x: x['missing_course']), 
                      results_df[metric])
            ax.set_xlabel('Missing Course Penalty')
            ax.set_ylabel(metric.replace('_', ' ').title())
            ax.grid(True)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.results_dir, 'penalty_analysis.png'))
        plt.close()

    def summarize_results(self):
        """Output summary of findings"""
        results_df = pd.DataFrame(self.results)
        best_result = results_df.loc[results_df['score'].idxmin()]
        
        summary = {
            'best_penalties': best_result['penalties'],
            'metrics': {
                'score': best_result['score'],
                'missing_courses': best_result['missing_courses'],
                'teacher_conflicts': best_result['teacher_conflicts'],
                'special_course_issues': best_result['special_course_issues'],
                'overloaded_sections': best_result['overloaded_sections']
            }
        }
        
        with open(os.path.join(self.results_dir, 'tuning_summary.json'), 'w') as f:
            json.dump(summary, f, indent=4)

def main():
    tuner = PenaltyTuner()
    tuner.run_tuning()

if __name__ == "__main__":
    main()
