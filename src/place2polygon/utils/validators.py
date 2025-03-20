"""
Validator module for input validation.

This module provides validator functions for ensuring that inputs meet
the required specifications before processing.
"""

import re
from typing import Dict, List, Optional, Any, Union
import logging

logger = logging.getLogger(__name__)

def validate_location_name(name: str) -> bool:
    """
    Validate a location name.
    
    Args:
        name: The location name to validate.
        
    Returns:
        True if valid, False otherwise.
    """
    if not name or not isinstance(name, str):
        logger.warning(f"Invalid location name: {name}")
        return False
    
    # Location name should be at least 2 characters long
    if len(name.strip()) < 2:
        logger.warning(f"Location name too short: {name}")
        return False
    
    # Basic alphanumeric check with common punctuation
    # This is intentionally permissive as location names can vary widely
    pattern = r'^[\w\s.,\'()-]+$'
    if not re.match(pattern, name):
        logger.warning(f"Location name contains invalid characters: {name}")
        return False
    
    return True

def validate_coordinates(lat: float, lon: float) -> bool:
    """
    Validate latitude and longitude coordinates.
    
    Args:
        lat: Latitude value.
        lon: Longitude value.
        
    Returns:
        True if valid, False otherwise.
    """
    # Latitude must be between -90 and 90
    if not isinstance(lat, (int, float)) or lat < -90 or lat > 90:
        logger.warning(f"Invalid latitude: {lat}")
        return False
    
    # Longitude must be between -180 and 180
    if not isinstance(lon, (int, float)) or lon < -180 or lon > 180:
        logger.warning(f"Invalid longitude: {lon}")
        return False
    
    return True

def validate_bbox(bbox: List[float]) -> bool:
    """
    Validate a bounding box.
    
    Args:
        bbox: List of [min_lon, min_lat, max_lon, max_lat].
        
    Returns:
        True if valid, False otherwise.
    """
    if not isinstance(bbox, list) or len(bbox) != 4:
        logger.warning(f"Invalid bbox format: {bbox}")
        return False
    
    min_lon, min_lat, max_lon, max_lat = bbox
    
    # Check longitude values
    if not isinstance(min_lon, (int, float)) or not isinstance(max_lon, (int, float)):
        logger.warning(f"Invalid longitude values in bbox: {min_lon}, {max_lon}")
        return False
    
    if min_lon < -180 or min_lon > 180 or max_lon < -180 or max_lon > 180:
        logger.warning(f"Longitude values out of range in bbox: {min_lon}, {max_lon}")
        return False
    
    if min_lon > max_lon:
        logger.warning(f"Minimum longitude greater than maximum longitude in bbox: {min_lon}, {max_lon}")
        return False
    
    # Check latitude values
    if not isinstance(min_lat, (int, float)) or not isinstance(max_lat, (int, float)):
        logger.warning(f"Invalid latitude values in bbox: {min_lat}, {max_lat}")
        return False
    
    if min_lat < -90 or min_lat > 90 or max_lat < -90 or max_lat > 90:
        logger.warning(f"Latitude values out of range in bbox: {min_lat}, {max_lat}")
        return False
    
    if min_lat > max_lat:
        logger.warning(f"Minimum latitude greater than maximum latitude in bbox: {min_lat}, {max_lat}")
        return False
    
    return True

def validate_nominatim_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize parameters for Nominatim API.
    
    Args:
        params: Dictionary of parameters for Nominatim API.
        
    Returns:
        Sanitized parameters dictionary.
    """
    valid_params = {}
    
    # Allowed parameter keys
    allowed_keys = {
        'q', 'street', 'city', 'county', 'state', 'country', 'postalcode',
        'format', 'addressdetails', 'extratags', 'namedetails', 'polygon_geojson',
        'polygon_kml', 'polygon_svg', 'polygon_text', 'limit', 'viewbox',
        'bounded', 'email', 'exclude_place_ids', 'dedupe', 'debug', 'polygon_threshold'
    }
    
    for key, value in params.items():
        if key not in allowed_keys:
            logger.warning(f"Ignoring invalid Nominatim parameter: {key}")
            continue
        
        # Sanitize the value
        if isinstance(value, str):
            # Remove any potentially harmful characters
            value = re.sub(r'[<>]', '', value)
        
        valid_params[key] = value
    
    return valid_params

def validate_admin_level(admin_level: Optional[int]) -> bool:
    """
    Validate an administrative level value.
    
    Args:
        admin_level: The admin level to validate.
        
    Returns:
        True if valid, False otherwise.
    """
    if admin_level is None:
        return True
    
    if not isinstance(admin_level, int):
        logger.warning(f"Admin level must be an integer: {admin_level}")
        return False
    
    # Admin levels in OSM typically range from 2 to 10
    if admin_level < 2 or admin_level > 10:
        logger.warning(f"Admin level out of typical range (2-10): {admin_level}")
        return False
    
    return True

def validate_geojson(geojson: Dict[str, Any]) -> bool:
    """
    Validate a GeoJSON object.
    
    Args:
        geojson: The GeoJSON object to validate.
        
    Returns:
        True if valid, False otherwise.
    """
    if not isinstance(geojson, dict):
        logger.warning(f"GeoJSON must be a dictionary: {type(geojson)}")
        return False
    
    # Check for required fields
    required_fields = ['type', 'coordinates']
    if not all(field in geojson for field in required_fields):
        logger.warning(f"GeoJSON missing required fields: {required_fields}")
        return False
    
    # Validate type
    valid_types = ['Point', 'LineString', 'Polygon', 'MultiPoint', 
                  'MultiLineString', 'MultiPolygon', 'GeometryCollection']
    if geojson['type'] not in valid_types:
        logger.warning(f"Invalid GeoJSON type: {geojson['type']}")
        return False
    
    # For GeometryCollection, validate geometries
    if geojson['type'] == 'GeometryCollection':
        if 'geometries' not in geojson:
            logger.warning("GeometryCollection missing 'geometries' field")
            return False
        
        if not isinstance(geojson['geometries'], list):
            logger.warning("GeometryCollection 'geometries' must be a list")
            return False
        
        # Basic check for each geometry
        for geometry in geojson['geometries']:
            if not isinstance(geometry, dict) or 'type' not in geometry:
                logger.warning(f"Invalid geometry in GeometryCollection: {geometry}")
                return False
    
    return True
