"""
Gemini orchestrator module for multi-stage polygon boundary searches.

This module uses Google's Gemini Flash 2.0 to orchestrate intelligent searches
for polygon boundaries, including parameter optimization, strategy selection,
and result validation.
"""

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Any, Union, Tuple

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
        model_name: str = "gemini-2.0-flash"
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
    
    def _parse_gemini_response(self, response: str) -> Any:
        """
        Parse a response from Gemini, attempting multiple methods if needed.
        
        Args:
            response: The raw response string from Gemini
            
        Returns:
            The parsed response object
        
        Raises:
            ValueError: If parsing fails after all attempts
        """
        # First, try to parse the response directly as JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.debug("Initial JSON parsing failed, attempting cleanup")
        
        # Try to extract a JSON object if it's embedded in text
        try:
            # Find content between first { and last }
            match = re.search(r'(\{.*\})', response, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            
            # Find content between first [ and last ]
            match = re.search(r'(\[.*\])', response, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except (json.JSONDecodeError, AttributeError):
            logger.debug("JSON extraction failed, attempting line-by-line parsing")
        
        # Try to clean up the response by removing non-JSON lines
        try:
            # Remove markdown code blocks
            clean_response = re.sub(r'```(?:json)?(.*?)```', r'\1', response, flags=re.DOTALL)
            # Remove explanatory text before and after
            clean_response = re.sub(r'^.*?(\[|\{)', r'\1', clean_response, flags=re.DOTALL)
            clean_response = re.sub(r'(\]|\}).*?$', r'\1', clean_response, flags=re.DOTALL)
            return json.loads(clean_response)
        except json.JSONDecodeError:
            logger.debug("Cleanup parsing failed, using fallback")
        
        # If all parsing attempts fail, return a default structure
        # This ensures we don't completely fail but can still fall back to basic strategies
        logger.warning("All JSON parsing attempts failed, using fallback default structure")
        
        # Create a default structure based on what we're expecting
        if isinstance(response, str):
            if "description" in response and "params" in response:
                # Likely a search strategy response
                return [
                    {
                        "description": "Structured search with query parameter",
                        "params": {
                            "q": "SEARCH_TERM",
                            "polygon_geojson": 1,
                            "addressdetails": 1,
                            "limit": 5
                        }
                    }
                ]
            elif "is_match" in response:
                # Likely a validation response
                return {
                    "is_match": False,
                    "confidence": 0,
                    "reasoning": "Failed to parse response"
                }
        
        # If we can't determine the type, just return a generic search strategy
        return [
            {
                "description": "Generic fallback search",
                "params": {
                    "q": "SEARCH_TERM",
                    "polygon_geojson": 1,
                    "addressdetails": 1,
                    "limit": 5
                }
            }
        ]

    def _generate_search_strategies(
        self,
        location_name: str,
        location_type: Optional[str],
        location_context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate search strategies for the location using Gemini.
        
        Args:
            location_name: Name of the location to search for.
            location_type: Type of location (city, county, state, etc.).
            location_context: Optional context about the location.
            
        Returns:
            List of search strategies to try.
        """
        try:
            # Get base strategy options from docs
            base_strategies = self.docs_provider.get_search_strategies()
            
            # Use first strategy as a base
            if not base_strategies:
                raise ValueError("No base strategies available")
                
            base_strategy = base_strategies[0]
            
            # Generate prompt
            prompt = self._create_strategy_prompt(
                location_name, location_type, location_context, base_strategy
            )
            
            # Generate response
            response = self._generate_response(prompt)
            
            # Parse response - use our robust parser
            strategies = self._parse_gemini_response(response)
            
            # Ensure strategies is a list
            if not isinstance(strategies, list):
                logger.warning(f"Unexpected response format from Gemini: {type(strategies)}")
                raise ValueError(f"Invalid strategies format: {type(strategies)}")
            
            # Add default params if missing
            for strategy in strategies:
                if "params" in strategy:
                    if "polygon_geojson" not in strategy["params"]:
                        strategy["params"]["polygon_geojson"] = 1
                    if "addressdetails" not in strategy["params"]:
                        strategy["params"]["addressdetails"] = 1
                    
                    # Replace SEARCH_TERM placeholder with actual location name
                    for param, value in strategy["params"].items():
                        if value == "SEARCH_TERM":
                            strategy["params"][param] = location_name
                        
            return strategies
        except Exception as e:
            logger.error(f"Error generating search strategies: {str(e)}")
            
            # Return basic strategies if Gemini fails
            # This ensures we always have fallback options
            return [
                {
                    "description": "Structured search for city using specific parameters",
                    "params": {
                        "polygon_geojson": 1,
                        "addressdetails": 1, 
                        "limit": 3,
                        "city": location_name
                    }
                },
                {
                    "description": "Free-form search with location name",
                    "params": {
                        "q": location_name,
                        "polygon_geojson": 1,
                        "addressdetails": 1,
                        "limit": 5
                    }
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
        # Format location type for the prompt
        location_type_str = location_type or "Unknown"
        
        # Format context information
        context_str = ""
        if location_context:
            context_items = []
            for key, value in location_context.items():
                if key == "nearby_locations" and value:
                    context_items.append(f"Nearby locations: {', '.join(value[:3])}")
                elif key == "relevance_score" and value:
                    context_items.append(f"Relevance score: {value}")
            
            if context_items:
                context_str = "\n".join(context_items)
        
        # Create a simplified prompt that asks for very structured output
        prompt = f"""
You are generating search strategies to find the polygon boundary for a location using the Nominatim API.

LOCATION: {location_name}
TYPE: {location_type_str}
{context_str}

TASK:
Generate 2 search strategies for finding the polygon boundary of this location.

SEARCH PARAMETERS:
- Always include "polygon_geojson": 1 to request polygon data
- Always include "addressdetails": 1 to get address details
- Use "q" parameter for free-form searches
- Use specific parameters like "city", "county", "state" for structured searches

OUTPUT FORMAT:
Return a JSON array containing exactly 2 strategy objects with this exact structure:
[
  {{
    "description": "Strategy 1 description",
    "params": {{
      "key1": "value1",
      "key2": "value2",
      "polygon_geojson": 1,
      "addressdetails": 1
    }}
  }},
  {{
    "description": "Strategy 2 description",
    "params": {{
      "key1": "value1",
      "key2": "value2",
      "polygon_geojson": 1,
      "addressdetails": 1
    }}
  }}
]

Do not include any explanations or additional text, just return the JSON array.
"""
        
        return prompt
    
    def _execute_search(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a search strategy and return the best result.
        
        Args:
            strategy: The search strategy to execute.
            
        Returns:
            The best search result, or an empty dict if no results found.
        """
        try:
            params = strategy.get("params", {})
            logger.info(f"Executing search with params: {params}")
            
            # Execute the search
            results = self.nominatim_client.search(**params)
            
            if not results:
                return {}
            
            # Get the best result by importance score
            best_result = max(results, key=lambda x: x.get("importance", 0))
            
            # Basic validation
            if not self._basic_validate_result(best_result, params.get("q", ""), params.get("type")):
                return {}
            
            return best_result
        except Exception as e:
            logger.error(f"Error executing search: {str(e)}")
            return {}
    
    def _create_structured_search_params(self, location_name: str, location_type: Optional[str]) -> Dict[str, Any]:
        """
        Create structured search parameters based on location type.
        
        Args:
            location_name: Name of the location to search for.
            location_type: Type of location (city, county, state, etc.).
            
        Returns:
            Dictionary of search parameters.
        """
        params = {
            "polygon_geojson": 1,
            "addressdetails": 1,
            "limit": 3
        }
        
        # Add structured parameters based on type
        if location_type == "city":
            params["city"] = location_name
        elif location_type == "county":
            params["county"] = location_name
        elif location_type == "state":
            params["state"] = location_name
        elif location_type == "country":
            params["country"] = location_name
        else:
            # If no specific type, use free-form query
            params["q"] = location_name
            params["limit"] = 5
            
        return params
    
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
            logger.warning(f"Invalid GeoJSON for {location_name}")
            return False
        
        # Skip validation if geojson is not a polygon
        if result["geojson"]["type"] not in ["Polygon", "MultiPolygon"]:
            geojson_type = result["geojson"]["type"]
            logger.warning(f"Result has non-polygon GeoJSON type: {geojson_type}")
            return False
            
        # Check if location name is in display name
        display_name = result.get("display_name", "")
        if location_name.lower() not in display_name.lower() and len(location_name) > 3:
            logger.warning(f"Location name '{location_name}' not found in display name: {display_name}")
            
            # Continue with validation despite name mismatch - let Gemini decide
        
        try:
            # Generate prompt
            prompt = self._create_validation_prompt(result, location_name, location_type)
            
            # Generate response
            response = self._generate_response(prompt)
            
            # Parse response using our robust parser
            validation = self._parse_gemini_response(response)
            
            # Extract validation result
            is_valid = validation.get("is_match", False)
            confidence = validation.get("confidence", 0)
            
            logger.info(f"Validation result: valid={is_valid}, confidence={confidence}")
            
            # Only consider valid if confidence is high enough
            return is_valid and confidence >= 80
        except Exception as e:
            logger.error(f"Error validating result: {str(e)}")
            
            # Default to name-based validation if Gemini fails
            # This ensures we don't completely fail just because of validation
            display_name = result.get("display_name", "").lower()
            address = result.get("address", {})
            
            # Basic validation logic
            if location_name.lower() in display_name:
                return True
                
            # Try to match with components of the address
            for _, component in address.items():
                if isinstance(component, str) and location_name.lower() in component.lower():
                    return True
                    
            return False
    
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
            location_name: Name of the location being searched for.
            location_type: Type of location being searched for.
            
        Returns:
            Prompt string.
        """
        # Extract relevant data from result
        display_name = result.get("display_name", "")
        type_value = result.get("type", "")
        osm_type = result.get("osm_type", "")
        importance = result.get("importance", 0)
        address = result.get("address", {})
        
        # Convert address dict to a string - limit to 5 key items for brevity
        address_items = list(address.items())[:5]
        address_str = "\n".join([f"    {k}: {v}" for k, v in address_items])
        
        # Create the prompt with very explicit formatting instructions
        prompt = f"""
You are evaluating whether a search result from Nominatim API matches a location we're looking for.

TARGET LOCATION: {location_name}
TARGET TYPE: {location_type or 'Unknown'}

SEARCH RESULT:
  display_name: {display_name}
  type: {type_value}
  osm_type: {osm_type}
  importance: {importance}
  address:
{address_str}

TASK:
Determine if this result is a good match for our target location.

EVALUATION CRITERIA:
1. Name similarity: Does the result name match or contain the target name?
2. Type match: Is the result type compatible with the target type?
3. Importance: Is this a significant feature (higher importance score)?
4. Address context: Does the address information match expectations?

OUTPUT FORMAT:
Return ONLY a JSON object with exactly this structure and nothing else:
{{
  "is_match": true or false,
  "confidence": number between 0-100,
  "reasoning": "Brief explanation"
}}

Reply with ONLY the JSON object, no introduction or additional text.
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

    def _generate_response(self, prompt: str, max_retries: int = 2) -> str:
        """
        Generate a response from Gemini with error handling and retries.
        
        Args:
            prompt: The prompt to send to Gemini
            max_retries: Maximum number of retries for transient errors
            
        Returns:
            The text response from Gemini
            
        Raises:
            ValueError: If generation fails after all retries
        """
        for attempt in range(max_retries + 1):
            try:
                # Configure generation parameters for more reliable structured output
                generation_config = GenerationConfig(
                    temperature=0.1,  # Use low temperature for more predictable output
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=2048
                )
                
                # Generate response
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                # Return the text content
                return response.text.strip()
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Gemini API error (attempt {attempt+1}/{max_retries+1}): {str(e)}")
                    time.sleep(1)  # Wait before retrying
                else:
                    logger.error(f"Gemini API failed after {max_retries+1} attempts: {str(e)}")
                    raise ValueError(f"Failed to generate response from Gemini: {str(e)}")
                    
        # This should never be reached due to the raise in the loop
        raise ValueError("Failed to generate response from Gemini after retries")

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
