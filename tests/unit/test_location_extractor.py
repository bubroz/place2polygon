"""
Unit tests for the LocationExtractor class.
"""

import pytest
from unittest.mock import patch, MagicMock
import spacy

from place2polygon.core.location_extractor import LocationExtractor


@pytest.fixture
def mock_nlp():
    """Mock spaCy NLP object."""
    mock = MagicMock(spec=spacy.language.Language)
    
    # Mock the Doc object created by the nlp model
    mock_doc = MagicMock()
    
    # Create mock entities
    mock_seattle = MagicMock()
    mock_seattle.text = "Seattle"
    mock_seattle.label_ = "GPE"
    mock_seattle.start_char = 0
    mock_seattle.end_char = 7
    
    mock_washington = MagicMock()
    mock_washington.text = "Washington"
    mock_washington.label_ = "GPE"
    mock_washington.start_char = 20
    mock_washington.end_char = 30
    
    # Set up the entities
    mock_doc.ents = [mock_seattle, mock_washington]
    
    # Set up sentences for context
    mock_sentence = MagicMock()
    mock_sentence.text = "Seattle is a beautiful city in Washington state."
    mock_seattle.sent = mock_sentence
    mock_washington.sent = mock_sentence
    
    # Configure the mock's behavior
    mock.return_value = mock_doc
    
    return mock


class TestLocationExtractor:
    """Tests for the LocationExtractor class."""
    
    @patch("place2polygon.core.location_extractor.spacy.load")
    def test_init(self, mock_spacy_load):
        """Test the initializer."""
        mock_spacy_load.return_value = MagicMock()
        
        extractor = LocationExtractor(model_name="en_core_web_sm")
        
        mock_spacy_load.assert_called_once_with("en_core_web_sm")
        assert extractor.model_name == "en_core_web_sm"
        assert extractor.min_relevance_score == 30.0
    
    @patch("place2polygon.core.location_extractor.spacy.load")
    def test_init_custom_relevance(self, mock_spacy_load):
        """Test the initializer with custom relevance score."""
        mock_spacy_load.return_value = MagicMock()
        
        extractor = LocationExtractor(model_name="en_core_web_sm", min_relevance_score=50.0)
        
        assert extractor.min_relevance_score == 50.0
    
    def test_extract_locations(self, mock_nlp):
        """Test extracting locations from text."""
        with patch("place2polygon.core.location_extractor.spacy.load", return_value=mock_nlp):
            extractor = LocationExtractor()
            
            # Test with sample text
            text = "Seattle is a beautiful city in Washington state."
            locations = extractor.extract_locations(text)
            
            # Verify the results
            assert len(locations) == 2
            
            # Check Seattle
            seattle = next((loc for loc in locations if loc["name"] == "Seattle"), None)
            assert seattle is not None
            assert seattle["type"] == "city"
            assert seattle["occurrences"] == 1
            assert "relevance_score" in seattle
            
            # Check Washington
            washington = next((loc for loc in locations if loc["name"] == "Washington"), None)
            assert washington is not None
            assert washington["type"] == "state"
            assert washington["occurrences"] == 1
            assert "relevance_score" in washington
    
    def test_extract_locations_empty_text(self, mock_nlp):
        """Test extracting locations from empty text."""
        with patch("place2polygon.core.location_extractor.spacy.load", return_value=mock_nlp):
            extractor = LocationExtractor()
            
            # Test with empty text
            locations = extractor.extract_locations("")
            
            # Verify empty result
            assert locations == []
    
    def test_normalize_location_name(self):
        """Test normalizing location names."""
        with patch("place2polygon.core.location_extractor.spacy.load", return_value=MagicMock()):
            extractor = LocationExtractor()
            
            # Test normalizing state abbreviation
            assert extractor._normalize_location_name("WA") == "Washington"
            
            # Test normalizing city with state abbreviation
            assert extractor._normalize_location_name("Seattle, WA") == "Seattle, Washington"
            
            # Test normalizing with punctuation
            assert extractor._normalize_location_name("Seattle.") == "Seattle"
            
            # Test normalizing with whitespace
            assert extractor._normalize_location_name(" Portland ") == "Portland"
    
    def test_determine_location_type(self, mock_nlp):
        """Test determining location types."""
        with patch("place2polygon.core.location_extractor.spacy.load", return_value=mock_nlp):
            extractor = LocationExtractor()
            
            # Create mock entity for testing
            entity = MagicMock()
            doc = mock_nlp("Washington is a state. Seattle is a city.")
            
            # Test state detection
            entity.text = "Washington"
            entity.label_ = "GPE"
            assert extractor._determine_location_type(entity, doc) == "state"
            
            # Test city detection (based on GPE label and not matching state name)
            entity.text = "Seattle"
            entity.label_ = "GPE"
            assert extractor._determine_location_type(entity, doc) == "city"
            
            # Test county detection (should match based on context)
            entity.text = "King County"
            entity.start = 0
            entity.end = 2
            doc = mock_nlp("King County is located in Washington.")
            assert extractor._determine_location_type(entity, doc) == "county"
    
    def test_enhance_locations_with_context(self, mock_nlp):
        """Test enhancing locations with context."""
        with patch("place2polygon.core.location_extractor.spacy.load", return_value=mock_nlp):
            extractor = LocationExtractor()
            
            # Sample locations
            locations = [
                {
                    "name": "Seattle",
                    "type": "city",
                    "relevance_score": 75.0
                }
            ]
            
            # Sample text
            text = "Seattle is a city in Washington state."
            
            # Enhance locations
            enhanced = extractor.enhance_locations_with_context(locations, text)
            
            # Verify the results
            assert len(enhanced) == 1
            assert "context_sentences" in enhanced[0]
            assert "related_locations" in enhanced[0]
    
    def test_calculate_relevance_scores(self, mock_nlp):
        """Test calculating relevance scores."""
        with patch("place2polygon.core.location_extractor.spacy.load", return_value=mock_nlp):
            extractor = LocationExtractor()
            
            # Sample locations
            locations = [
                {
                    "name": "Seattle",
                    "occurrences": 3,
                    "char_start": 0
                },
                {
                    "name": "Washington",
                    "occurrences": 1,
                    "char_start": 50
                }
            ]
            
            # Create mock doc
            doc = MagicMock()
            doc.text = "Seattle is mentioned multiple times. Seattle is a city in Washington. Seattle is beautiful."
            
            # Calculate scores
            extractor._calculate_relevance_scores(locations, doc)
            
            # Verify scores exist and Seattle has higher relevance
            assert "relevance_score" in locations[0]
            assert "relevance_score" in locations[1]
            assert locations[0]["relevance_score"] > locations[1]["relevance_score"] 