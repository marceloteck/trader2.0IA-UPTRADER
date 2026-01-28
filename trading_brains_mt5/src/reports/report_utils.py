"""
Report utilities: CSV, JSON, basic charts.
"""

from __future__ import annotations

import json
import csv
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


logger = logging.getLogger("trading_brains.reports")


class ReportGenerator:
    """Generate reports in multiple formats."""
    
    def __init__(self, output_dir: str):
        """Initialize reporter."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save_json(self, filename: str, data: Dict[str, Any]) -> Path:
        """Save report as JSON."""
        output_file = self.output_dir / filename
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved JSON report: {output_file}")
        return output_file
    
    def save_csv(self, filename: str, headers: List[str], rows: List[List[Any]]) -> Path:
        """Save report as CSV."""
        output_file = self.output_dir / filename
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        logger.info(f"Saved CSV report: {output_file}")
        return output_file
    
    def save_text(self, filename: str, content: str) -> Path:
        """Save report as text."""
        output_file = self.output_dir / filename
        with open(output_file, 'w') as f:
            f.write(content)
        logger.info(f"Saved text report: {output_file}")
        return output_file
    
    def simple_line_chart(
        self, 
        title: str, 
        points: List[tuple],  # (x_label, y_value)
        width: int = 80,
        height: int = 20
    ) -> str:
        """
        Generate simple ASCII line chart.
        
        Returns chart as string.
        """
        if not points:
            return "No data"
        
        values = [p[1] for p in points]
        min_val = min(values)
        max_val = max(values)
        
        if min_val == max_val:
            max_val = min_val + 1
        
        chart = [title]
        chart.append("")
        
        # Plot points
        for row in range(height, 0, -1):
            line = ""
            threshold = min_val + (max_val - min_val) * row / height
            
            for val in values:
                line += "█" if val >= threshold else " "
            
            chart.append(line)
        
        # X axis
        chart.append("-" * len(values))
        
        # Labels (sample)
        labels = []
        step = max(1, len(points) // 10)
        for i in range(0, len(points), step):
            labels.append(points[i][0])
        
        return "\n".join(chart) + "\n\n" + f"Min: {min_val:.2f}  Max: {max_val:.2f}"
