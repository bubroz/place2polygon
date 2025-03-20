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
            A list of search strategy dictionaries.
        """
        logger.info(f"Generating search strategies for {location_name}")
        
        # Get search strategy documentation
        search_strategies = self.docs_provider.get_search_strategies()
        
        # Prepare a base strategy to provide context
        base_strategy = {
            "description": "Basic structured search",
            "params": {
                "q": location_name,
                "polygon_geojson": 1,
                "addressdetails": 1,
                "limit": 5
            }
        }
        
        # Create prompt
        prompt = self._create_strategy_prompt(
            location_name,
            location_type,
            location_context,
            base_strategy
        )
        
        try:
            # Define JSON schema for search strategies response
            response_schema = {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "description": {"type": "STRING"},
                        "params": {
                            "type": "OBJECT",
                            "properties": {
                                "q": {"type": "STRING"},
                                "polygon_geojson": {"type": "INTEGER"},
                                "addressdetails": {"type": "INTEGER"},
                                "limit": {"type": "INTEGER"},
                                "country": {"type": "STRING", "nullable": True},
                                "state": {"type": "STRING", "nullable": True},
                                "county": {"type": "STRING", "nullable": True},
                                "city": {"type": "STRING", "nullable": True}
                            },
                            "required": ["q", "polygon_geojson"]
                        }
                    },
                    "required": ["description", "params"]
                }
            }
            
            # Configure generation with schema for structured output
            config_params = {
                "temperature": 0.1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048
            }
            
            # Check if structured output parameters are supported
            try:
                # Try creating a config with response_mime_type to test
                test_config = GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema={"type": "OBJECT"}
                )
                # If no error, add the parameters
                config_params["response_mime_type"] = "application/json"
                config_params["response_schema"] = response_schema
                logger.info("Using structured output parameters for JSON generation")
            except TypeError:
                logger.warning("Structured output parameters not supported in this version of google.generativeai library")
            
            generation_config = GenerationConfig(**config_params)
            
            # Generate search strategies
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Parse response
            strategies = json.loads(response.text)
            
            # Add the basic strategy as a fallback
            if not strategies or not isinstance(strategies, list):
                strategies = [base_strategy]
            elif not any(strategy.get("params", {}).get("q") == location_name for strategy in strategies):
                strategies.append(base_strategy)
            
            logger.info(f"Generated {len(strategies)} search strategies")
            return strategies
            
        except Exception as e:
            logger.error(f"Failed to generate search strategies: {str(e)}")
            # Fall back to basic search strategy
            return [base_strategy]
    
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
            location_name: Name of the location searched for.
            location_type: Type of location (city, county, state, etc.).
            
        Returns:
            True if the result is valid, False otherwise.
        """
        # First perform basic validation
        if not self._basic_validate_result(result, location_name, location_type):
            logger.info("Result failed basic validation")
            return False
        
        # Then use Gemini for deeper validation
        try:
            # Create prompt
            prompt = self._create_validation_prompt(result, location_name, location_type)
            
            # Define JSON schema for validation response
            response_schema = {
                "type": "OBJECT",
                "properties": {
                    "is_match": {"type": "BOOLEAN"},
                    "confidence": {"type": "NUMBER"},
                    "reasoning": {"type": "STRING"}
                },
                "required": ["is_match", "confidence", "reasoning"]
            }
            
            # Configure generation with schema for structured output
            config_params = {
                "temperature": 0.1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048
            }
            
            # Check if structured output parameters are supported
            try:
                # Try creating a config with response_mime_type to test
                test_config = GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema={"type": "OBJECT"}
                )
                # If no error, add the parameters
                config_params["response_mime_type"] = "application/json"
                config_params["response_schema"] = response_schema
                logger.info("Using structured output parameters for JSON generation")
            except TypeError:
                logger.warning("Structured output parameters not supported in this version of google.generativeai library")
            
            generation_config = GenerationConfig(**config_params)
            
            # Generate validation
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Parse response
            validation = json.loads(response.text)
            
            # Log validation result
            logger.info(f"Gemini validation: {validation['is_match']} (confidence: {validation['confidence']})")
            logger.debug(f"Reasoning: {validation['reasoning']}")
            
            return validation["is_match"] and validation["confidence"] > 0.5
            
        except Exception as e:
            logger.error(f"Failed to validate result: {str(e)}")
            # Fall back to basic validation
            return True  # Assume valid if Gemini validation fails
    
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
                config_params = {
                    "temperature": 0.1,  # Use low temperature for more predictable output
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 2048
                }
                
                # Check if response_mime_type is supported in this version of the library
                try:
                    # Try creating a config with response_mime_type to test
                    test_config = GenerationConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                    # If no error, add the parameter
                    config_params["response_mime_type"] = "application/json"
                    logger.info("Using response_mime_type for structured JSON output")
                except TypeError:
                    # response_mime_type not supported in this version
                    logger.warning("response_mime_type not supported in this version of google.generativeai library")
                
                # Generate response
                generation_config = GenerationConfig(**config_params)
                
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
