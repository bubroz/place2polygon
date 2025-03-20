"""
Configuration file for pytest providing fixtures for testing Place2Polygon.

This file contains shared fixtures that can be used across all tests.
"""

import os
import json
import sqlite3
import tempfile
from typing import Dict, List, Any, Generator, Tuple
from unittest.mock import MagicMock
import pytest

import place2polygon
from place2polygon.core import LocationExtractor, NominatimClient, BoundarySelector, MapVisualizer
from place2polygon.cache import SQLiteCache, CacheManager


@pytest.fixture
def sample_text() -> str:
    """Sample text with location mentions for testing."""
    return """
    Seattle is a beautiful city in Washington state. The Space Needle is a famous landmark.
    Portland, Oregon is known for its roses and coffee. 
    San Francisco, California is famous for the Golden Gate Bridge and Silicon Valley nearby.
    New York City is the most populous city in the United States, located in New York state.
    """


@pytest.fixture
def sample_locations() -> List[Dict[str, Any]]:
    """Sample extracted locations for testing."""
    return [
        {
            "name": "Seattle",
            "original_name": "Seattle",
            "type": "city",
            "char_start": 5,
            "char_end": 12,
            "sentence": "Seattle is a beautiful city in Washington state.",
            "occurrences": 1,
            "mentions": ["Seattle"],
            "relevance_score": 75.5,
        },
        {
            "name": "Washington",
            "original_name": "Washington",
            "type": "state",
            "char_start": 37,
            "char_end": 47,
            "sentence": "Seattle is a beautiful city in Washington state.",
            "occurrences": 1,
            "mentions": ["Washington"],
            "relevance_score": 65.2,
        },
        {
            "name": "Portland, Oregon",
            "original_name": "Portland, Oregon",
            "type": "city",
            "char_start": 100,
            "char_end": 116,
            "sentence": "Portland, Oregon is known for its roses and coffee.",
            "occurrences": 1,
            "mentions": ["Portland, Oregon"],
            "relevance_score": 70.3,
        }
    ]


@pytest.fixture
def sample_nominatim_result() -> Dict[str, Any]:
    """Sample Nominatim API result."""
    return {
        "place_id": 12345,
        "licence": "Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright",
        "osm_type": "relation",
        "osm_id": 237385,
        "lat": "47.6062095",
        "lon": "-122.3320708",
        "display_name": "Seattle, King County, Washington, United States",
        "class": "boundary",
        "type": "administrative",
        "importance": 0.7342,
        "address": {
            "city": "Seattle",
            "county": "King County",
            "state": "Washington",
            "country": "United States"
        },
        "geojson": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-122.4, 47.5],
                    [-122.2, 47.5],
                    [-122.2, 47.7],
                    [-122.4, 47.7],
                    [-122.4, 47.5]
                ]
            ]
        }
    }


@pytest.fixture
def mock_extractor() -> LocationExtractor:
    """Mock LocationExtractor that returns predefined locations."""
    extractor = MagicMock(spec=LocationExtractor)
    
    def mock_extract_locations(text):
        # Return sample locations regardless of input text
        locations = [
            {
                "name": "Seattle",
                "type": "city",
                "relevance_score": 75.5,
            },
            {
                "name": "Washington",
                "type": "state",
                "relevance_score": 65.2,
            }
        ]
        return locations
    
    extractor.extract_locations.side_effect = mock_extract_locations
    return extractor


@pytest.fixture
def mock_nominatim_client(sample_nominatim_result) -> NominatimClient:
    """Mock NominatimClient that returns predefined results."""
    client = MagicMock(spec=NominatimClient)
    client.search.return_value = [sample_nominatim_result]
    return client


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Temporary SQLite database path for testing."""
    _, path = tempfile.mkstemp(suffix='.db')
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def temp_cache(temp_db_path) -> SQLiteCache:
    """Temporary SQLiteCache for testing."""
    return SQLiteCache(db_path=temp_db_path, default_ttl=1)


@pytest.fixture
def temp_cache_manager(temp_cache) -> CacheManager:
    """Temporary CacheManager for testing."""
    return CacheManager(cache=temp_cache, auto_cleanup_interval=0)


@pytest.fixture
def temp_html_path() -> Generator[str, None, None]:
    """Temporary HTML file path for testing map output."""
    _, path = tempfile.mkstemp(suffix='.html')
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def temp_geojson_path() -> Generator[str, None, None]:
    """Temporary GeoJSON file path for testing export."""
    _, path = tempfile.mkstemp(suffix='.geojson')
    yield path
    if os.path.exists(path):
        os.unlink(path) 