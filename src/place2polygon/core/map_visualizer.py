"""
Map visualizer module for creating interactive maps with location boundaries.

This module uses Folium to create interactive maps with polygons for
location boundaries, with appropriate styling and popups.
"""

import os
import json
import tempfile
from typing import Dict, List, Optional, Any, Union, Tuple
import logging

import folium
from folium.plugins import MarkerCluster

logger = logging.getLogger(__name__)

# Default map style configurations
DEFAULT_STYLES = {
    "country": {
        "color": "#3388ff",
        "weight": 2,
        "fillColor": "#3388ff",
        "fillOpacity": 0.1,
    },
    "state": {
        "color": "#33a02c",
        "weight": 2,
        "fillColor": "#33a02c",
        "fillOpacity": 0.1,
    },
    "county": {
        "color": "#e31a1c",
        "weight": 2,
        "fillColor": "#e31a1c",
        "fillOpacity": 0.1,
    },
    "city/town": {
        "color": "#ff7f00",
        "weight": 2,
        "fillColor": "#ff7f00",
        "fillOpacity": 0.2,
    },
    "neighborhood/district": {
        "color": "#6a3d9a",
        "weight": 2,
        "fillColor": "#6a3d9a",
        "fillOpacity": 0.2,
    },
    # Default style for other types
    "default": {
        "color": "#666666",
        "weight": 2,
        "fillColor": "#666666",
        "fillOpacity": 0.2,
    },
    # Style for point markers
    "point": {
        "color": "#1f78b4",
    }
}

