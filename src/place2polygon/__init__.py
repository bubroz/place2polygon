"""
Place2Polygon: A tool for extracting location mentions from text and finding their precise 
polygon boundaries using OpenStreetMap data.

This package provides functionality to extract location mentions from text,
find their polygon boundaries, and visualize them on interactive maps.
"""

import logging
from typing import Dict, List, Optional, Any, Union, Tuple

from place2polygon.core import (
    LocationExtractor, default_extractor,
    NominatimClient, default_client,
    BoundarySelector, default_selector,
    MapVisualizer, default_visualizer
)
from place2polygon.cache import CacheManager, default_manager
from place2polygon.gemini import GeminiOrchestrator, default_orchestrator

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

__version__ = "0.1.0"

def extract_and_map_locations(
    text: str,
    output_path: Optional[str] = None,
    cache_ttl: Optional[int] = None,
    extractor: LocationExtractor = default_extractor,
    client: NominatimClient = default_client,
    cache_manager: CacheManager = default_manager,
    selector: BoundarySelector = default_selector,
    visualizer: MapVisualizer = default_visualizer,
    orchestrator: Optional[GeminiOrchestrator] = default_orchestrator,
    min_relevance_score: float = 30.0,
    map_title: Optional[str] = None,
    use_gemini: bool = True
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Extract locations from text and create a map with polygon boundaries.
    
    Args:
        text: Text content to analyze.
        output_path: Path to save the output map. Default creates a temp file.
        cache_ttl: Cache time-to-live in days. Default uses system setting.
        extractor: LocationExtractor instance to use.
        client: NominatimClient instance to use.
        cache_manager: CacheManager instance to use.
        selector: BoundarySelector instance to use.
        visualizer: MapVisualizer instance to use.
        orchestrator: GeminiOrchestrator instance to use for intelligent searches.
        min_relevance_score: Minimum relevance score for locations.
        map_title: Optional title for the map.
        use_gemini: Whether to use Gemini for orchestrating searches.
        
    Returns:
        Tuple of (extracted locations with boundaries, path to the generated map).
    """
    logger.info("Extracting locations from text")
    locations = extractor.extract_locations(text)
    
    # Filter by minimum relevance score
    locations = [loc for loc in locations if loc.get('relevance_score', 0) >= min_relevance_score]
    
    if not locations:
        logger.warning("No relevant locations found in the text")
        return [], ""
    
    logger.info(f"Found {len(locations)} relevant locations")
    
    # Enhance locations with context
    locations = extractor.enhance_locations_with_context(locations, text)
    
    # Determine which search method to use
    if use_gemini and orchestrator:
        logger.info("Using Gemini orchestration for polygon searches")
        enriched_locations = find_polygons_with_gemini(
            locations,
            orchestrator=orchestrator,
            cache_manager=cache_manager,
            cache_ttl=cache_ttl
        )
    else:
        logger.info("Using basic polygon search method")
        enriched_locations = find_polygon_boundaries(
            locations,
            client=client,
            cache_manager=cache_manager,
            selector=selector,
            cache_ttl=cache_ttl
        )
    
    # Create map
    map_path = visualizer.create_map(
        enriched_locations,
        title=map_title or "Place2Polygon Map",
        output_path=output_path
    )
    
    return enriched_locations, map_path

def extract_locations(
    text: str,
    extractor: LocationExtractor = default_extractor,
    min_relevance_score: float = 30.0
) -> List[Dict[str, Any]]:
    """
    Extract location mentions from text.
    
    Args:
        text: Text content to analyze.
        extractor: LocationExtractor instance to use.
        min_relevance_score: Minimum relevance score for locations.
        
    Returns:
        List of extracted locations with metadata.
    """
    locations = extractor.extract_locations(text)
    
    # Filter by minimum relevance score
    locations = [loc for loc in locations if loc.get('relevance_score', 0) >= min_relevance_score]
    
    # Enhance with context
    if locations:
        locations = extractor.enhance_locations_with_context(locations, text)
    
    return locations

def find_polygons_with_gemini(
    locations: List[Dict[str, Any]],
    orchestrator: GeminiOrchestrator,
    cache_manager: CacheManager = default_manager,
    cache_ttl: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Find polygon boundaries for locations using Gemini orchestration.
    
    Args:
        locations: List of location dictionaries.
        orchestrator: GeminiOrchestrator instance to use.
        cache_manager: CacheManager instance to use.
        cache_ttl: Cache time-to-live in days. Default uses system setting.
        
    Returns:
        Locations with boundary data.
    """
    enriched_locations = []
    
    for location in locations:
        location_name = location['name']
        location_type = location['type']
        
        logger.info(f"Finding polygon boundary for {location_name} ({location_type}) using Gemini")
        
        # Try to get from cache
        cache_key = f"boundary_{location_name}_{location_type}"
        cached_result = cache_manager.get_cached_result(cache_key)
        
        if cached_result:
            logger.info(f"Found cached boundary for {location_name}")
            # Merge the cached boundary data with the location data
            location_with_boundary = {**location, **cached_result}
            enriched_locations.append(location_with_boundary)
            continue
        
        # Extract context information for the location
        location_context = {
            'context_sentences': location.get('context_sentences', []),
            'related_locations': location.get('related_locations', [])
        }
        
        # Add state information if available from related locations
        for related in location.get('related_locations', []):
            if related.get('relationship') == 'parent' and related.get('type') == 'state':
                location_context['state'] = related.get('name')
        
        # Use Gemini to orchestrate the search
        result = orchestrator.orchestrate_search(
            location_name=location_name,
            location_type=location_type,
            location_context=location_context
        )
        
        if result:
            # Extract coordinates for marker fallback
            if 'lat' in result and 'lon' in result:
                lat = float(result['lat'])
                lon = float(result['lon'])
            else:
                lat, lon = None, None
            
            # Extract boundary data
            boundary_data = {
                'boundary': result.get('geojson'),
                'display_name': result.get('display_name'),
                'osm_id': result.get('osm_id'),
                'osm_type': result.get('osm_type'),
                'latitude': lat,
                'longitude': lon,
                'address': result.get('address', {}),
            }
            
            # Cache the boundary data
            cache_manager.cache_result(boundary_data, cache_ttl, cache_key)
            
            # Merge the location data with the boundary data
            location_with_boundary = {**location, **boundary_data}
            enriched_locations.append(location_with_boundary)
        else:
            logger.warning(f"No boundary found for {location_name}")
            # Keep the location without a boundary
            enriched_locations.append(location)
    
    return enriched_locations

def find_polygon_boundaries(
    locations: List[Dict[str, Any]],
    client: NominatimClient = default_client,
    cache_manager: CacheManager = default_manager,
    selector: BoundarySelector = default_selector,
    cache_ttl: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Find polygon boundaries for locations using basic search.
    
    Args:
        locations: List of location dictionaries.
        client: NominatimClient instance to use.
        cache_manager: CacheManager instance to use.
        selector: BoundarySelector instance to use.
        cache_ttl: Cache time-to-live in days. Default uses system setting.
        
    Returns:
        Locations with boundary data.
    """
    enriched_locations = []
    
    for location in locations:
        location_name = location['name']
        location_type = location['type']
        
        logger.info(f"Finding polygon boundary for {location_name} ({location_type})")
        
        # Try to get from cache
        cache_key = f"boundary_{location_name}_{location_type}"
        cached_result = cache_manager.get_cached_result(cache_key)
        
        if cached_result:
            logger.info(f"Found cached boundary for {location_name}")
            # Merge the cached boundary data with the location data
            location_with_boundary = {**location, **cached_result}
            enriched_locations.append(location_with_boundary)
            continue
        
        # Search for the location with Nominatim
        search_results = client.search(
            query=location_name,
            polygon_geojson=True,
            addressdetails=True,
            extratags=True,
            limit=5
        )
        
        if not search_results:
            logger.warning(f"No results found for {location_name}")
            # Keep the location without a boundary
            enriched_locations.append(location)
            continue
        
        # Select the most appropriate boundary
        selected_boundaries = selector.select_boundaries(
            search_results,
            location_type=location_type
        )
        
        if selected_boundaries:
            # Get the best match
            best_match = selected_boundaries[0]
            
            # Extract coordinates for marker fallback
            if 'lat' in best_match and 'lon' in best_match:
                lat = float(best_match['lat'])
                lon = float(best_match['lon'])
            else:
                lat, lon = None, None
            
            # Extract boundary data
            boundary_data = {
                'boundary': best_match.get('geojson'),
                'display_name': best_match.get('display_name'),
                'osm_id': best_match.get('osm_id'),
                'osm_type': best_match.get('osm_type'),
                'latitude': lat,
                'longitude': lon,
                'address': best_match.get('address', {}),
            }
            
            # Cache the boundary data
            cache_manager.cache_result(boundary_data, cache_ttl, cache_key)
            
            # Merge the location data with the boundary data
            location_with_boundary = {**location, **boundary_data}
            enriched_locations.append(location_with_boundary)
        else:
            # No valid boundary found
            logger.warning(f"No valid boundary found for {location_name}")
            
            # If the search result has coordinates, use them for a point marker
            if search_results and 'lat' in search_results[0] and 'lon' in search_results[0]:
                result = search_results[0]
                lat = float(result['lat'])
                lon = float(result['lon'])
                
                # Add coordinates to the location
                location_with_point = {**location, 'latitude': lat, 'longitude': lon}
                enriched_locations.append(location_with_point)
            else:
                # Keep the location without a boundary or coordinates
                enriched_locations.append(location)
    
    return enriched_locations

def create_map(
    locations_with_boundaries: List[Dict[str, Any]],
    output_path: Optional[str] = None,
    visualizer: MapVisualizer = default_visualizer,
    title: Optional[str] = None
) -> str:
    """
    Create an interactive map with polygon boundaries.
    
    Args:
        locations_with_boundaries: Locations with boundary data.
        output_path: Path to save the map.
        visualizer: MapVisualizer instance to use.
        title: Optional title for the map.
        
    Returns:
        Path to the generated map.
    """
    map_path = visualizer.create_map(
        locations_with_boundaries,
        title=title or "Place2Polygon Map",
        output_path=output_path
    )
    
    return map_path

def export_to_geojson(
    locations_with_boundaries: List[Dict[str, Any]],
    output_path: str,
    visualizer: MapVisualizer = default_visualizer
) -> str:
    """
    Export location boundaries to a GeoJSON file.
    
    Args:
        locations_with_boundaries: Locations with boundary data.
        output_path: Path to save the GeoJSON file.
        visualizer: MapVisualizer instance to use.
        
    Returns:
        Path to the saved GeoJSON file.
    """
    return visualizer.export_to_geojson(locations_with_boundaries, output_path)
