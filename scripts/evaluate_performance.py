#!/usr/bin/env python3
"""
Evaluation script for Place2Polygon performance.

This script processes sample text files to compare the effectiveness of:
1. Normal search mode (without Gemini)
2. Gemini-powered search mode

It generates statistics on match rates, boundary quality, and performance.
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Add the src directory to the path so we can import place2polygon
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import place2polygon
from place2polygon.core.location_extractor import LocationExtractor
from place2polygon.core.nominatim_client import NominatimClient
from place2polygon.gemini.orchestrator import GeminiOrchestrator, default_orchestrator
from place2polygon.core.boundary_selector import select_best_boundary

def process_file(file_path: str, use_gemini: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Process a file and return the extracted locations with their boundaries."""
    print(f"\nProcessing {file_path} with {'Gemini' if use_gemini else 'Normal'} mode...")
    
    # Start timing
    start_time = time.time()
    
    # Extract locations
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    extractor = LocationExtractor()
    locations = extractor.extract_locations(text)
    
    # Find boundaries
    if use_gemini and default_orchestrator:
        client = default_orchestrator
        print(f"Using Gemini orchestration for {len(locations)} locations")
    else:
        client = NominatimClient()
        print(f"Using Normal mode for {len(locations)} locations")
    
    locations_with_boundaries = []
    
    for location in locations:
        name = location["name"]
        entity_type = location.get("type", "").lower()
        print(f"  Finding boundary for {name} ({entity_type})")
        
        try:
            result = None
            
            # Use different search methods based on mode
            if use_gemini and default_orchestrator and hasattr(client, "orchestrate_search"):
                result = client.orchestrate_search(name, location_type=entity_type)
            else:
                results = client.search(name, location_type=entity_type)
                # Get the first result if there are any
                result = results[0] if results else None
            
            if result:
                # Store the result with the location
                location["boundary"] = result
                locations_with_boundaries.append(location)
                
                # Determine boundary quality
                quality = "polygon" if "geojson" in result and result["geojson"]["type"] in ["Polygon", "MultiPolygon"] else "point"
                print(f"    ✓ Found {quality} boundary")
            else:
                print(f"    ✗ No boundary found")
                location["boundary"] = None
                locations_with_boundaries.append(location)
        except Exception as e:
            print(f"    ✗ Error: {str(e)}")
            location["boundary"] = None
            locations_with_boundaries.append(location)
    
    # Calculate statistics
    end_time = time.time()
    
    stats = {
        "file": file_path,
        "mode": "Gemini" if use_gemini else "Normal",
        "total_locations": len(locations),
        "matched_locations": sum(1 for loc in locations_with_boundaries if loc.get("boundary")),
        "polygon_boundaries": sum(1 for loc in locations_with_boundaries
                              if loc.get("boundary") and "geojson" in loc["boundary"] 
                              and loc["boundary"]["geojson"]["type"] in ["Polygon", "MultiPolygon"]),
        "point_boundaries": sum(1 for loc in locations_with_boundaries
                             if loc.get("boundary") and ("geojson" not in loc["boundary"] 
                             or loc["boundary"]["geojson"]["type"] not in ["Polygon", "MultiPolygon"])),
        "no_boundaries": sum(1 for loc in locations_with_boundaries if not loc.get("boundary")),
        "processing_time": end_time - start_time,
    }
    
    return locations_with_boundaries, stats