class MapVisualizer:
    """
    Create interactive maps with location boundaries.
    
    Args:
        default_zoom: Default zoom level for the map.
        cluster_points: Whether to cluster point markers.
        styles: Optional custom styles for different location types.
    """
    
    def __init__(
        self,
        default_zoom: int = 4,
        cluster_points: bool = True,
        styles: Optional[Dict[str, Dict[str, Any]]] = None
    ):
        """Initialize the map visualizer."""
        self.default_zoom = default_zoom
        self.cluster_points = cluster_points
        self.styles = styles or DEFAULT_STYLES
    
    def create_map(
        self,
        locations: List[Dict[str, Any]],
        center: Optional[Tuple[float, float]] = None,
        zoom: Optional[int] = None,
        title: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Create an interactive map with polygons for location boundaries.
        
        Args:
            locations: List of location dictionaries with boundaries.
            center: Optional map center (latitude, longitude).
            zoom: Optional zoom level (overrides default_zoom).
            title: Optional map title.
            output_path: Optional path to save the map HTML.
            
        Returns:
            Path to the saved map HTML file.
        """
        # Determine map center and zoom
        if not center and locations:
            # Use the first location with coordinates as center
            for location in locations:
                if 'latitude' in location and 'longitude' in location:
                    center = (location['latitude'], location['longitude'])
                    break
            
            # Default center if none found
            if not center:
                # Center on continental US
                center = (39.8283, -98.5795)
        elif not center:
            # Default center (continental US)
            center = (39.8283, -98.5795)
        
        # Create the map
        m = folium.Map(
            location=center,
            zoom_start=zoom or self.default_zoom,
            tiles='OpenStreetMap'
        )
        
        # Add title if provided
        if title:
            self._add_title(m, title)
        
        # Create a marker cluster if clustering is enabled
        marker_cluster = MarkerCluster() if self.cluster_points else m
        
        # Add locations to map
        has_polygons = False
        for location in locations:
            # Check if the location has a boundary
            if 'boundary' in location and location['boundary']:
                has_polygons = True
                self._add_polygon(m, location)
            elif all(key in location for key in ['latitude', 'longitude']):
                # Fallback to point marker
                self._add_marker(marker_cluster, location)
        
        # Add the marker cluster to the map if we created one
        if self.cluster_points and not has_polygons:
            marker_cluster.add_to(m)
        
        # Add layer control if we have polygons
        if has_polygons:
            folium.LayerControl().add_to(m)
        
        # Save the map to a file
        if not output_path:
            # Create a temporary file
            fd, output_path = tempfile.mkstemp(suffix='.html')
            os.close(fd)
        
        m.save(output_path)
        logger.info(f"Map saved to {output_path}")
        
        return output_path
    
    def _add_polygon(self, map_obj: folium.Map, location: Dict[str, Any]) -> None:
        """
        Add a polygon to the map.
        
        Args:
            map_obj: The folium Map object.
            location: Location dictionary with boundary data.
        """
        boundary = location['boundary']
        location_name = location.get('name', 'Unknown location')
        location_type = location.get('type', 'default')
        
        # Get the style for this location type
        style = self.styles.get(location_type, self.styles['default']).copy()
        
        # Apply relevance score to opacity if available
        if 'relevance_score' in location:
            score = location['relevance_score']
            style['fillOpacity'] = min(0.9, style.get('fillOpacity', 0.2) * (score / 50))
        
        # Create a GeoJson layer
        if 'type' in boundary and boundary['type'] in ['Polygon', 'MultiPolygon']:
            # Create the GeoJSON feature
            feature = {
                'type': 'Feature',
                'properties': {
                    'name': location_name,
                    'type': location_type,
                    **{k: v for k, v in location.items() if k not in ['boundary', 'polygon_geojson']}
                },
                'geometry': boundary
            }
            
            # Create the popup content
            popup_content = self._create_popup_content(location)
            
            # Add the GeoJson layer to the map
            folium.GeoJson(
                data=feature,
                name=location_name,
                style_function=lambda x: style,
                tooltip=folium.Tooltip(location_name),
                popup=folium.Popup(popup_content, max_width=300)
            ).add_to(map_obj)
    
    def _add_marker(self, map_obj: Union[folium.Map, MarkerCluster], location: Dict[str, Any]) -> None:
        """
        Add a marker to the map.
        
        Args:
            map_obj: The folium Map or MarkerCluster object.
            location: Location dictionary with coordinates.
        """
        location_name = location.get('name', 'Unknown location')
        lat = location.get('latitude')
        lon = location.get('longitude')
        
        if lat is not None and lon is not None:
            # Create the popup content
            popup_content = self._create_popup_content(location)
            
            # Add the marker to the map
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_content, max_width=300),
                tooltip=location_name,
                icon=folium.Icon(color=self.styles['point']['color'])
            ).add_to(map_obj)
    
    def _create_popup_content(self, location: Dict[str, Any]) -> str:
        """
        Create HTML content for popups.
        
        Args:
            location: Location dictionary.
            
        Returns:
            HTML content for the popup.
        """
        # Basic info
        name = location.get('name', 'Unknown location')
        location_type = location.get('type', 'unknown')
        
        # Create HTML content
        content = f"<div style='width: 100%; max-width: 300px;'>"
        content += f"<h4>{name}</h4>"
        content += f"<p><strong>Type:</strong> {location_type.capitalize()}</p>"
        
        # Add relevance score if available
        if 'relevance_score' in location:
            score = location['relevance_score']
            content += f"<p><strong>Relevance:</strong> {score:.1f}/100</p>"
        
        # Add OSM data if available
        if 'osm_id' in location:
            osm_id = location['osm_id']
            osm_type = location.get('osm_type', '')
            content += f"<p><strong>OSM:</strong> {osm_type} {osm_id}</p>"
        
        # Add address if available
        if 'address' in location and isinstance(location['address'], dict):
            content += "<p><strong>Address:</strong><br>"
            address = location['address']
            address_parts = []
            
            # Add specific address components if available
            for key in ['road', 'house_number', 'city', 'county', 'state', 'country']:
                if key in address:
                    address_parts.append(address[key])
            
            content += ", ".join(address_parts)
            content += "</p>"
        
        # Add context sentences if available
        if 'context_sentences' in location and location['context_sentences']:
            sentences = location['context_sentences']
            if sentences:
                content += "<p><strong>Context:</strong><br>"
                content += f"<em>{sentences[0][:100]}...</em>"
                content += "</p>"
        
        content += "</div>"
        return content
    
    def _add_title(self, map_obj: folium.Map, title: str) -> None:
        """
        Add a title to the map.
        
        Args:
            map_obj: The folium Map object.
            title: The title text.
        """
        title_html = f'''
            <div style="position: fixed; 
                        top: 10px; left: 50px; width: 80%; 
                        background-color: white; color: black; 
                        font-size: 16px; font-weight: bold;
                        padding: 10px; border-radius: 5px;
                        z-index: 9999; text-align: center;">
                {title}
            </div>
        '''
        map_obj.get_root().html.add_child(folium.Element(title_html))
    
    def export_to_geojson(
        self,
        locations: List[Dict[str, Any]],
        output_path: str
    ) -> str:
        """
        Export location boundaries to a GeoJSON file.
        
        Args:
            locations: List of location dictionaries with boundaries.
            output_path: Path to save the GeoJSON file.
            
        Returns:
            Path to the saved GeoJSON file.
        """
        feature_collection = {
            "type": "FeatureCollection",
            "features": []
        }
        
        for location in locations:
            # Check if the location has a boundary
            if 'boundary' in location and location['boundary']:
                boundary = location['boundary']
                
                # Create a GeoJSON feature
                feature = {
                    "type": "Feature",
                    "properties": {
                        "name": location.get('name', 'Unknown location'),
                        "type": location.get('type', 'unknown'),
                        "relevance_score": location.get('relevance_score', 0)
                    },
                    "geometry": boundary
                }
                
                # Add additional properties
                for key, value in location.items():
                    if key not in ['boundary', 'polygon_geojson', 'name', 'type', 'relevance_score']:
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            feature["properties"][key] = value
                
                feature_collection["features"].append(feature)
            elif all(key in location for key in ['latitude', 'longitude']):
                # Add point for locations without boundaries
                lat = location['latitude']
                lon = location['longitude']
                
                # Create a GeoJSON feature for the point
                feature = {
                    "type": "Feature",
                    "properties": {
                        "name": location.get('name', 'Unknown location'),
                        "type": location.get('type', 'unknown'),
                        "relevance_score": location.get('relevance_score', 0),
                        "is_point": True
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    }
                }
                
                # Add additional properties
                for key, value in location.items():
                    if key not in ['latitude', 'longitude', 'boundary', 'name', 'type', 'relevance_score']:
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            feature["properties"][key] = value
                
                feature_collection["features"].append(feature)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(feature_collection, f, indent=2)
        
        logger.info(f"GeoJSON exported to {output_path}")
        return output_path

# Create a default instance
default_visualizer = MapVisualizer()
