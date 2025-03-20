"""
Boundary selector module for intelligently selecting the most appropriate
boundary from multiple options.

This module provides functionality to select the most appropriate boundary
when multiple administrative boundaries are found for nested locations.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
import logging
import json

from place2polygon.utils.validators import validate_geojson

logger = logging.getLogger(__name__)

# Map of OSM admin levels to human-readable types for the US
US_ADMIN_LEVELS = {
    2: "country",
    4: "state",
    6: "county",
    8: "city/town",
    10: "neighborhood/district"
}

class BoundarySelector:
    """
    Select the most appropriate boundary for display from multiple options.
    
    Args:
        prefer_smaller: Whether to prefer smaller (more specific) boundaries.
        max_results: Maximum number of boundaries to return.
    """
    
    def __init__(self, prefer_smaller: bool = True, max_results: int = 1):
        """Initialize the boundary selector."""
        self.prefer_smaller = prefer_smaller
        self.max_results = max_results
    
    def select_boundaries(
        self,
        nominatim_results: List[Dict[str, Any]],
        location_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Select the most appropriate boundary from Nominatim results.
        
        Args:
            nominatim_results: List of Nominatim API results.
            location_type: Optional location type hint (city, county, state, etc.)
            
        Returns:
            List of selected boundary results.
        """
        if not nominatim_results:
            logger.warning("No boundaries to select from")
            return []
        
        # Filter out results without polygons
        has_polygon = [r for r in nominatim_results if self._has_valid_polygon(r)]
        
        if not has_polygon:
            logger.warning("No results with valid polygons found")
            return []
        
        # Get admin level for each result
        with_levels = [(r, self._get_admin_level(r)) for r in has_polygon]
        
        # Filter by location type if specified
        if location_type:
            target_levels = self._get_target_admin_levels(location_type)
            if target_levels:
                filtered = [(r, level) for r, level in with_levels if level in target_levels]
                if filtered:
                    with_levels = filtered
        
        # Sort by admin level (ascending = larger areas first, descending = smaller areas first)
        with_levels.sort(key=lambda x: x[1], reverse=self.prefer_smaller)
        
        # Return the top results
        return [r for r, _ in with_levels[:self.max_results]]
    
    def _has_valid_polygon(self, result: Dict[str, Any]) -> bool:
        """
        Check if a result has a valid polygon.
        
        Args:
            result: Nominatim API result.
            
        Returns:
            True if the result has a valid polygon, False otherwise.
        """
        # Check for GeoJSON polygon
        if 'geojson' in result:
            geojson = result['geojson']
            if not validate_geojson(geojson):
                return False
            
            # Check if it's a polygon type
            polygon_types = ['Polygon', 'MultiPolygon']
            return geojson.get('type') in polygon_types
        
        return False
    
    def _get_admin_level(self, result: Dict[str, Any]) -> int:
        """
        Get the administrative level of a result.
        
        Args:
            result: Nominatim API result.
            
        Returns:
            The administrative level (2-10) or a default value.
        """
        # Try to get from address
        if 'address' in result:
            for key in result['address']:
                if key.startswith('admin_level_'):
                    level_str = key.replace('admin_level_', '')
                    try:
                        return int(level_str)
                    except ValueError:
                        pass
        
        # Try to get from extratags
        if 'extratags' in result and 'admin_level' in result['extratags']:
            try:
                return int(result['extratags']['admin_level'])
            except ValueError:
                pass
        
        # Try to determine from OSM type and class
        osm_type = result.get('osm_type')
        osm_class = result.get('class')
        
        if osm_type == 'relation' and osm_class == 'boundary':
            # This is likely an administrative boundary, default to level 8 (city/town)
            return 8
        elif osm_type == 'relation' and osm_class == 'place':
            # This is likely a place, default to level 10 (neighborhood)
            return 10
        elif osm_class == 'natural':
            # Natural features, default to level 0 (lowest priority)
            return 0
        
        # Default value
        return 5  # Middle priority
    
    def _get_target_admin_levels(self, location_type: str) -> List[int]:
        """
        Get target administrative levels for a location type.
        
        Args:
            location_type: The location type (city, county, state, etc.)
            
        Returns:
            List of administrative levels that match the location type.
        """
        # Map location types to admin levels
        type_to_level = {
            'country': [2],
            'state': [4],
            'province': [4],
            'county': [6],
            'parish': [6],
            'borough': [6],
            'city': [8],
            'town': [8],
            'village': [8],
            'municipality': [8],
            'neighborhood': [10],
            'district': [10],
            'quarter': [10]
        }
        
        # Get the level for the specified type (case-insensitive)
        for key, levels in type_to_level.items():
            if location_type.lower() == key.lower():
                return levels
        
        # For unknown types, return a wide range
        return [4, 6, 8, 10]
    
    def get_nested_hierarchy(self, results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Organize results into a hierarchical structure based on admin levels.
        
        Args:
            results: List of Nominatim API results.
            
        Returns:
            Dictionary mapping admin level names to lists of results.
        """
        hierarchy = {}
        
        # Group results by admin level
        for result in results:
            level = self._get_admin_level(result)
            level_name = US_ADMIN_LEVELS.get(level, f"level_{level}")
            
            if level_name not in hierarchy:
                hierarchy[level_name] = []
            
            hierarchy[level_name].append(result)
        
        return hierarchy
    
    def combine_boundaries(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Combine multiple boundaries into a single GeoJSON feature collection.
        
        Args:
            results: List of Nominatim API results with polygons.
            
        Returns:
            GeoJSON feature collection.
        """
        feature_collection = {
            "type": "FeatureCollection",
            "features": []
        }
        
        for result in results:
            if 'geojson' in result:
                geojson = result['geojson']
                
                # Create a feature from the geometry
                feature = {
                    "type": "Feature",
                    "properties": {
                        "name": result.get('display_name', ''),
                        "osm_id": result.get('osm_id', ''),
                        "admin_level": self._get_admin_level(result),
                        "type": US_ADMIN_LEVELS.get(self._get_admin_level(result), "unknown")
                    },
                    "geometry": geojson
                }
                
                feature_collection["features"].append(feature)
        
        return feature_collection

# Create a default instance
default_selector = BoundarySelector()