def generate_report(stats_normal: Dict[str, Any], stats_gemini: Dict[str, Any], output_file: str = None):
    """Generate a report comparing normal and Gemini mode performance."""
    # Combine stats for report
    if not stats_gemini:
        print("\n📊 PERFORMANCE REPORT (Normal mode only):")
        print(f"{'=' * 60}")
        print(f"File: {stats_normal['file']}")
        print(f"Total locations: {stats_normal['total_locations']}")
        print(f"Match rate: {stats_normal['matched_locations']/stats_normal['total_locations']*100:.1f}%")
        print(f"Polygon boundaries: {stats_normal['polygon_boundaries']} ({stats_normal['polygon_boundaries']/stats_normal['total_locations']*100:.1f}%)")
        print(f"Point boundaries: {stats_normal['point_boundaries']}")
        print(f"No boundaries: {stats_normal['no_boundaries']}")
        print(f"Processing time: {stats_normal['processing_time']:.2f} seconds")
        return
    
    # Full comparison report
    print("\n📊 PERFORMANCE COMPARISON REPORT:")
    print(f"{'=' * 60}")
    print(f"File: {stats_normal['file']}")
    print(f"Total locations: {stats_normal['total_locations']}")
    print(f"{'=' * 60}")
    print(f"{'Metric':<20} {'Normal':<15} {'Gemini':<15} {'Difference':<15}")
    print(f"{'-' * 60}")
    
    # Match rate
    normal_match_rate = stats_normal['matched_locations'] / stats_normal['total_locations'] * 100
    gemini_match_rate = stats_gemini['matched_locations'] / stats_gemini['total_locations'] * 100
    match_diff = gemini_match_rate - normal_match_rate
    print(f"{'Match rate':<20} {normal_match_rate:.1f}% {gemini_match_rate:.1f}% {match_diff:+.1f}%")
    
    # Polygon rate
    normal_polygon_rate = stats_normal['polygon_boundaries'] / stats_normal['total_locations'] * 100
    gemini_polygon_rate = stats_gemini['polygon_boundaries'] / stats_gemini['total_locations'] * 100
    polygon_diff = gemini_polygon_rate - normal_polygon_rate
    print(f"{'Polygon rate':<20} {normal_polygon_rate:.1f}% {gemini_polygon_rate:.1f}% {polygon_diff:+.1f}%")
    
    # Raw counts
    print(f"{'Polygon boundaries':<20} {stats_normal['polygon_boundaries']:<15} {stats_gemini['polygon_boundaries']:<15} {stats_gemini['polygon_boundaries'] - stats_normal['polygon_boundaries']:+d}")
    print(f"{'Point boundaries':<20} {stats_normal['point_boundaries']:<15} {stats_gemini['point_boundaries']:<15} {stats_gemini['point_boundaries'] - stats_normal['point_boundaries']:+d}")
    print(f"{'No boundaries':<20} {stats_normal['no_boundaries']:<15} {stats_gemini['no_boundaries']:<15} {stats_gemini['no_boundaries'] - stats_normal['no_boundaries']:+d}")
    
    # Time comparison
    time_diff = stats_gemini['processing_time'] - stats_normal['processing_time']
    time_diff_percent = (time_diff / stats_normal['processing_time']) * 100
    print(f"{'Processing time':<20} {stats_normal['processing_time']:.2f}s {stats_gemini['processing_time']:.2f}s {time_diff:+.2f}s ({time_diff_percent:+.1f}%)")
    
    # Summary judgment
    print(f"\n💡 SUMMARY:")
    if gemini_match_rate > normal_match_rate:
        print(f"✓ Gemini found {match_diff:.1f}% more matches")
    else:
        print(f"✗ Gemini found {abs(match_diff):.1f}% fewer matches")
    
    if gemini_polygon_rate > normal_polygon_rate:
        print(f"✓ Gemini found {polygon_diff:.1f}% more polygon boundaries")
    else:
        print(f"✗ Gemini found {abs(polygon_diff):.1f}% fewer polygon boundaries")
    
    if time_diff < 0:
        print(f"✓ Gemini was {abs(time_diff):.2f}s faster")
    else:
        print(f"✗ Gemini was {time_diff:.2f}s slower")
    
    # Export report if requested
    if output_file:
        report = {
            "timestamp": datetime.now().isoformat(),
            "file": stats_normal['file'],
            "total_locations": stats_normal['total_locations'],
            "normal": stats_normal,
            "gemini": stats_gemini,
            "comparison": {
                "match_rate_diff": match_diff,
                "polygon_rate_diff": polygon_diff,
                "time_diff": time_diff,
                "time_diff_percent": time_diff_percent
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Evaluate Place2Polygon performance")
    parser.add_argument("file", help="Path to the text file to process")
    parser.add_argument("--output", "-o", help="Path to save the report JSON")
    parser.add_argument("--normal-only", action="store_true", help="Run only normal mode (no Gemini)")
    args = parser.parse_args()
    
    # Check for Gemini API key
    has_gemini = bool(os.environ.get("GOOGLE_API_KEY"))
    if not has_gemini and not args.normal_only:
        print("No GOOGLE_API_KEY found in environment. Gemini mode will be skipped.")
        print("Set GOOGLE_API_KEY to enable Gemini comparison.")
    
    # Process with normal mode
    _, stats_normal = process_file(args.file, use_gemini=False)
    
    # Process with Gemini if available
    stats_gemini = None
    if has_gemini and not args.normal_only:
        _, stats_gemini = process_file(args.file, use_gemini=True)
    
    # Generate report
    generate_report(stats_normal, stats_gemini, args.output)

if __name__ == "__main__":
    main() 