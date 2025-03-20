#!/usr/bin/env python3
"""
Dashboard generator for Place2Polygon performance results.

This script generates an HTML dashboard from performance evaluation data,
visualizing the results of normal vs Gemini search modes with charts and tables.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

def generate_html_header(file_name: str, timestamp: str) -> str:
    """Generate the HTML header section."""
    try:
        date_obj = datetime.fromisoformat(timestamp)
        formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
    except:
        formatted_date = timestamp
        
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Place2Polygon Performance Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        header {{
            margin-bottom: 30px;
            border-bottom: 1px solid #eee;
            padding-bottom: 15px;
        }}
        h1 {{
            color: #2c3e50;
            margin: 0;
            font-size: 28px;
        }}
        .metadata {{
            color: #7f8c8d;
            font-size: 14px;
            margin-top: 8px;
        }}
        .charts-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .chart-box {{
            flex: 1;
            min-width: 300px;
            background-color: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.05);
        }}
        .chart-title {{
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 10px;
            color: #34495e;
        }}
        .stats-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        .stats-table th, .stats-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
            text-align: left;
        }}
        .stats-table th {{
            background-color: #f8f9fa;
            font-weight: 600;
            color: #2c3e50;
        }}
        .stats-table tr:last-child td {{
            border-bottom: none;
        }}
        .positive {{
            color: #27ae60;
        }}
        .negative {{
            color: #e74c3c;
        }}
        .summary {{
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-top: 30px;
        }}
        .summary h3 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .summary ul {{
            padding-left: 20px;
        }}
        .summary li {{
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Place2Polygon Performance Dashboard</h1>
            <div class="metadata">
                File: <strong>{file_name}</strong> | Generated: <strong>{formatted_date}</strong>
            </div>
        </header>
"""

def generate_chart_containers() -> str:
    """Generate the chart container HTML."""
    return """
        <div class="charts-container">
            <div class="chart-box">
                <div class="chart-title">Boundary Types Comparison</div>
                <canvas id="boundaryTypesChart"></canvas>
            </div>
            <div class="chart-box">
                <div class="chart-title">Match Rate Comparison</div>
                <canvas id="matchRateChart"></canvas>
            </div>
        </div>
        
        <div class="chart-box">
            <div class="chart-title">Processing Time</div>
            <canvas id="timeChart"></canvas>
        </div>
"""

def generate_stats_table(normal: Dict[str, Any], gemini: Dict[str, Any], comparison: Dict[str, Any]) -> str:
    """Generate the statistics table HTML."""
    # Calculate metrics
    normal_match_rate = f"{normal['matched_locations']/normal['total_locations']*100:.1f}%"
    gemini_match_rate = f"{gemini['matched_locations']/gemini['total_locations']*100:.1f}%"
    match_rate_diff_class = "positive" if comparison['match_rate_diff'] > 0 else "negative"
    match_rate_diff = f"{comparison['match_rate_diff']:+.1f}%"
    
    normal_polygon_rate = f"{normal['polygon_boundaries']/normal['total_locations']*100:.1f}%"
    gemini_polygon_rate = f"{gemini['polygon_boundaries']/gemini['total_locations']*100:.1f}%"
    polygon_rate_diff_class = "positive" if comparison['polygon_rate_diff'] > 0 else "negative"
    polygon_rate_diff = f"{comparison['polygon_rate_diff']:+.1f}%"
    
    polygon_diff_class = "positive" if gemini['polygon_boundaries'] > normal['polygon_boundaries'] else "negative"
    polygon_diff = f"{gemini['polygon_boundaries'] - normal['polygon_boundaries']:+d}"
    
    point_diff_class = "positive" if gemini['point_boundaries'] < normal['point_boundaries'] else "negative"
    point_diff = f"{gemini['point_boundaries'] - normal['point_boundaries']:+d}"
    
    no_boundary_diff_class = "positive" if gemini['no_boundaries'] < normal['no_boundaries'] else "negative"
    no_boundary_diff = f"{gemini['no_boundaries'] - normal['no_boundaries']:+d}"
    
    time_diff_class = "positive" if comparison['time_diff'] < 0 else "negative"
    time_diff = f"{comparison['time_diff']:+.2f}s ({comparison['time_diff_percent']:+.1f}%)"
    
    return f"""
        <h2>Performance Statistics</h2>
        <table class="stats-table">
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Normal</th>
                    <th>Gemini</th>
                    <th>Difference</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Match Rate</td>
                    <td>{normal_match_rate}</td>
                    <td>{gemini_match_rate}</td>
                    <td class="{match_rate_diff_class}">{match_rate_diff}</td>
                </tr>
                <tr>
                    <td>Polygon Rate</td>
                    <td>{normal_polygon_rate}</td>
                    <td>{gemini_polygon_rate}</td>
                    <td class="{polygon_rate_diff_class}">{polygon_rate_diff}</td>
                </tr>
                <tr>
                    <td>Polygon Boundaries</td>
                    <td>{normal['polygon_boundaries']}</td>
                    <td>{gemini['polygon_boundaries']}</td>
                    <td class="{polygon_diff_class}">{polygon_diff}</td>
                </tr>
                <tr>
                    <td>Point Boundaries</td>
                    <td>{normal['point_boundaries']}</td>
                    <td>{gemini['point_boundaries']}</td>
                    <td class="{point_diff_class}">{point_diff}</td>
                </tr>
                <tr>
                    <td>No Boundaries</td>
                    <td>{normal['no_boundaries']}</td>
                    <td>{gemini['no_boundaries']}</td>
                    <td class="{no_boundary_diff_class}">{no_boundary_diff}</td>
                </tr>
                <tr>
                    <td>Processing Time</td>
                    <td>{normal['processing_time']:.2f}s</td>
                    <td>{gemini['processing_time']:.2f}s</td>
                    <td class="{time_diff_class}">{time_diff}</td>
                </tr>
            </tbody>
        </table>
"""

