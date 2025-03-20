"""
Location extractor module for identifying and extracting location mentions from text.

This module uses spaCy's Named Entity Recognition (NER) to extract location mentions from
text and provides functionality to analyze their relevance and context.
"""

import re
import string
from typing import Dict, List, Optional, Any, Tuple, Set
from collections import Counter
import logging

import spacy
from spacy.tokens import Doc, Span, Token

from place2polygon.utils.validators import validate_location_name

logger = logging.getLogger(__name__)

# US States dictionary for normalization and disambiguation
US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia'
}

# Reverse mapping for full name to abbreviation
US_STATE_ABBREVS = {v: k for k, v in US_STATES.items()}

# Common location type words to help identify location types from context
LOCATION_TYPE_INDICATORS = {
    'city': ['city', 'town', 'village', 'municipality', 'metropolitan'],
    'county': ['county', 'parish', 'borough'],
    'state': ['state', 'province', 'territory'],
    'neighborhood': ['neighborhood', 'neighbourhood', 'district', 'quarter'],
    'country': ['country', 'nation'],
    'region': ['region', 'area', 'zone', 'valley'],
    'mountain': ['mountain', 'mount', 'mt', 'peak', 'ridge'],
    'water': ['lake', 'river', 'ocean', 'sea', 'bay', 'gulf']
}

