"""
Unit tests for the BoundarySelector class.
"""

import pytest
from unittest.mock import patch

from place2polygon.core.boundary_selector import BoundarySelector


@pytest.fixture
def sample_results():
    """Sample Nominatim results with polygons."""
    return [
        {
            "place_id": 123,
            "osm_type": "relation",
            "osm_id": 456,
            "display_name": "Seattle, King County, Washington, USA",
            "class": "boundary",
            "type": "administrative",
            "geojson": {
                "type": "Polygon",
                "coordinates": [
                    [[-122.4, 47.5], [-122.2, 47.5], [-122.2, 47.7], [-122.4, 47.7], [-122.4, 47.5]]
                ]
            },
            "address": {
                "city": "Seattle",
                "county": "King County",
                "state": "Washington"
            },
            "extratags": {
                "admin_level": "8"
            }
        },
        {
            "place_id": 124,
            "osm_type": "relation",
            "osm_id": 457,
            "display_name": "King County, Washington, USA",
            "class": "boundary",
            "type": "administrative",
            "geojson": {
                "type": "Polygon",
                "coordinates": [
                    [[-122.6, 47.3], [-122.0, 47.3], [-122.0, 47.9], [-122.6, 47.9], [-122.6, 47.3]]
                ]
            },
            "address": {
                "county": "King County",
                "state": "Washington"
            },
            "extratags": {
                "admin_level": "6"
            }
        },
        {
            "place_id": 125,
            "osm_type": "relation",
            "osm_id": 458,
            "display_name": "Washington, USA",
            "class": "boundary",
            "type": "administrative",
            "geojson": {
                "type": "Polygon",
                "coordinates": [
                    [[-124.7, 45.5], [-117.0, 45.5], [-117.0, 49.0], [-124.7, 49.0], [-124.7, 45.5]]
                ]
            },
            "address": {
                "state": "Washington"
            },
            "extratags": {
                "admin_level": "4"
            }
        }
    ]


@pytest.fixture
def results_without_polygons():
    """Sample Nominatim results without polygons."""
    return [
        {
            "place_id": 123,
            "osm_type": "node",
            "osm_id": 456,
            "display_name": "Seattle, King County, Washington, USA",
            "class": "place",
            "type": "city",
            "lat": "47.6062",
            "lon": "-122.3321",
            "address": {
                "city": "Seattle",
                "county": "King County",
                "state": "Washington"
            }
        },
        {
            "place_id": 124,
            "osm_type": "node",
            "osm_id": 457,
            "display_name": "King County, Washington, USA",
            "class": "place",
            "type": "county",
            "lat": "47.5",
            "lon": "-122.3",
            "address": {
                "county": "King County",
                "state": "Washington"
            }
        }
    ]


@pytest.fixture
def mixed_results(sample_results, results_without_polygons):
    """Mix of results with and without polygons."""
    return sample_results[0:1] + results_without_polygons


class TestBoundarySelector:
    """Tests for the BoundarySelector class."""
    
    def test_init(self):
        """Test initializing the boundary selector."""
        selector = BoundarySelector()
        assert selector.prefer_smaller is True
        assert selector.max_results == 1
        
        selector = BoundarySelector(prefer_smaller=False, max_results=3)
        assert selector.prefer_smaller is False
        assert selector.max_results == 3
    
    def test_select_boundaries_empty(self):
        """Test selecting boundaries from empty input."""
        selector = BoundarySelector()
        result = selector.select_boundaries([])
        assert result == []
    
    def test_select_boundaries_no_polygons(self, results_without_polygons):
        """Test selecting boundaries when no results have polygons."""
        selector = BoundarySelector()
        result = selector.select_boundaries(results_without_polygons)
        assert result == []
    
    def test_select_boundaries_with_polygons(self, sample_results):
        """Test selecting boundaries from results with polygons."""
        selector = BoundarySelector(prefer_smaller=True)
        result = selector.select_boundaries(sample_results)
        
        # Should select the city (smallest/most specific)
        assert len(result) == 1
        assert result[0]["osm_id"] == 456  # City
        
        # Try with different preference
        selector = BoundarySelector(prefer_smaller=False)
        result = selector.select_boundaries(sample_results)
        
        # Should select the state (largest/least specific)
        assert len(result) == 1
        assert result[0]["osm_id"] == 458  # State
    
    def test_select_boundaries_multiple_results(self, sample_results):
        """Test selecting multiple boundaries."""
        selector = BoundarySelector(prefer_smaller=True, max_results=2)
        result = selector.select_boundaries(sample_results)
        
        # Should select city and county (in that order)
        assert len(result) == 2
        assert result[0]["osm_id"] == 456  # City
        assert result[1]["osm_id"] == 457  # County
    
    def test_select_boundaries_by_type(self, sample_results):
        """Test selecting boundaries by location type."""
        selector = BoundarySelector()
        
        # Filter for state
        result = selector.select_boundaries(sample_results, location_type="state")
        assert len(result) == 1
        assert result[0]["osm_id"] == 458  # State
        
        # Filter for county
        result = selector.select_boundaries(sample_results, location_type="county")
        assert len(result) == 1
        assert result[0]["osm_id"] == 457  # County
    
    def test_has_valid_polygon(self, sample_results, results_without_polygons):
        """Test checking for valid polygons."""
        selector = BoundarySelector()
        
        # Test with valid polygon
        assert selector._has_valid_polygon(sample_results[0]) is True
        
        # Test without polygon
        assert selector._has_valid_polygon(results_without_polygons[0]) is False
        
        # Test with invalid type
        invalid_result = sample_results[0].copy()
        invalid_result["geojson"] = {"type": "Point", "coordinates": [1, 2]}
        assert selector._has_valid_polygon(invalid_result) is False
    
    def test_get_admin_level(self, sample_results):
        """Test extracting admin level."""
        selector = BoundarySelector()
        
        # Test with explicit admin level
        assert selector._get_admin_level(sample_results[0]) == 8
        
        # Test without admin level
        result_without_level = sample_results[0].copy()
        result_without_level.pop("extratags")
        assert selector._get_admin_level(result_without_level) == 8  # Default for boundary
        
        # Test with natural class
        natural_result = {
            "osm_type": "way",
            "class": "natural",
            "type": "coastline"
        }
        assert selector._get_admin_level(natural_result) == 0
    
    def test_get_nested_hierarchy(self, sample_results):
        """Test organizing results into hierarchical structure."""
        selector = BoundarySelector()
        hierarchy = selector.get_nested_hierarchy(sample_results)
        
        assert "city/town" in hierarchy
        assert "county" in hierarchy
        assert "state" in hierarchy
        
        assert len(hierarchy["city/town"]) == 1
        assert len(hierarchy["county"]) == 1
        assert len(hierarchy["state"]) == 1
    
    def test_combine_boundaries(self, sample_results):
        """Test combining boundaries into a feature collection."""
        selector = BoundarySelector()
        feature_collection = selector.combine_boundaries(sample_results)
        
        assert feature_collection["type"] == "FeatureCollection"
        assert len(feature_collection["features"]) == 3
        
        # Check properties of first feature
        feature = feature_collection["features"][0]
        assert feature["type"] == "Feature"
        assert "properties" in feature
        assert "geometry" in feature
        assert feature["properties"]["name"] == sample_results[0]["display_name"]
        assert feature["properties"]["osm_id"] == sample_results[0]["osm_id"] 