"""
Documentation provider module for Nominatim API documentation.

This module fetches and parses Nominatim API documentation to provide structured
information about API parameters, options, and best practices.
"""

import os
import json
from typing import Dict, List, Optional, Any, Union
import logging
import httpx
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Base URL for Nominatim documentation
NOMINATIM_DOCS_URL = "https://nominatim.org/release-docs/latest/api"

# Local cache path for documentation
DEFAULT_CACHE_PATH = "nominatim_docs_cache.json"

class NominatimDocsProvider:
    """
    Provider for Nominatim API documentation.
    
    This class fetches, parses, and provides structured information about
    Nominatim API parameters, options, and best practices.
    
    Args:
        cache_path: Path to the local documentation cache file.
        base_url: Base URL for Nominatim documentation.
        refresh_cache: Whether to refresh the cache on initialization.
    """
    
    def __init__(
        self,
        cache_path: str = DEFAULT_CACHE_PATH,
        base_url: str = NOMINATIM_DOCS_URL,
        refresh_cache: bool = False
    ):
        """Initialize the documentation provider."""
        self.cache_path = cache_path
        self.base_url = base_url
        self.docs_cache: Dict[str, Any] = {}
        
        # Load docs from cache or fetch if needed
        if not refresh_cache and os.path.exists(cache_path):
            self._load_cache()
        else:
            self._fetch_and_cache_docs()
    
    def _load_cache(self) -> None:
        """Load documentation from cache."""
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                self.docs_cache = json.load(f)
            logger.info(f"Loaded Nominatim documentation from cache: {self.cache_path}")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading documentation cache: {str(e)}")
            self.docs_cache = {}
    
    def _save_cache(self) -> None:
        """Save documentation to cache."""
        try:
            cache_dir = os.path.dirname(self.cache_path)
            if cache_dir and not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
                
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.docs_cache, f, indent=2)
            logger.info(f"Saved Nominatim documentation to cache: {self.cache_path}")
        except IOError as e:
            logger.error(f"Error saving documentation cache: {str(e)}")
    
    def _fetch_and_cache_docs(self) -> None:
        """Fetch and cache Nominatim documentation."""
        logger.info("Fetching Nominatim documentation...")
        
        # Define sections to fetch
        sections = {
            "search": f"{self.base_url}/Search.html",
            "lookup": f"{self.base_url}/Lookup.html",
            "reverse": f"{self.base_url}/Reverse.html",
            "status": f"{self.base_url}/Status.html",
            "output": f"{self.base_url}/Output.html",
            "faq": f"{self.base_url}/Faq.html",
        }
        
        # Fetch and parse each section
        for section_name, url in sections.items():
            try:
                content = self._fetch_url(url)
                if content:
                    self.docs_cache[section_name] = self._parse_documentation(content, section_name)
            except Exception as e:
                logger.error(f"Error fetching {section_name} documentation: {str(e)}")
        
        # Save to cache
        self._save_cache()
    
    def _fetch_url(self, url: str) -> Optional[str]:
        """
        Fetch content from a URL.
        
        Args:
            url: The URL to fetch.
            
        Returns:
            The content of the URL, or None if the request fails.
        """
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {str(e)}")
            return None
    
    def _parse_documentation(self, content: str, section_name: str) -> Dict[str, Any]:
        """
        Parse HTML documentation into structured data.
        
        Args:
            content: The HTML content to parse.
            section_name: The name of the section being parsed.
            
        Returns:
            A dictionary of parsed documentation.
        """
        # Parse based on section type
        if section_name == "search":
            return self._parse_search_docs(content)
        elif section_name == "lookup":
            return self._parse_lookup_docs(content)
        elif section_name == "reverse":
            return self._parse_reverse_docs(content)
        elif section_name == "output":
            return self._parse_output_docs(content)
        elif section_name == "faq":
            return self._parse_faq_docs(content)
        else:
            # Default parsing for other sections
            return {"raw_content": content}
    
    def _parse_search_docs(self, content: str) -> Dict[str, Any]:
        """
        Parse search API documentation.
        
        Args:
            content: The HTML content to parse.
            
        Returns:
            A dictionary of parsed search documentation.
        """
        result = {
            "parameters": {},
            "best_practices": [],
            "examples": []
        }
        
        # Extract parameter tables
        param_tables = re.findall(r'<h3[^>]*>([^<]+)</h3>.*?<table[^>]*>(.*?)</table>', content, re.DOTALL)
        
        for section_title, table_html in param_tables:
            section_title = section_title.strip()
            
            # Extract parameters from the table
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
            for row in rows[1:]:  # Skip header row
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                if len(cells) >= 2:
                    param_name = re.sub(r'<[^>]+>', '', cells[0]).strip()
                    param_desc = re.sub(r'<[^>]+>', ' ', cells[1]).strip()
                    param_desc = re.sub(r'\s+', ' ', param_desc)
                    
                    if param_name:
                        result["parameters"][param_name] = {
                            "description": param_desc,
                            "section": section_title
                        }
        
        # Extract best practices
        best_practices = re.findall(r'<div class="admonition note">.*?<p>(.*?)</p>', content, re.DOTALL)
        result["best_practices"] = [re.sub(r'<[^>]+>', ' ', bp).strip() for bp in best_practices]
        
        # Extract examples
        examples = re.findall(r'<div class="highlight-default notranslate">.*?<pre>(.*?)</pre>', content, re.DOTALL)
        result["examples"] = [re.sub(r'<[^>]+>', '', ex).strip() for ex in examples]
        
        return result
    
    def _parse_lookup_docs(self, content: str) -> Dict[str, Any]:
        """Parse lookup API documentation."""
        # Similar to _parse_search_docs but for lookup documentation
        return self._parse_search_docs(content)  # For simplicity, reuse the same parser
    
    def _parse_reverse_docs(self, content: str) -> Dict[str, Any]:
        """Parse reverse geocoding API documentation."""
        # Similar to _parse_search_docs but for reverse geocoding documentation
        return self._parse_search_docs(content)  # For simplicity, reuse the same parser
    
    def _parse_output_docs(self, content: str) -> Dict[str, Any]:
        """Parse output format documentation."""
        result = {
            "formats": {},
            "notes": []
        }
        
        # Extract format descriptions
        format_sections = re.findall(r'<h3[^>]*>([^<]+)</h3>.*?<p>(.*?)</p>', content, re.DOTALL)
        
        for format_name, description in format_sections:
            format_name = format_name.strip()
            description = re.sub(r'<[^>]+>', ' ', description).strip()
            description = re.sub(r'\s+', ' ', description)
            
            if format_name:
                result["formats"][format_name] = description
        
        # Extract notes
        notes = re.findall(r'<div class="admonition note">.*?<p>(.*?)</p>', content, re.DOTALL)
        result["notes"] = [re.sub(r'<[^>]+>', ' ', note).strip() for note in notes]
        
        return result
    
    def _parse_faq_docs(self, content: str) -> Dict[str, Any]:
        """Parse FAQ documentation."""
        result = {
            "questions": []
        }
        
        # Extract FAQ items
        faq_items = re.findall(r'<div class="section" id="[^"]*">.*?<h3>(.*?)</h3>.*?<p>(.*?)</p>', content, re.DOTALL)
        
        for question, answer in faq_items:
            question = re.sub(r'<[^>]+>', '', question).strip()
            answer = re.sub(r'<[^>]+>', ' ', answer).strip()
            answer = re.sub(r'\s+', ' ', answer)
            
            if question and answer:
                result["questions"].append({
                    "question": question,
                    "answer": answer
                })
        
        return result
    
    def get_parameter_info(self, param_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific Nominatim API parameter.
        
        Args:
            param_name: The name of the parameter to look up.
            
        Returns:
            A dictionary of parameter information, or None if not found.
        """
        # Look in search, lookup, and reverse sections
        for section_name in ["search", "lookup", "reverse"]:
            section = self.docs_cache.get(section_name, {})
            parameters = section.get("parameters", {})
            
            if param_name in parameters:
                return parameters[param_name]
        
        return None
    
    def get_best_practices(self) -> List[str]:
        """
        Get a list of best practices for Nominatim API usage.
        
        Returns:
            A list of best practice strings.
        """
        best_practices = []
        
        # Collect best practices from all sections
        for section_name in ["search", "lookup", "reverse"]:
            section = self.docs_cache.get(section_name, {})
            if "best_practices" in section:
                best_practices.extend(section["best_practices"])
        
        return best_practices
    
    def get_examples(self, api_type: str) -> List[str]:
        """
        Get examples for a specific API type.
        
        Args:
            api_type: The API type (search, lookup, reverse).
            
        Returns:
            A list of example strings.
        """
        if api_type in self.docs_cache and "examples" in self.docs_cache[api_type]:
            return self.docs_cache[api_type]["examples"]
        
        return []
    
    def get_parameters_for_api(self, api_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all parameters for a specific API type.
        
        Args:
            api_type: The API type (search, lookup, reverse).
            
        Returns:
            A dictionary of parameter information.
        """
        if api_type in self.docs_cache and "parameters" in self.docs_cache[api_type]:
            return self.docs_cache[api_type]["parameters"]
        
        return {}
    
    def get_search_strategy(self, location_type: str) -> Dict[str, Any]:
        """
        Get recommended search strategy for a specific location type.
        
        Args:
            location_type: The type of location (city, county, state, etc.).
            
        Returns:
            A dictionary of search strategy recommendations.
        """
        # Define basic strategies for different location types
        strategies = {
            "country": {
                "params": {
                    "country": True,
                    "polygon_geojson": 1,
                    "limit": 1
                },
                "recommended_params": ["country"],
                "fallback_params": ["q"]
            },
            "state": {
                "params": {
                    "state": True,
                    "country": "us",  # For US focus
                    "polygon_geojson": 1,
                    "limit": 1
                },
                "recommended_params": ["state", "country"],
                "fallback_params": ["q"]
            },
            "county": {
                "params": {
                    "county": True,
                    "state": True,
                    "country": "us",  # For US focus
                    "polygon_geojson": 1,
                    "limit": 1
                },
                "recommended_params": ["county", "state"],
                "fallback_params": ["q"]
            },
            "city": {
                "params": {
                    "city": True,
                    "state": True,
                    "country": "us",  # For US focus
                    "polygon_geojson": 1,
                    "limit": 1
                },
                "recommended_params": ["city", "state"],
                "fallback_params": ["q"]
            },
            "neighborhood": {
                "params": {
                    "q": True,
                    "city": True,
                    "state": True,
                    "country": "us",  # For US focus
                    "polygon_geojson": 1,
                    "limit": 5
                },
                "recommended_params": ["q", "city", "state"],
                "fallback_params": ["q"]
            }
        }
        
        # Return strategy for the requested location type, or a default
        return strategies.get(location_type.lower(), {
            "params": {
                "q": True,
                "polygon_geojson": 1,
                "limit": 5
            },
            "recommended_params": ["q"],
            "fallback_params": ["q"]
        })
    
    def get_search_strategies(self) -> Dict[str, Any]:
        """
        Get a collection of common search strategies.
        
        Returns:
            Dictionary containing recommended search strategies for different location types.
        """
        strategies = {
            "common_params": {
                "polygon_geojson": 1,
                "addressdetails": 1,
                "extratags": True,
                "limit": 5
            },
            "city_strategy": self.get_search_strategy("city"),
            "state_strategy": self.get_search_strategy("state"),
            "county_strategy": self.get_search_strategy("county"),
            "country_strategy": self.get_search_strategy("country"),
            "recommended_params": [
                "q", "city", "county", "state", "country", "postalcode",
                "polygon_geojson", "addressdetails", "extratags", "limit"
            ],
            "strategies": [
                {
                    "description": "Basic query with location name",
                    "params": {
                        "q": "<location_name>",
                        "polygon_geojson": 1,
                        "addressdetails": 1,
                        "limit": 5
                    },
                    "explanation": "Simple free-form search by name"
                },
                {
                    "description": "Structured search with location type",
                    "params": {
                        "<location_type>": "<location_name>",
                        "polygon_geojson": 1,
                        "addressdetails": 1,
                        "limit": 3
                    },
                    "explanation": "Targeted search using the specific location type field"
                },
                {
                    "description": "Search with OSM tags",
                    "params": {
                        "q": "<location_name>",
                        "polygon_geojson": 1,
                        "addressdetails": 1,
                        "extratags": 1,
                        "limit": 5
                    },
                    "explanation": "Search with extra OSM tags for better filtering"
                }
            ]
        }
        
        return strategies

# Create a default instance
default_provider = NominatimDocsProvider()
