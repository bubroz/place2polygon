"""
Nominatim client module for interfacing with the OpenStreetMap Nominatim API.

This module provides a client for making requests to the Nominatim API with
rate limiting, proper HTTP headers, and error handling.
"""

import json
import time
import os
from typing import Dict, List, Optional, Any, Union
import logging
from urllib.parse import urlencode

import httpx

from place2polygon.utils.rate_limiter import nominatim_limiter
from place2polygon.utils.validators import validate_nominatim_params, validate_location_name

logger = logging.getLogger(__name__)

class NominatimClient:
    """
    Client for the OpenStreetMap Nominatim API.
    
    Args:
        base_url: The base URL for the Nominatim API.
        user_agent: The User-Agent header value (required by Nominatim).
        referer: The Referer header value.
        timeout: Request timeout in seconds.
    """
    
    def __init__(
        self,
        base_url: str = "https://nominatim.openstreetmap.org",
        user_agent: Optional[str] = None,
        referer: Optional[str] = None,
        timeout: int = 30
    ):
        """Initialize the Nominatim client."""
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent or os.environ.get("NOMINATIM_USER_AGENT", "Place2Polygon/0.1.0")
        self.referer = referer or os.environ.get("NOMINATIM_REFERER", "https://github.com/bubroz/place2polygon")
        self.timeout = timeout
        
        # Verify user agent is set (required by Nominatim)
        if not self.user_agent:
            raise ValueError("User-Agent header is required for Nominatim API. Set NOMINATIM_USER_AGENT env var.")
    
    def search(
        self,
        query: Optional[str] = None,
        structured_query: Optional[Dict[str, str]] = None,
        limit: int = 10,
        polygon_geojson: bool = True,
        addressdetails: bool = True,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search for places using the Nominatim API.
        
        Args:
            query: Free-form search query.
            structured_query: Dictionary with structured search parameters.
            limit: Maximum number of results to return.
            polygon_geojson: Whether to return polygon geometries as GeoJSON.
            addressdetails: Whether to return address details.
            **kwargs: Additional parameters to pass to the API.
            
        Returns:
            List of search results.
        """
        # Parameter validation
        if not query and not structured_query:
            raise ValueError("Either query or structured_query must be provided")
        
        if query and not validate_location_name(query):
            logger.warning(f"Invalid query: {query}")
            return []
        
        # Prepare parameters
        params = {
            "format": "json",
            "limit": limit,
            "polygon_geojson": 1 if polygon_geojson else 0,
            "addressdetails": 1 if addressdetails else 0,
        }
        
        # Add query or structured query
        if query:
            params["q"] = query
        elif structured_query:
            params.update(structured_query)
        
        # Add additional parameters
        params.update(kwargs)
        
        # Validate and sanitize parameters
        params = validate_nominatim_params(params)
        
        return self._make_request("search", params)
    
    def lookup(
        self,
        osm_ids: List[str],
        polygon_geojson: bool = True,
        addressdetails: bool = True,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Look up OSM objects by their IDs.
        
        Args:
            osm_ids: List of OSM IDs (e.g., ["N123456", "W123456", "R123456"]).
            polygon_geojson: Whether to return polygon geometries as GeoJSON.
            addressdetails: Whether to return address details.
            **kwargs: Additional parameters to pass to the API.
            
        Returns:
            List of lookup results.
        """
        # Validate OSM IDs
        if not osm_ids:
            raise ValueError("OSM IDs must be provided")
        
        # Prepare parameters
        params = {
            "format": "json",
            "osm_ids": ",".join(osm_ids),
            "polygon_geojson": 1 if polygon_geojson else 0,
            "addressdetails": 1 if addressdetails else 0,
        }
        
        # Add additional parameters
        params.update(kwargs)
        
        # Validate and sanitize parameters
        params = validate_nominatim_params(params)
        
        return self._make_request("lookup", params)
    
    def reverse(
        self,
        lat: float,
        lon: float,
        zoom: int = 18,
        polygon_geojson: bool = True,
        addressdetails: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Reverse geocode a coordinate.
        
        Args:
            lat: Latitude.
            lon: Longitude.
            zoom: Zoom level for reverse geocoding.
            polygon_geojson: Whether to return polygon geometries as GeoJSON.
            addressdetails: Whether to return address details.
            **kwargs: Additional parameters to pass to the API.
            
        Returns:
            Reverse geocoding result.
        """
        # Validate coordinates
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise ValueError(f"Invalid coordinates: lat={lat}, lon={lon}")
        
        # Prepare parameters
        params = {
            "format": "json",
            "lat": lat,
            "lon": lon,
            "zoom": zoom,
            "polygon_geojson": 1 if polygon_geojson else 0,
            "addressdetails": 1 if addressdetails else 0,
        }
        
        # Add additional parameters
        params.update(kwargs)
        
        # Validate and sanitize parameters
        params = validate_nominatim_params(params)
        
        result = self._make_request("reverse", params)
        return result[0] if result else {}
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Make a request to the Nominatim API with rate limiting.
        
        Args:
            endpoint: The API endpoint.
            params: The request parameters.
            
        Returns:
            The API response as a list of dictionaries.
        """
        # Prepare request URL
        url = f"{self.base_url}/{endpoint}?{urlencode(params)}"
        
        # Prepare headers
        headers = {
            "User-Agent": self.user_agent,
            "Referer": self.referer,
            "Accept": "application/json",
        }
        
        # Apply rate limiting
        logger.debug(f"Making request to Nominatim API: {url}")
        
        try:
            # Execute with rate limiting and retry
            response_data = nominatim_limiter.execute_with_retry(
                self._perform_request,
                url=url,
                headers=headers,
                max_retries=3,
                backoff_factor=2.0,
                rate_limit_key="nominatim"
            )
            
            # If the response is empty, return an empty list
            if not response_data:
                return []
            
            # For reverse geocoding, the response is a single object, not a list
            if isinstance(response_data, dict):
                return [response_data]
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error making request to Nominatim API: {str(e)}")
            return []
    
    def _perform_request(self, url: str, headers: Dict[str, str]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Perform the actual HTTP request.
        
        Args:
            url: The request URL.
            headers: The request headers.
            
        Returns:
            The response data.
            
        Raises:
            Exception: If the request fails.
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, headers=headers)
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Parse JSON response
                if response.text.strip():
                    return response.json()
                else:
                    return []
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Rate limit exceeded, will retry with backoff")
                raise
            elif e.response.status_code == 404:
                logger.warning(f"No results found for request: {url}")
                return []
            else:
                logger.error(f"HTTP error: {e}")
                raise
                
        except httpx.TimeoutException:
            logger.error(f"Request timed out: {url}")
            raise
            
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise

# Create a default instance
default_client = NominatimClient()
