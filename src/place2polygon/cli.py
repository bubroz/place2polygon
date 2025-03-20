"""
Command-line interface for Place2Polygon.

This module provides a command-line interface for the Place2Polygon package,
allowing users to extract locations from text and create maps from the command line.
"""

import os
import sys
from typing import Optional
import logging

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich import print as rprint

import place2polygon
from place2polygon import extract_and_map_locations, extract_locations, find_polygon_boundaries, create_map, export_to_geojson

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
    input_file: str = typer.Argument(..., help="Input text file path"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Output HTML map file path"),
    geojson_file: Optional[str] = typer.Option(None, "--geojson", "-g", help="Output GeoJSON file path"),
    min_relevance: float = typer.Option(30.0, "--min-relevance", "-r", help="Minimum relevance score (0-100)"),
    cache_ttl: Optional[int] = typer.Option(30, "--cache-ttl", "-c", help="Cache TTL in days"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Map title"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    open_browser: bool = typer.Option(False, "--open", "-b", help="Open map in browser"),
    use_gemini: bool = typer.Option(True, "--gemini/--no-gemini", help="Use Gemini for intelligent search")
):
    """
    Extract locations from a text file and create an interactive map.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Read input file
        with open(input_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Generate title if not provided
        if not title:
            title = f"Places in {os.path.basename(input_file)}"
        
        # Check if we can use Gemini
        if use_gemini and not os.environ.get("GOOGLE_API_KEY"):
            console.print("[yellow]Warning: GOOGLE_API_KEY not set. Disabling Gemini.[/yellow]")
            use_gemini = False
        
        # Extract locations and create map
        locations, map_path = extract_and_map_locations(
            text,
            output_path=output_file,
            cache_ttl=cache_ttl,
            min_relevance_score=min_relevance,
            map_title=title,
            use_gemini=use_gemini
        )
        
        console.print(f"[bold green]Found {len(locations)} locations[/bold green]")
        console.print(f"[bold green]Map created at {map_path}[/bold green]")
        
        # Export to GeoJSON if specified
        if geojson_file and locations:
            geojson_path = export_to_geojson(locations, geojson_file)
            console.print(f"[bold green]GeoJSON exported to {geojson_path}[/bold green]")
        
        # Open in browser if requested
        if open_browser and map_path:
            import webbrowser
            webbrowser.open(f"file://{os.path.abspath(map_path)}")
        
        return locations, map_path
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        if verbose:
            logger.exception("Error details")
        return [], ""

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