class LocationExtractor:
    """
    Extract location mentions from text using spaCy NER.
    
    Args:
        model_name: The spaCy model name to use.
        min_relevance_score: Minimum relevance score (0-100) for locations.
    """
    
    def __init__(self, model_name: str = "en_core_web_sm", min_relevance_score: float = 30.0):
        """Initialize the LocationExtractor with a spaCy model."""
        self.model_name = model_name
        self.min_relevance_score = min_relevance_score
        self.nlp = self._load_model()
        
    def _load_model(self) -> spacy.language.Language:
        """
        Load and configure the spaCy model.
        
        Returns:
            The loaded spaCy model.
        """
        try:
            nlp = spacy.load(self.model_name)
            logger.info(f"Loaded spaCy model: {self.model_name}")
            return nlp
        except OSError:
            logger.error(f"Failed to load spaCy model: {self.model_name}")
            logger.info("Please install the model with: python -m spacy download en_core_web_sm")
            raise
    
    def extract_locations(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract locations from text with metadata.
        
        Args:
            text: The text to extract locations from.
            
        Returns:
            A list of dictionaries containing location data and metadata.
        """
        if not text or not isinstance(text, str):
            logger.warning("No text provided for location extraction")
            return []
        
        # Process the text with spaCy
        doc = self.nlp(text)
        
        # Extract location entities (GPE = Geopolitical Entity, LOC = Location)
        location_ents = [ent for ent in doc.ents if ent.label_ in ('GPE', 'LOC')]
        
        if not location_ents:
            logger.info("No location entities found in the text")
            return []
        
        # Get unique locations (ignoring duplicates for now)
        unique_locations = {}
        for ent in location_ents:
            location_name = self._normalize_location_name(ent.text)
            if location_name not in unique_locations and validate_location_name(location_name):
                location_type = self._determine_location_type(ent, doc)
                location_data = {
                    'name': location_name,
                    'original_name': ent.text,
                    'type': location_type,
                    'char_start': ent.start_char,
                    'char_end': ent.end_char,
                    'sentence': ent.sent.text.strip(),
                    'occurrences': 1,
                    'mentions': [ent.text],
                }
                unique_locations[location_name] = location_data
            elif location_name in unique_locations:
                # Update existing location data for duplicates
                unique_locations[location_name]['occurrences'] += 1
                if ent.text not in unique_locations[location_name]['mentions']:
                    unique_locations[location_name]['mentions'].append(ent.text)
        
        # Convert to list and calculate relevance scores
        locations = list(unique_locations.values())
        self._calculate_relevance_scores(locations, doc)
        
        # Filter by minimum relevance score
        locations = [loc for loc in locations if loc['relevance_score'] >= self.min_relevance_score]
        
        # Sort by relevance score (descending)
        locations.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return locations
    
    def _normalize_location_name(self, name: str) -> str:
        """
        Normalize a location name (remove punctuation, expand state abbreviations, etc.).
        
        Args:
            name: The location name to normalize.
            
        Returns:
            The normalized location name.
        """
        # Remove leading/trailing whitespace and punctuation
        name = name.strip()
        name = name.strip(string.punctuation)
        
        # Check if it's a US state abbreviation
        if name.upper() in US_STATES:
            return US_STATES[name.upper()]
        
        # Expand state abbreviations in combined names (e.g., "Portland, OR")
        parts = name.split(',')
        if len(parts) == 2:
            city, state = parts[0].strip(), parts[1].strip()
            if state.upper() in US_STATES:
                return f"{city}, {US_STATES[state.upper()]}"
        
        return name
    
    def _determine_location_type(self, entity: Span, doc: Doc) -> str:
        """
        Determine the type of location based on context and known patterns.
        
        Args:
            entity: The spaCy entity span.
            doc: The spaCy document.
            
        Returns:
            The location type (city, county, state, etc.).
        """
        # Check if it's a US state
        if entity.text in US_STATES.values() or entity.text.upper() in US_STATES:
            return 'state'
        
        # Look for type indicators in the surrounding context
        context_start = max(0, entity.start - 5)
        context_end = min(len(doc), entity.end + 5)
        context = doc[context_start:context_end].text.lower()
        
        for loc_type, indicators in LOCATION_TYPE_INDICATORS.items():
            for indicator in indicators:
                # Check for patterns like "X County" or "County of X"
                if f"{entity.text} {indicator}".lower() in context or f"{indicator} of {entity.text}".lower() in context:
                    return loc_type
        
        # Default types based on entity label
        if entity.label_ == 'GPE':
            # Assume cities are more common than countries in most texts
            return 'city'
        elif entity.label_ == 'LOC':
            return 'region'
        
        return 'unknown'
    
    def _calculate_relevance_scores(self, locations: List[Dict[str, Any]], doc: Doc) -> None:
        """
        Calculate relevance scores for locations based on various factors.
        
        Args:
            locations: List of location dictionaries.
            doc: The spaCy document.
            
        Modifies the location dictionaries in place, adding a 'relevance_score' key.
        """
        # Get total number of locations
        total_locations = len(locations)
        max_occurrences = max([loc['occurrences'] for loc in locations]) if locations else 1
        
        # Calculate document sections (beginning, middle, end)
        doc_length = len(doc.text)
        beginning_section = doc_length * 0.25
        ending_section = doc_length * 0.75
        
        for location in locations:
            # Base score starts at 50
            score = 50.0
            
            # Adjust based on frequency (up to +20)
            frequency_score = (location['occurrences'] / max_occurrences) * 20
            score += frequency_score
            
            # Position bonus (up to +15)
            char_start = location['char_start']
            if char_start < beginning_section:
                # Locations mentioned at the beginning get a bigger bonus
                position_score = 15.0 * (1 - (char_start / beginning_section))
            elif char_start > ending_section:
                # Locations in conclusion get a moderate bonus
                position_score = 10.0 * ((char_start - ending_section) / (doc_length - ending_section))
            else:
                # Locations in the middle get a smaller bonus
                position_score = 5.0
            score += position_score
            
            # Known location type bonus (up to +10)
            if location['type'] != 'unknown':
                score += 10.0
            
            # Cap at 100
            location['relevance_score'] = min(round(score, 1), 100.0)
    
    def enhance_locations_with_context(self, locations: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
        """
        Enhance location data with additional context from the text.
        
        Args:
            locations: List of location dictionaries.
            text: The original text.
            
        Returns:
            Enhanced location dictionaries.
        """
        if not locations:
            return []
        
        doc = self.nlp(text)
        
        for location in locations:
            # Find mentions in text to extract context
            location_name = location['name']
            location_mentions = []
            
            for sent in doc.sents:
                sent_text = sent.text.lower()
                if location_name.lower() in sent_text:
                    location_mentions.append(sent.text)
            
            # Add context information to location data
            location['context_sentences'] = location_mentions[:3]  # Limit to 3 context sentences
            
            # Try to identify hierarchical relationships
            location['related_locations'] = self._identify_related_locations(location, locations)
        
        return locations
    
    def _identify_related_locations(self, location: Dict[str, Any], all_locations: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Identify hierarchical relationships between locations.
        
        Args:
            location: The location to find relationships for.
            all_locations: All extracted locations.
            
        Returns:
            List of related location dictionaries with relationship type.
        """
        related = []
        location_name = location['name'].lower()
        location_type = location['type']
        
        for other in all_locations:
            if other['name'] == location['name']:
                continue
                
            other_name = other['name'].lower()
            other_type = other['type']
            
            # Check for comma-separated hierarchies like "Portland, Oregon"
            if ',' in location_name and other_name in location_name.split(',')[1].strip():
                related.append({'name': other['name'], 'relationship': 'parent', 'type': other_type})
            elif ',' in other_name and location_name in other_name.split(',')[1].strip():
                related.append({'name': other['name'], 'relationship': 'child', 'type': other_type})
            
            # Check for state-city relationships
            if location_type == 'city' and other_type == 'state':
                # For a city, see if state is mentioned in the same contexts
                for sent in location.get('context_sentences', []):
                    if other_name in sent.lower():
                        related.append({'name': other['name'], 'relationship': 'parent', 'type': 'state'})
                        break
            elif location_type == 'state' and other_type == 'city':
                # For a state, see if cities are mentioned in the same contexts
                for sent in location.get('context_sentences', []):
                    if other_name in sent.lower():
                        related.append({'name': other['name'], 'relationship': 'child', 'type': 'city'})
                        break
        
        return related

# Create a default instance
default_extractor = LocationExtractor()
