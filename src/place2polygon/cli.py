"""
Command-line interface for Place2Polygon.

This module provides a command-line interface for the Place2Polygon package,
allowing users to extract locations from text and create maps from the command line.
"""

import os
import sys
from typing import Optional
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich import print as rprint

import place2polygon
from place2polygon import extract_and_map_locations, extract_locations, find_polygon_boundaries, create_map, export_to_geojson
from place2polygon.core.location_extractor import LocationExtractor
from place2polygon.core.map_visualizer import MapVisualizer
from place2polygon.core.nominatim_client import default_client

# Set up logging with rich
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)

logger = logging.getLogger("place2polygon.cli")

app = typer.Typer(help="Extract location mentions from text and find their polygon boundaries.")
console = Console()

@app.command()
def extract(
    input_file: str = typer.Argument(..., help="Input text file path"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Output JSON file path"),
    min_relevance: float = typer.Option(30.0, "--min-relevance", "-r", help="Minimum relevance score (0-100)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """
    Extract location mentions from a text file.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Read input file
        with open(input_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Extract locations
        locations = extract_locations(text, min_relevance_score=min_relevance)
        
        # Print results
        console.print(f"[bold green]Found {len(locations)} locations:[/bold green]")
        for loc in locations:
            console.print(f"- [bold]{loc['name']}[/bold] ({loc['type']}) - Relevance: {loc['relevance_score']:.1f}")
        
        # Write output file if specified
        if output_file:
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(locations, f, indent=2)
            console.print(f"[bold green]Locations saved to {output_file}[/bold green]")
        
        return locations
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        if verbose:
            logger.exception("Error details")
        return []

@app.command()
def map(
    ctx: typer.Context,
    file: str = typer.Argument(..., help="Text file to extract locations from"),
    output: str = typer.Option("map.html", "--output", "-o", help="Output file for the map"),
    use_gemini: bool = typer.Option(False, "--gemini", "-g", help="Use Gemini for orchestration"),
    cache_stats: bool = typer.Option(False, "--cache-stats", "-c", help="Show cache statistics"),
) -> int:
    """Generate a map from a text file."""
    try:
        with open(file, "r") as f:
            text = f.read()
            
        logger.info("Extracting locations from text")
        extractor = LocationExtractor()
        locations = extractor.extract_locations(text)
        logger.info(f"Found {len(locations)} relevant locations")
        
        # Find the polygon boundaries for each location
        client = default_client
        
        # Use the gemini orchestrator if requested
        if use_gemini:
            logger.info("Using Gemini orchestration for polygon searches")
            from place2polygon.gemini.orchestrator import GeminiOrchestrator, default_orchestrator
            if default_orchestrator is None:
                logger.warning("Gemini orchestration not available, using basic client")
            else:
                client = default_orchestrator
        
        # Create a new map
        map_vis = MapVisualizer()
        
        # Debug log the first location structure
        if locations and len(locations) > 0:
            logger.info(f"First location structure: {locations[0]}")
        
        # Process each location
        locations_with_boundaries = []
        for location in locations:
            name = location["name"]
            entity_type = location.get("type", "").lower()
            
            # Make "gpe" more user friendly
            if entity_type == "gpe":
                entity_type = "city"
                
            logger.info(f"Finding polygon boundary for {name} ({entity_type}) {'' if not use_gemini else 'using Gemini'}")
            
            try:
                result = None
                
                # Try to find with gemini first if available
                if use_gemini and hasattr(client, "orchestrate_search"):
                    try:
                        result = client.orchestrate_search(name, location_type=entity_type)
                    except Exception as e:
                        logger.error(f"Error finding boundary with Gemini: {str(e)}")
                        logger.warning(f"Falling back to basic search for {name}")
                        
                # If gemini search failed or not available, try basic search
                if result is None:
                    results = client.search(name, location_type=entity_type)
                    # Get the first result if there are any
                    result = results[0] if results else None
                    
                # If we found a result, add it to the map
                if result:
                    try:
                        # Store the result in a format compatible with the map visualizer
                        boundary_data = {
                            "name": name,
                            "type": entity_type,
                            "boundary": result["geojson"] if "geojson" in result else None,
                            "osm_id": result.get("osm_id"),
                            "osm_type": result.get("osm_type"),
                            "address": result.get("address", {})
                        }
                        
                        # Add coordinates if available
                        if "lat" in result and "lon" in result:
                            boundary_data["latitude"] = float(result["lat"])
                            boundary_data["longitude"] = float(result["lon"])
                            
                        # Store for later adding to the map
                        locations_with_boundaries.append(boundary_data)
                    except Exception as e:
                        logger.error(f"Error adding boundary for {name}: {str(e)}")
                else:
                    logger.warning(f"No boundary found for {name}")
            except Exception as e:
                logger.error(f"Error finding boundary for {name}: {str(e)}")
                logger.warning(f"No boundary found for {name}")
                
        # Create the map with all found boundaries
        if locations_with_boundaries:
            # Create the map with all found boundaries
            map_output_path = map_vis.create_map(
                locations=locations_with_boundaries,
                output_path=output,
                title=f"Place2Polygon: {len(locations_with_boundaries)} Locations"
            )
            logger.info(f"Map saved to {map_output_path}")
        else:
            logger.warning("No boundaries found for any locations")
        
        # Show cache stats if requested
        if cache_stats:
            stats = client.get_cache_stats()
            print("\nCache Statistics:")
            print(f"  Hits: {stats['hits']}")
            print(f"  Misses: {stats['misses']}")
            print(f"  Hit Rate: {stats['hit_rate']:.1%}")
            print(f"  Size: {stats['size']} items")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1
        
    return 0

@app.command()
def setup_gemini():
    """
    Setup the Google API key for Gemini integration.
    """
    console.print("[bold]Setup Google API Key for Gemini Integration[/bold]")
    console.print("This will help you set up the API key for Gemini Flash 2.0 integration.")
    console.print("")
    
    # Check if API key is already set
    current_key = os.environ.get("GOOGLE_API_KEY", "")
    if current_key:
        console.print(f"[green]Google API key is already set in the environment.[/green]")
        change_key = typer.confirm("Do you want to change it?")
        if not change_key:
            return
    
    # Get the new API key
    api_key = typer.prompt("Enter your Google API key", hide_input=True)
    
    if not api_key:
        console.print("[yellow]No API key entered. Setup canceled.[/yellow]")
        return
    
    # Write to .env file
    try:
        with open(".env", "r") as f:
            env_lines = f.readlines()
    except:
        env_lines = []
    
    # Update or add GOOGLE_API_KEY line
    key_updated = False
    for i, line in enumerate(env_lines):
        if line.startswith("GOOGLE_API_KEY="):
            env_lines[i] = f"GOOGLE_API_KEY={api_key}\n"
            key_updated = True
            break
    
    if not key_updated:
        env_lines.append(f"GOOGLE_API_KEY={api_key}\n")
    
    # Write back to .env file
    with open(".env", "w") as f:
        f.writelines(env_lines)
    
    console.print("[green]Google API key has been saved to .env file.[/green]")
    console.print("To use it in the current session, please run:")
    console.print(f"[bold]export GOOGLE_API_KEY={api_key}[/bold]")

@app.command()
def version():
    """
    Show version information.
    """
    console.print(f"[bold]Place2Polygon[/bold] version {place2polygon.__version__}")
    console.print("A tool for extracting location mentions from text and finding their precise polygon boundaries.")
    console.print("https://github.com/bubroz/place2polygon")
    
    # Check if Gemini is available
    if os.environ.get("GOOGLE_API_KEY"):
        console.print("[green]Gemini Flash 2.0 integration: Available[/green]")
    else:
        console.print("[yellow]Gemini Flash 2.0 integration: Not configured (run 'setup_gemini' command)[/yellow]")

if __name__ == "__main__":
    app()
