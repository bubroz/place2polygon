"""
Integration tests for the end-to-end workflow.
"""

import os
import json
from unittest.mock import patch, MagicMock
import pytest

import place2polygon
from place2polygon import extract_and_map_locations, extract_locations, find_polygon_boundaries, create_map


class TestEndToEnd:
    """Integration tests for the end-to-end workflow."""
    
    @patch("place2polygon.core.nominatim_client.NominatimClient.search")
    def test_extract_and_map_locations(self, mock_search, sample_text, sample_nominatim_result, temp_html_path):
        """Test the full end-to-end workflow."""
        # Mock Nominatim search to return our sample result
        mock_search.return_value = [sample_nominatim_result]
        
        # Run the full workflow
        locations, map_path = extract_and_map_locations(
            text=sample_text,
            output_path=temp_html_path,
            use_gemini=False  # Disable Gemini for testing
        )
        
        # Verify locations were extracted
        assert len(locations) > 0
        
        # Verify the map was created
        assert os.path.exists(map_path)
        assert map_path == temp_html_path
        
        # Verify Nominatim was called
        mock_search.assert_called()
        
        # Check that locations have the right structure
        for location in locations:
            # Each location should have basic attributes
            assert "name" in location
            assert "type" in location
            assert "relevance_score" in location
    
    @patch("place2polygon.core.location_extractor.LocationExtractor.extract_locations")
    @patch("place2polygon.core.location_extractor.LocationExtractor.enhance_locations_with_context")
    def test_extract_locations(self, mock_enhance, mock_extract, sample_text, sample_locations):
        """Test the location extraction step."""
        # Mock the extractor
        mock_extract.return_value = sample_locations
        mock_enhance.return_value = sample_locations
        
        # Run the extraction
        locations = extract_locations(sample_text)
        
        # Verify extraction was performed
        mock_extract.assert_called_once_with(sample_text)
        
        # Verify enhancement was performed when locations are found
        mock_enhance.assert_called_once()
        
        # Verify we get the expected locations
        assert locations == sample_locations
    
    @patch("place2polygon.core.nominatim_client.NominatimClient.search")
    def test_find_polygon_boundaries(self, mock_search, sample_locations, sample_nominatim_result, temp_cache):
        """Test finding polygon boundaries."""
        # Mock Nominatim search to return our sample result
        mock_search.return_value = [sample_nominatim_result]
        
        # Create a cache manager with our test cache
        from place2polygon.cache import CacheManager
        cache_manager = CacheManager(cache=temp_cache)
        
        # Run the boundary search
        enriched_locations = find_polygon_boundaries(
            locations=sample_locations,
            cache_manager=cache_manager
        )
        
        # Verify Nominatim was called
        assert mock_search.call_count == len(sample_locations)
        
        # Verify boundaries were added to locations
        for location in enriched_locations:
            if "boundary" in location:
                assert location["boundary"] == sample_nominatim_result["geojson"]
                assert "display_name" in location
                assert "osm_id" in location
    
    def test_create_map(self, temp_html_path):
        """Test creating a map."""
        # Sample locations with boundaries
        locations = [
            {
                "name": "Seattle",
                "type": "city",
                "boundary": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-122.4, 47.5], [-122.2, 47.5], [-122.2, 47.7], [-122.4, 47.7], [-122.4, 47.5]]
                    ]
                }
            },
            {
                "name": "Portland",
                "type": "city",
                "latitude": 45.5231,
                "longitude": -122.6765
            }
        ]
        
        # Create the map
        map_path = create_map(locations, output_path=temp_html_path)
        
        # Verify the map was created
        assert os.path.exists(map_path)
        assert map_path == temp_html_path
        
        # Check file size to ensure it's a real HTML file
        assert os.path.getsize(map_path) > 0
    
    @patch("place2polygon.find_polygons_with_gemini")
    def test_use_gemini_option(self, mock_find_polygons, sample_text, sample_locations, temp_html_path):
        """Test the use_gemini option in extract_and_map_locations."""
        # Mock functions to avoid actual API calls
        with patch("place2polygon.extract_locations", return_value=sample_locations):
            with patch("place2polygon.create_map", return_value=temp_html_path):
                # Test with Gemini enabled
                extract_and_map_locations(
                    text=sample_text,
                    output_path=temp_html_path,
                    use_gemini=True
                )
                # Verify Gemini search was used
                mock_find_polygons.assert_called_once()
                
                # Reset mock
                mock_find_polygons.reset_mock()
                
                # Test with Gemini disabled
                with patch("place2polygon.find_polygon_boundaries") as mock_find_boundaries:
                    extract_and_map_locations(
                        text=sample_text,
                        output_path=temp_html_path,
                        use_gemini=False
                    )
                    # Verify regular search was used instead
                    mock_find_polygons.assert_not_called()
                    mock_find_boundaries.assert_called_once() 