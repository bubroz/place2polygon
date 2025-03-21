"""
Command-line interface for Place2Polygon.

This module provides a command-line interface for extracting locations from text,
finding their polygon boundaries, and visualizing them on a map.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from place2polygon import (
    __version__,
    extract_locations,
    find_polygon_boundaries,
    find_polygons_with_gemini
)
from place2polygon.core import (
    LocationExtractor,
    NominatimClient,
    BoundarySelector,
    MapVisualizer
)
from place2polygon.gemini import GeminiOrchestrator, setup_google_credentials
from place2polygon.utils import default_output_manager
from place2polygon.cache import CacheManager

logger = logging.getLogger(__name__)

def setup_logging(verbose: bool = False) -> None:
    """
    Set up logging configuration.
    
    Args:
        verbose: Whether to use verbose logging.
    """
    logging_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def extract_command(args: argparse.Namespace) -> None:
    """
    Execute the extract command.
    
    Args:
        args: Command-line arguments.
    """
    # Set up logging
    setup_logging(args.verbose)
    
    # Read input file
    logger.info(f"Reading text from {args.input_file}")
    with open(args.input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Extract locations
    logger.info("Extracting locations from text")
    extractor = LocationExtractor()
    locations = extractor.extract_locations(text)
    
    # Filter by minimum relevance score
    locations = [loc for loc in locations
                if loc.get('relevance_score', 0) >= args.min_relevance]
    
    if not locations:
        logger.warning("No relevant locations found in the text")
        sys.exit(0)
    
    logger.info(f"Found {len(locations)} relevant locations")
    
    # Generate output path
    if args.output:
        output_path = args.output
    else:
        output_path = str(default_output_manager.get_data_path(data_type="locations"))
    
    # Write output
    logger.info(f"Writing locations to {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(locations, f, indent=2)
    
    logger.info(f"Extracted {len(locations)} locations")

def map_command(args: argparse.Namespace) -> None:
    """
    Execute the map command.
    
    Args:
        args: Command-line arguments.
    """
    # Set up logging
    setup_logging(args.verbose)
    
    # Read input file
    logger.info(f"Reading text from {args.input_file}")
    with open(args.input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Extract locations
    logger.info("Extracting locations from text")
    extractor = LocationExtractor()
    locations = extractor.extract_locations(text)
    
    # Filter by minimum relevance score
    locations = [loc for loc in locations
                if loc.get('relevance_score', 0) >= args.min_relevance]
    
    if not locations:
        logger.warning("No relevant locations found in the text")
        sys.exit(0)
    
    logger.info(f"Found {len(locations)} relevant locations")
    
    # Add contextual information
    locations = extractor.enhance_locations_with_context(locations, text)
    
    # Find boundaries
    client = NominatimClient()
    selector = BoundarySelector()
    cache_manager = CacheManager()
    
    if args.gemini:
        # Use Gemini API for searching
        logger.info("Using Gemini API for intelligent searches")
        try:
            orchestrator = GeminiOrchestrator()
            locations_with_boundaries = find_polygons_with_gemini(
                locations, 
                orchestrator=orchestrator,
                cache_manager=cache_manager,
                cache_ttl=args.cache_ttl
            )
        except Exception as e:
            logger.error(f"Error using Gemini API: {str(e)}")
            logger.info("Falling back to basic search")
            locations_with_boundaries = find_polygon_boundaries(
                locations,
                client=client,
                cache_manager=cache_manager,
                selector=selector,
                cache_ttl=args.cache_ttl
            )
    else:
        # Use basic search
        logger.info("Using basic search for boundaries")
        locations_with_boundaries = find_polygon_boundaries(
            locations,
            client=client,
            cache_manager=cache_manager,
            selector=selector, 
            cache_ttl=args.cache_ttl
        )
    
    # Create map
    visualizer = MapVisualizer()
    
    # Generate output path
    if args.output:
        output_path = args.output
    else:
        output_path = str(default_output_manager.get_map_path())
    
    logger.info(f"Creating map at {output_path}")
    visualizer.create_map(
        locations_with_boundaries,
        title=args.title or "Place2Polygon Map",
        output_path=output_path
    )
    
    logger.info(f"Map created at {output_path}")

def setup_gemini_command(args: argparse.Namespace) -> None:
    """
    Set up Google credentials for Gemini API access.
    
    Args:
        args: Command-line arguments.
    """
    # Set up logging
    setup_logging(args.verbose)
    
    # Set up Google credentials
    api_key = args.api_key
    if not api_key:
        api_key = input("Enter your Google API Key: ")
    
    setup_google_credentials(api_key, save=True)
    logger.info("Google credentials set up successfully")

def version_command(args: argparse.Namespace) -> None:
    """
    Display version information.
    
    Args:
        args: Command-line arguments.
    """
    print(f"Place2Polygon v{__version__}")

def list_outputs_command(args: argparse.Namespace) -> None:
    """
    List available output files.
    
    Args:
        args: Command-line arguments.
    """
    # Set up logging
    setup_logging(args.verbose)
    
    # Get output files
    output_files = default_output_manager.list_outputs(
        output_type=args.type,
        max_items=args.max_items
    )
    
    if not output_files:
        print("No output files found.")
        return
    
    # Display outputs
    print(f"Found {len(output_files)} output files:")
    for file_path in output_files:
        print(f"  {file_path}")

def cleanup_command(args: argparse.Namespace) -> None:
    """
    Clean up old output files.
    
    Args:
        args: Command-line arguments.
    """
    # Set up logging
    setup_logging(args.verbose)
    
    # Clean up files
    deleted_count = default_output_manager.clean_old_files(
        max_age_days=args.max_age,
        directories=args.directories
    )
    
    print(f"Deleted {deleted_count} old files.")

def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Extract locations from text and find their polygon boundaries."
    )
    subparsers = parser.add_subparsers(
        dest="command",
        help="Command to execute."
    )
    
    # Extract command
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract locations from text."
    )
    extract_parser.add_argument(
        "input_file",
        help="Input text file."
    )
    extract_parser.add_argument(
        "--output", "-o",
        help="Output JSON file. Default: places2polygon_output/data/locations_<timestamp>.json"
    )
    extract_parser.add_argument(
        "--min-relevance", "-r",
        type=float,
        default=30.0,
        help="Minimum relevance score (0-100). Default: 30.0"
    )
    extract_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging."
    )
    
    # Map command
    map_parser = subparsers.add_parser(
        "map",
        help="Create a map of locations from text."
    )
    map_parser.add_argument(
        "input_file",
        help="Input text file."
    )
    map_parser.add_argument(
        "--output", "-o",
        help="Output HTML file. Default: place2polygon_output/maps/map_<timestamp>.html"
    )
    map_parser.add_argument(
        "--title", "-t",
        help="Map title."
    )
    map_parser.add_argument(
        "--min-relevance", "-r",
        type=float,
        default=30.0,
        help="Minimum relevance score (0-100). Default: 30.0"
    )
    map_parser.add_argument(
        "--cache-ttl",
        type=int,
        help="Cache time-to-live in days."
    )
    map_parser.add_argument(
        "--gemini", "-g",
        action="store_true",
        help="Use Gemini API for intelligent searches."
    )
    map_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging."
    )
    
    # Setup Gemini command
    setup_gemini_parser = subparsers.add_parser(
        "setup_gemini",
        help="Set up Google credentials for Gemini API access."
    )
    setup_gemini_parser.add_argument(
        "--api-key", "-k",
        help="Google API Key."
    )
    setup_gemini_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging."
    )
    
    # Version command
    version_parser = subparsers.add_parser(
        "version",
        help="Display version information."
    )
    
    # List outputs command
    list_parser = subparsers.add_parser(
        "list",
        help="List available output files."
    )
    list_parser.add_argument(
        "--type", "-t",
        choices=["maps", "reports", "data"],
        help="Type of outputs to list."
    )
    list_parser.add_argument(
        "--max-items", "-m",
        type=int,
        default=10,
        help="Maximum number of items to list per category."
    )
    list_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging."
    )
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="Clean up old output files."
    )
    cleanup_parser.add_argument(
        "--max-age", "-m",
        type=int,
        default=30,
        help="Maximum age of files in days before they're deleted."
    )
    cleanup_parser.add_argument(
        "--directories", "-d",
        nargs="+",
        choices=["maps", "reports", "data"],
        help="Directories to clean."
    )
    cleanup_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging."
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute command
    if args.command == "extract":
        extract_command(args)
    elif args.command == "map":
        map_command(args)
    elif args.command == "setup_gemini":
        setup_gemini_command(args)
    elif args.command == "version":
        version_command(args)
    elif args.command == "list":
        list_outputs_command(args)
    elif args.command == "cleanup":
        cleanup_command(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
