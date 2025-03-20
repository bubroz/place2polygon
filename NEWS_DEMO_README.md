# Place2Polygon News Article Demo

This demo shows how to use the Place2Polygon tool to analyze news articles and visualize the locations mentioned in them on a map with precise polygon boundaries from OpenStreetMap.

## Features

- Extract location mentions from news articles using spaCy NER
- Find precise polygon boundaries using OpenStreetMap data via Nominatim
- Intelligent search orchestration using Gemini Flash 2.0
- Focus on accurate US location boundaries (states, counties, cities, neighborhoods)
- Smart boundary selection for nested locations (only show most specific boundary)
- Determine the relevance of each location based on position and frequency
- Create an interactive map visualization with accurate administrative boundaries
- Display detailed location information in popups
- Persistent caching of Nominatim results for improved performance and policy compliance

## Files

- `nominatim_article_demo.py` - The main script that uses Nominatim API to find proper polygon boundaries
- `local_article_demo.py` - Legacy script that has been deprecated (use nominatim_article_demo.py instead)
- `sample_article.txt` - A sample news article for demonstration
- `polygon_cache.db` - SQLite database for caching polygon search results
- `gemini_orchestrator.py` - Implements the Gemini Flash 2.0 search orchestration

## Usage

```bash
# Run with the default sample article
python nominatim_article_demo.py

# Or specify your own article file
python nominatim_article_demo.py path/to/your/article.txt

# Run with specific cache settings
python nominatim_article_demo.py --cache-ttl=30 path/to/your/article.txt
```

## Creating Your Own Articles

You can create your own article text files to analyze. The format should be:

```
Title of the Article

The content of the article goes here. Make sure to include location mentions
that you want to be detected and visualized on the map.

Multiple paragraphs are supported.
```

## Output

The demo will:

1. Print information about the extracted locations
2. Use Gemini Flash 2.0 to orchestrate sophisticated polygon boundary searches
2. Query Nominatim (respecting rate limits) to find polygon boundaries
4. Apply smart boundary selection to avoid redundant overlapping polygons
5. Create an interactive map visualization with:
   - Precise administrative boundaries from OpenStreetMap
   - Point markers ONLY as a last resort fallback when thorough polygon boundary searches fail
6. Save the map to `demo_output/nominatim_article_map.html`
7. Open the map in your default web browser
8. Export the results to JSON for validation

## Smart Boundary Selection

The demo implements intelligent boundary selection:
- When a location is found within another (e.g., city within a county within a state), only the most specific boundary is shown
- Point markers are only displayed after exhaustive attempts to find polygon boundaries have failed
- The hierarchical relationship between locations is preserved in the data

## Polygon Search Algorithm

The demo uses a multi-stage search algorithm orchestrated by Gemini Flash 2.0:

1. First attempts to find exact polygon match with proper admin level
2. If unsuccessful, tries broader criteria (different admin levels)
3. Attempts alternative name variations and boundary types
4. Only falls back to point markers after all polygon search strategies are exhausted
5. Maintains detailed search logs for debugging failed polygon searches

## Caching System

The demo implements a robust caching system that:

- Persists all Nominatim query results to SQLite database
- Enforces configurable time-to-live (TTL) for cached data
- Includes polygon geometries in GeoJSON format
- Dramatically improves performance for repeated location lookups
- Ensures compliance with OSM usage policies
- Provides cache statistics and management utilities

## Validation

The exported JSON file (`extracted_locations_with_boundaries.json`) can be used to validate the accuracy of location extraction and boundary matching. It includes:

- Name, type, and administrative level of each location
- Whether a polygon boundary was found
- Geometry type (MultiPolygon, Polygon, Point, etc.)
- Administrative hierarchy (state, county, city, etc.)
- OSM relation ID for the boundary
- Number of mentions in the text
- Complete search attempt history for each location

## Requirements

This demo requires the following Python packages:
- spacy (with the en_core_web_sm model)
- pandas
- geopandas
- folium
- shapely
- requests (for Nominatim API)
- google-generativeai (for Gemini Flash 2.0)
- sqlite3 (for persistent caching)

## Current Limitations

- Focused primarily on US locations currently
- Uses Nominatim public API with appropriate rate limiting
- May have reduced accuracy for non-US locations

## Troubleshooting

If you encounter issues with the boundary matching, check:
1. Internet connectivity (required for Nominatim API)
2. The location name spelling matches what's in OpenStreetMap
3. The location type is correctly identified (state, county, city, etc.)
4. You're not exceeding Nominatim API rate limits (check cache statistics)
5. Review the search logs for details on attempted search strategies 