def generate_summary(performance_data: Dict[str, Any]) -> str:
    """Generate the summary section HTML."""
    normal = performance_data["normal"]
    gemini = performance_data["gemini"]
    comparison = performance_data["comparison"]
    total_locations = performance_data["total_locations"]
    
    # Create summary bullet points
    match_rate_summary = ""
    if comparison['match_rate_diff'] > 0:
        match_rate_summary = f'<li class="positive">✓ Gemini found {abs(comparison["match_rate_diff"]):.1f}% more matches</li>'
    else:
        match_rate_summary = f'<li class="negative">✗ Gemini found {abs(comparison["match_rate_diff"]):.1f}% fewer matches</li>'
    
    polygon_rate_summary = ""
    if comparison['polygon_rate_diff'] > 0:
        polygon_rate_summary = f'<li class="positive">✓ Gemini found {abs(comparison["polygon_rate_diff"]):.1f}% more polygon boundaries</li>'
    else:
        polygon_rate_summary = f'<li class="negative">✗ Gemini found {abs(comparison["polygon_rate_diff"]):.1f}% fewer polygon boundaries</li>'
    
    time_summary = ""
    if comparison['time_diff'] < 0:
        time_summary = f'<li class="positive">✓ Gemini was {abs(comparison["time_diff"]):.2f}s faster</li>'
    else:
        time_summary = f'<li class="negative">✗ Gemini was {abs(comparison["time_diff"]):.2f}s slower</li>'
    
    return f"""
        <div class="summary">
            <h3>Analysis Summary</h3>
            <ul>
                {match_rate_summary}
                {polygon_rate_summary}
                {time_summary}
                <li>Total locations processed: {total_locations}</li>
            </ul>
            
            <h3>Observations</h3>
            <p>
                In this test, the standard non-Gemini search found more boundaries overall. This is likely because:
            </p>
            <ul>
                <li>The Gemini structured output feature wasn't working due to library version issues</li>
                <li>Some locations with possessive forms (e.g., "Las Vegas' Strip") caused validation failures in Gemini mode</li>
                <li>The additional validation in Gemini mode rejected some borderline matches that normal mode accepted</li>
            </ul>
            <p>
                Recommendations:
            </p>
            <ul>
                <li>Update the google-generativeai library to support structured output</li>
                <li>Add preprocessing for possessive forms</li>
                <li>Fine-tune the validation thresholds in Gemini mode</li>
            </ul>
        </div>
    </div>
"""

