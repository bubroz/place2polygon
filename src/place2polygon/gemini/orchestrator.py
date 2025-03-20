"""
Gemini orchestrator module for multi-stage polygon boundary searches.

This module uses Google's Gemini Flash 2.0 to orchestrate intelligent searches
for polygon boundaries, including parameter optimization, strategy selection,
and result validation.
"""

import os
import json
import time
from typing import Dict, List, Optional, Any, Union, Tuple
import logging

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from place2polygon.core.nominatim_client import NominatimClient, default_client
from place2polygon.gemini.documentation_provider import NominatimDocsProvider, default_provider
from place2polygon.utils.validators import validate_geojson

logger = logging.getLogger(__name__)

class GeminiOrchestrator:
    """
    Orchestrator for multi-stage polygon boundary searches using Gemini.
    
    Args:
        api_key: Google API key for Gemini.
        nominatim_client: NominatimClient instance to use.
        docs_provider: NominatimDocsProvider instance to use.
        model_name: Gemini model name to use.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        nominatim_client: NominatimClient = default_client,
        docs_provider: NominatimDocsProvider = default_provider,
        model_name: str = "gemini-1.5-flash"
    ):
        """Initialize the Gemini orchestrator."""
        self.nominatim_client = nominatim_client
        self.docs_provider = docs_provider
        self.model_name = model_name
        
        # Configure Gemini API
        api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Google API key is required for Gemini. Set GOOGLE_API_KEY env var.")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name=self.model_name)
        
        # Tracking for search attempts
        self.search_attempts = []
        self.search_logs = []
    
    def orchestrate_search(
        self,
        location_name: str,
        location_type: Optional[str] = None,
        location_context: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3
    ) -> Dict[str, Any]:
        """
        Orchestrate a multi-stage search for polygon boundaries.
        
        Args:
            location_name: Name of the location to search for.
            location_type: Type of location (city, county, state, etc.).
            location_context: Optional context about the location.
            max_attempts: Maximum number of search attempts.
            
        Returns:
            The best search result, or an empty dict if no results found.
        """
        logger.info(f"Orchestrating search for {location_name} ({location_type or 'unknown type'})")
        
        # Reset tracking for this search
        self.search_attempts = []
        self.search_logs = []
        
        # Get search strategies
        strategies = self._generate_search_strategies(location_name, location_type, location_context)
        
        # Try each strategy in order
        best_result = {}
        attempt = 0
        
        for strategy in strategies[:max_attempts]:
            attempt += 1
            logger.info(f"Attempt {attempt}/{max_attempts}: {strategy['description']}")
            
            # Execute the search
            result = self._execute_search(strategy)
            
            # Track the attempt
            self.search_attempts.append({
                "attempt": attempt,
                "strategy": strategy,
                "success": bool(result),
                "timestamp": time.time()
            })
            
            # Log detailed search information
            self.search_logs.append({
                "location_name": location_name,
                "location_type": location_type,
                "strategy": strategy,
                "success": bool(result),
                "result_summary": self._summarize_result(result),
                "timestamp": time.time()
            })
            
            # Validate the result
            if result and self._validate_result(result, location_name, location_type):
                logger.info(f"Found valid result on attempt {attempt}")
                best_result = result
                break
        
        if not best_result:
            logger.warning(f"No valid results found after {attempt} attempts")
        
        return best_result
    
    def _generate_search_strategies(
        self,
        location_name: str,
        location_type: Optional[str],
        location_context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate search strategies using Gemini.
        
        Args:
            location_name: Name of the location to search for.
            location_type: Type of location (city, county, state, etc.).
            location_context: Optional context about the location.
            
        Returns:
            A list of search strategy dictionaries.
        """
        logger.info(f"Generating search strategies for {location_name}")
        
        # Get base strategy from documentation provider
        base_strategy = self.docs_provider.get_search_strategy(location_type or "unknown")
        
        # Create prompt for Gemini
        prompt = self._create_strategy_prompt(location_name, location_type, location_context, base_strategy)
        
        try:
            # Generate strategies with Gemini
            response = self.model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.2,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=2048,
                    response_mime_type="application/json"
                )
            )
            
            # Parse the response
            strategies_json = response.text
            strategies = json.loads(strategies_json)
            
            # Add fallback strategy
            fallback_strategy = {
                "description": "Fallback search with free-form query",
                "params": {
                    "q": location_name,
                    "polygon_geojson": 1,
                    "addressdetails": 1,
                    "limit": 5
                },
                "explanation": "Direct query using the location name"
            }
            
            strategies.append(fallback_strategy)
            
            return strategies
            
        except Exception as e:
            logger.error(f"Error generating search strategies: {str(e)}")
            
            # Return default strategies if Gemini fails
            return [
                {
                    "description": f"Structured search for {location_type or 'location'} using specific parameters",
                    "params": {
                        **({"city": location_name} if location_type == "city" else {}),
                        **({"county": location_name} if location_type == "county" else {}),
                        **({"state": location_name} if location_type == "state" else {}),
                        "polygon_geojson": 1,
                        "addressdetails": 1,
                        "limit": 3
                    },
                    "explanation": f"Structured query targeting {location_type or 'location'} data"
                },
                {
                    "description": "Free-form search with location name",
                    "params": {
                        "q": location_name,
                        "polygon_geojson": 1,
                        "addressdetails": 1,
                        "limit": 5
                    },
                    "explanation": "Direct query using the location name"
                }
            ]
    
    def _create_strategy_prompt(
        self,
        location_name: str,
        location_type: Optional[str],
        location_context: Optional[Dict[str, Any]],
        base_strategy: Dict[str, Any]
    ) -> str:
        """
        Create a prompt for Gemini to generate search strategies.
        
        Args:
            location_name: Name of the location to search for.
            location_type: Type of location (city, county, state, etc.).
            location_context: Optional context about the location.
            base_strategy: Base strategy from documentation provider.
            
        Returns:
            The prompt string.
        """
        # Format context information
        context_str = ""
        if location_context:
            context_items = []
            for key, value in location_context.items():
                if key == "state" and value:
                    context_items.append(f"State: {value}")
                elif key == "country" and value:
                    context_items.append(f"Country: {value}")
                elif key == "context_sentences" and value:
                    context_items.append(f"Context: {value[0]}")
            
            if context_items:
                context_str = "\n".join(context_items)
        
        # Get best practices from documentation
        best_practices = self.docs_provider.get_best_practices()
        best_practices_str = "\n".join([f"- {bp}" for bp in best_practices[:5]])
        
        # Get parameter information
        param_info = {}
        for param in base_strategy.get("recommended_params", []):
            info = self.docs_provider.get_parameter_info(param)
            if info:
                param_info[param] = info.get("description", "")
        
        param_info_str = "\n".join([f"- {param}: {desc}" for param, desc in param_info.items()])
        
        # Assemble the prompt
        prompt = f"""
You are an expert in querying the OpenStreetMap Nominatim API to find precise polygon boundaries for locations.

TASK: Generate a list of search strategies for finding the polygon boundary of a location in OpenStreetMap via Nominatim.

LOCATION: "{location_name}"
TYPE: {location_type or "Unknown"}
{context_str}

NOMINATIM BEST PRACTICES:
{best_practices_str}

PARAMETER INFORMATION:
{param_info_str}

OUTPUT INSTRUCTIONS:
- Return a JSON array of 2-3 search strategies, ordered from most to least likely to succeed
- Each strategy should have: "description", "params", and "explanation"
- The "params" object should contain parameters to pass to the Nominatim API
- The "explanation" should explain why this strategy might work
- Focus on strategies that are likely to return polygon boundaries
- Be specific with search parameters
- Use structured parameters when possible (city, county, state, etc.)
- Include the 'polygon_geojson' parameter set to 1
- Try different parameter combinations based on location type
- For US locations, try to be specific with states and counties

RESPONSE FORMAT:
[
  {{
    "description": "First strategy description",
    "params": {{
      "param1": "value1",
      "param2": "value2",
      "polygon_geojson": 1
    }},
    "explanation": "Why this strategy might work"
  }},
  ...
]
        """
        
        return prompt
    
    def _execute_search(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a search strategy using the Nominatim client.
        
        Args:
            strategy: The search strategy to execute.
            
        Returns:
            The best search result, or an empty dict if no results found.
        """
        try:
            # Get search parameters
            params = strategy.get("params", {})
            
            # Execute the search
            logger.info(f"Executing search with params: {params}")
            results = self.nominatim_client.search(**params)
            
            # Return the best result (first result)
            if results:
                return results[0]
            else:
                logger.warning("No results found for search")
                return {}
                
        except Exception as e:
            logger.error(f"Error executing search: {str(e)}")
            return {}
    
    def _validate_result(
        self,
        result: Dict[str, Any],
        location_name: str,
        location_type: Optional[str]
    ) -> bool:
        """
        Validate a search result using Gemini.
        
        Args:
            result: The search result to validate.
            location_name: Name of the location that was searched.
            location_type: Type of location that was searched.
            
        Returns:
            True if the result is valid, False otherwise.
        """
        # Check if result has a polygon
        if "geojson" not in result:
            logger.warning("Result does not have a geojson field")
            return False
        
        # Validate GeoJSON
        if not validate_geojson(result["geojson"]):
            logger.warning("Invalid GeoJSON in result")
            return False
        
        # Check if it's a polygon type
        geojson_type = result["geojson"].get("type")
        if geojson_type not in ["Polygon", "MultiPolygon"]:
            logger.warning(f"Result has non-polygon GeoJSON type: {geojson_type}")
            return False
        
        try:
            # Create validation prompt
            prompt = self._create_validation_prompt(result, location_name, location_type)
            
            # Validate with Gemini
            response = self.model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.1,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=128,
                    response_mime_type="application/json"
                )
            )
            
            # Parse the response
            validation_json = response.text
            validation = json.loads(validation_json)
            
            is_valid = validation.get("is_valid", False)
            confidence = validation.get("confidence", 0)
            
            logger.info(f"Validation result: valid={is_valid}, confidence={confidence}")
            
            # Consider valid if confidence is high enough
            return is_valid and confidence >= 70
            
        except Exception as e:
            logger.error(f"Error validating result: {str(e)}")
            
            # Fall back to basic validation if Gemini fails
            return self._basic_validate_result(result, location_name, location_type)
    
    def _create_validation_prompt(
        self,
        result: Dict[str, Any],
        location_name: str,
        location_type: Optional[str]
    ) -> str:
        """
        Create a prompt for Gemini to validate a search result.
        
        Args:
            result: The search result to validate.
            location_name: Name of the location that was searched.
            location_type: Type of location that was searched.
            
        Returns:
            The prompt string.
        """
        # Extract info from result
        display_name = result.get("display_name", "")
        osm_type = result.get("osm_type", "")
        osm_class = result.get("class", "")
        
        # Extract address components
        address = result.get("address", {})
        address_str = "\n".join([f"- {k}: {v}" for k, v in address.items()])
        
        # Assemble the prompt
        prompt = f"""
You are an expert in validating OpenStreetMap location data.

TASK: Validate whether this Nominatim API result matches the location we're looking for.

SEARCH TARGET:
- Name: "{location_name}"
- Type: {location_type or "Unknown"}

RESULT INFORMATION:
- Display Name: "{display_name}"
- OSM Type: {osm_type}
- Class: {osm_class}

ADDRESS COMPONENTS:
{address_str}

OUTPUT INSTRUCTIONS:
- Return a JSON object with "is_valid" (boolean), "confidence" (0-100), and "reason" (string)
- Check if the name in the result matches or contains the search target
- Check if the type matches (city, county, state, etc.)
- Check if address components make sense for this location
- Consider both the display name and individual address components

RESPONSE FORMAT:
{{
  "is_valid": true/false,
  "confidence": 0-100,
  "reason": "Explanation of your decision"
}}
        """
        
        return prompt
    
    def _basic_validate_result(
        self,
        result: Dict[str, Any],
        location_name: str,
        location_type: Optional[str]
    ) -> bool:
        """
        Perform basic validation of a search result.
        
        Args:
            result: The search result to validate.
            location_name: Name of the location that was searched.
            location_type: Type of location that was searched.
            
        Returns:
            True if the result is valid, False otherwise.
        """
        # Check if the display name contains the location name
        display_name = result.get("display_name", "").lower()
        if location_name.lower() not in display_name:
            logger.warning(f"Location name '{location_name}' not found in display name: {display_name}")
            
            # Check if it's in address components as a fallback
            address = result.get("address", {})
            found_in_address = False
            
            for val in address.values():
                if isinstance(val, str) and location_name.lower() in val.lower():
                    found_in_address = True
                    break
            
            if not found_in_address:
                return False
        
        # If location type is specified, check if it's in the result
        if location_type:
            # Check in class
            osm_class = result.get("class", "").lower()
            if location_type.lower() in osm_class:
                return True
            
            # Check in display name
            if location_type.lower() in display_name:
                return True
            
            # Check in address components
            address = result.get("address", {})
            for key, val in address.items():
                if (location_type.lower() in key.lower() or 
                    (isinstance(val, str) and location_type.lower() in val.lower())):
                    return True
            
            # Special handling for common types
            if location_type.lower() == "city":
                if "city" in address or "town" in address or "village" in address:
                    return True
            elif location_type.lower() == "state":
                if "state" in address or "province" in address:
                    return True
            elif location_type.lower() == "county":
                if "county" in address or "district" in address:
                    return True
        
        # Default to true if we can't determine
        return True
    
    def _summarize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a summary of a search result for logging.
        
        Args:
            result: The search result to summarize.
            
        Returns:
            A dictionary of summarized result information.
        """
        if not result:
            return {"found": False}
        
        return {
            "found": True,
            "display_name": result.get("display_name", ""),
            "osm_id": result.get("osm_id", ""),
            "osm_type": result.get("osm_type", ""),
            "class": result.get("class", ""),
            "has_polygon": "geojson" in result,
            "polygon_type": result.get("geojson", {}).get("type", "None"),
        }
    
    def get_search_logs(self) -> List[Dict[str, Any]]:
        """
        Get logs of search attempts.
        
        Returns:
            A list of search log dictionaries.
        """
        return self.search_logs

# Create a default instance if Google API key is available
try:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        default_orchestrator = GeminiOrchestrator(api_key=api_key)
    else:
        logger.warning("No Google API key found in environment. Default orchestrator not created.")
        default_orchestrator = None
except Exception as e:
    logger.error(f"Error creating default orchestrator: {str(e)}")
    default_orchestrator = None