def generate_javascript(normal: Dict[str, Any], gemini: Dict[str, Any]) -> str:
    """Generate the JavaScript for charts."""
    # Prepare chart data
    normal_polygon = str(normal['polygon_boundaries'])
    gemini_polygon = str(gemini['polygon_boundaries'])
    normal_point = str(normal['point_boundaries'])
    gemini_point = str(gemini['point_boundaries'])
    normal_no = str(normal['no_boundaries'])
    gemini_no = str(gemini['no_boundaries'])
    
    normal_matched = str(normal['matched_locations'])
    normal_not_matched = str(normal['total_locations'] - normal['matched_locations'])
    gemini_matched = str(gemini['matched_locations'])
    gemini_not_matched = str(gemini['total_locations'] - gemini['matched_locations'])
    
    normal_time = str(normal['processing_time'])
    gemini_time = str(gemini['processing_time'])
    
    return f"""
    <script>
        // Chart configurations
        const ctx1 = document.getElementById('boundaryTypesChart').getContext('2d');
        const boundaryTypesChart = new Chart(ctx1, {{
            type: 'bar',
            data: {{
                labels: ['Normal', 'Gemini'],
                datasets: [
                    {{
                        label: 'Polygon Boundaries',
                        data: [{normal_polygon}, {gemini_polygon}],
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    }},
                    {{
                        label: 'Point Boundaries',
                        data: [{normal_point}, {gemini_point}],
                        backgroundColor: 'rgba(255, 206, 86, 0.7)',
                    }},
                    {{
                        label: 'No Boundaries',
                        data: [{normal_no}, {gemini_no}],
                        backgroundColor: 'rgba(255, 99, 132, 0.7)',
                    }}
                ]
            }},
            options: {{
                responsive: true,
                scales: {{
                    x: {{
                        stacked: true,
                    }},
                    y: {{
                        stacked: true,
                        beginAtZero: true
                    }}
                }}
            }}
        }});
        
        const ctx2 = document.getElementById('matchRateChart').getContext('2d');
        const matchRateChart = new Chart(ctx2, {{
            type: 'doughnut',
            data: {{
                labels: ['Matched (Normal)', 'Not Matched (Normal)', 'Matched (Gemini)', 'Not Matched (Gemini)'],
                datasets: [{{
                    data: [
                        {normal_matched}, 
                        {normal_not_matched},
                        {gemini_matched},
                        {gemini_not_matched}
                    ],
                    backgroundColor: [
                        'rgba(54, 162, 235, 0.7)',
                        'rgba(255, 99, 132, 0.7)',
                        'rgba(75, 192, 192, 0.7)',
                        'rgba(255, 159, 64, 0.7)'
                    ]
                }}]
            }},
            options: {{
                responsive: true
            }}
        }});
        
        const ctx3 = document.getElementById('timeChart').getContext('2d');
        const timeChart = new Chart(ctx3, {{
            type: 'bar',
            data: {{
                labels: ['Processing Time (seconds)'],
                datasets: [
                    {{
                        label: 'Normal',
                        data: [{normal_time}],
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    }},
                    {{
                        label: 'Gemini',
                        data: [{gemini_time}],
                        backgroundColor: 'rgba(75, 192, 192, 0.7)',
                    }}
                ]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{
                        beginAtZero: true
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

def generate_html_report(performance_data: Dict[str, Any], output_file: str):
    """Generate an HTML dashboard from performance data."""
    normal = performance_data["normal"]
    gemini = performance_data["gemini"]
    comparison = performance_data["comparison"]
    timestamp = performance_data["timestamp"]
    file_name = os.path.basename(performance_data["file"])
    
    # Build HTML content by concatenating the different sections
    html_content = (
        generate_html_header(file_name, timestamp) +
        generate_chart_containers() +
        generate_stats_table(normal, gemini, comparison) +
        generate_summary(performance_data) +
        generate_javascript(normal, gemini)
    )
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Dashboard generated at: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Generate HTML dashboard from performance data")
    parser.add_argument("input_file", help="Path to the performance JSON file")
    parser.add_argument("--output", "-o", help="Path to save the HTML dashboard", 
                      default="performance_dashboard.html")
    args = parser.parse_args()
    
    # Load performance data
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            performance_data = json.load(f)
    except Exception as e:
        print(f"Error loading performance data: {str(e)}")
        sys.exit(1)
    
    # Generate report
    generate_html_report(performance_data, args.output)

if __name__ == "__main__":
    main() 