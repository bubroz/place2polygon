# Place2Polygon: Product Requirements Document

## 1. Executive Summary

Place2Polygon is a Python tool designed to extract location mentions from text and find their precise polygon boundaries using OpenStreetMap data. The system uses Gemini Flash 2.0 to orchestrate intelligent boundary searches, implements robust caching, and follows strict rate-limiting practices for API usage. The initial focus is on US locations with planned expansion to global coverage.

## 2. Product Overview

### 2.1 Problem Statement
Existing geocoding solutions typically return point coordinates for locations, but lack precise polygon boundaries. When visualizing locations mentioned in text on maps, using points alone creates an imprecise representation. Place2Polygon addresses this by prioritizing polygon boundaries over points.

### 2.2 Solution Overview
Place2Polygon extracts location mentions from text, conducts intelligent multi-stage searches for polygon boundaries, and creates interactive visualizations with accurate administrative boundaries. Point markers are used only as a last resort after exhaustive polygon searches fail.

### 2.3 Target Users
- Data journalists visualizing location-based stories
- GIS analysts processing location data from unstructured text
- Researchers analyzing geographical patterns in documents
- Developers building location-aware applications

## 3. User Stories & Use Cases

### 3.1 Primary Use Cases
1. **News Analysis**: Extract locations from news articles and visualize them with accurate boundaries.
2. **Document Processing**: Batch process documents to extract and map location data.
3. **Geospatial Research**: Analyze geographic patterns in text corpora.
4. **API Service**: Integrate with applications needing location extraction and boundary data.

### 3.2 User Stories
- As a journalist, I want to automatically extract and map locations from news articles so I can create compelling visualizations.
- As a researcher, I want to process multiple documents and extract location boundaries to analyze geographic patterns.
- As a developer, I want to integrate location boundary extraction into my application via a simple API.
- As an analyst, I want to validate extracted location boundaries against known administrative divisions.

## 4. Technical Requirements

### 4.1 Functional Requirements

#### 4.1.1 Location Extraction
- Extract location mentions from text using spaCy NER
- Identify location types (city, county, state, etc.)
- Determine location relevance based on position and frequency
- Support US place name conventions initially, with expansion plans

#### 4.1.2 Boundary Search
- Implement multi-stage search orchestrated by Gemini Flash 2.0
- Progressive search strategy with multiple fallback approaches
- Parameter optimization based on location type and context
- Result validation to ensure accurate boundaries
- Use point markers only as a last resort after exhaustive searches

#### 4.1.3 Caching System
- SQLite-based persistent cache for all Nominatim queries
- GeoJSON polygon storage for reuse across sessions
- Configurable TTL for cached data
- Cache statistics for monitoring and optimization
- Cache invalidation mechanism for updates

#### 4.1.4 Rate Limiting
- Strict compliance with OSM usage policies (max 1 request/second)
- Proper HTTP headers (User-Agent and Referer)
- Queueing mechanism for bulk operations
- Retry mechanism with exponential backoff

#### 4.1.5 Visualization
- Interactive map visualization with Folium
- Display of polygon boundaries with popups
- Smart boundary selection for nested locations
- Export capabilities to GeoJSON, HTML, and other formats

### 4.2 Non-Functional Requirements

#### 4.2.1 Performance
- Response time < 3 seconds for cached queries
- Response time < 10 seconds for non-cached single location
- Support for batch processing with optimal rate limiting
- Memory usage < 1GB for processing standard articles

#### 4.2.2 Scalability
- Handle documents with up to 1000 location mentions
- Support multi-threaded cache access
- Graceful degradation under high load

#### 4.2.3 Reliability
- 99.9% successful location extraction from well-formed text
- Graceful handling of API failures
- Comprehensive error logging
- No data loss in case of interruption

#### 4.2.4 Security
- Secure handling of API credentials
- Sanitization of inputs
- Safe handling of external API calls

## 5. Component Architecture

### 5.1 Core Components

```
+------------------------+     +----------------------+     +--------------------+
| Location Extractor     |---->| Gemini Orchestrator  |---->| Nominatim Client   |
| (spaCy NER)            |     | (Search Strategy)    |     | (API Interface)    |
+------------------------+     +----------------------+     +--------------------+
                                        |                           |
                                        v                           v
+------------------------+     +----------------------+     +--------------------+
| Map Visualizer         |<----| Boundary Selector    |<----| Cache Manager      |
| (Folium)               |     | (Smart Selection)    |     | (SQLite)           |
+------------------------+     +----------------------+     +--------------------+
```

### 5.2 Component Descriptions

#### 5.2.1 Location Extractor
- Processes text documents using spaCy NER
- Identifies and classifies location mentions
- Determines location relevance and context
- Resolves ambiguous location references

#### 5.2.2 Gemini Orchestrator
- Interfaces with Gemini Flash 2.0 API
- Manages multi-stage search strategies
- Accesses Nominatim documentation
- Validates search results
- Logs search attempts

#### 5.2.3 Nominatim Client
- Handles API requests to Nominatim
- Implements rate limiting
- Manages request headers and formatting
- Handles error responses
- Converts API responses to standard format

#### 5.2.4 Cache Manager
- SQLite-based persistent storage
- Thread-safe operations
- TTL management
- Statistics tracking
- Cache invalidation

#### 5.2.5 Boundary Selector
- Implements smart boundary selection
- Resolves nested locations
- Prioritizes relevant boundaries
- Applies boundary filtering rules

#### 5.2.6 Map Visualizer
- Creates interactive Folium maps
- Renders polygon boundaries
- Handles fallback to point markers
- Configures popups and styling
- Exports to various formats

## 6. API Designs

### 6.1 Core API

```python
# Main Public API
def extract_and_map_locations(text, output_path=None, cache_ttl=None):
    """Extract locations from text and create a map with polygon boundaries.
    
    Args:
        text (str): Text content to analyze
        output_path (str, optional): Path to save the output map. Default creates temp file.
        cache_ttl (int, optional): Cache time-to-live in days. Default uses system setting.
        
    Returns:
        dict: Extracted locations with boundaries and metadata
        str: Path to the generated map HTML file
    """
    
# Location Extraction API
def extract_locations(text):
    """Extract location mentions from text.
    
    Args:
        text (str): Text content to analyze
        
    Returns:
        list: Extracted locations with metadata
    """
    
# Polygon Search API
def find_polygon_boundaries(locations, use_cache=True):
    """Find polygon boundaries for locations.
    
    Args:
        locations (list): List of location dictionaries
        use_cache (bool): Whether to use cache
        
    Returns:
        list: Locations with boundary data
    """
    
# Map Visualization API
def create_map(locations_with_boundaries, output_path=None):
    """Create an interactive map with polygon boundaries.
    
    Args:
        locations_with_boundaries (list): Locations with boundary data
        output_path (str, optional): Path to save the map
        
    Returns:
        str: Path to the generated map
    """
```

### 6.2 Gemini Orchestrator API

```python
def orchestrate_polygon_search(location_name, location_type=None):
    """Orchestrate a multi-stage search for polygon boundaries.
    
    Args:
        location_name (str): Name of the location
        location_type (str, optional): Type of location (city, county, etc.)
        
    Returns:
        dict: Polygon boundary data or point data as fallback
    """
    
def get_search_strategies(location_name, location_type=None):
    """Get a list of search strategies for a location.
    
    Args:
        location_name (str): Name of the location
        location_type (str, optional): Type of location
        
    Returns:
        list: Ordered list of search strategy dictionaries
    """
```

### 6.3 Cache Manager API

```python
def get_from_cache(query_key):
    """Get result from cache.
    
    Args:
        query_key (str): Cache key
        
    Returns:
        dict: Cached result or None
    """
    
def save_to_cache(query_key, result, ttl=None):
    """Save result to cache.
    
    Args:
        query_key (str): Cache key
        result (dict): Result to cache
        ttl (int, optional): Time-to-live in days
    """
    
def get_cache_stats():
    """Get cache statistics.
    
    Returns:
        dict: Cache statistics
    """
```

## 7. Data Flow Diagrams

### 7.1 Main Process Flow

```
[Text Input] → [Location Extraction] → [Relevance Ranking] → [Cache Lookup] → [Gemini Orchestration]
     ↓                                                            ↑               ↓
     ↓                                                            ↑       [Nominatim API Calls]
     ↓                                                            ↑               ↓  
[Map Creation] ← [Visualization Config] ← [Boundary Selection] ← [Cache Storage]
     ↓
[HTML Output/Export]
```

### 7.2 Gemini Orchestration Flow

```
[Location Data] → [Generate Search Plan] → [Execute Search Strategy 1] → [Validate Results]
                          ↓                             ↓                      ↓
                   [Access Documentation]        [If failed, try              [If valid,
                          ↓                       next strategy]               return]
                   [Optimize Parameters] ← ← ← ← ← ← ← ← ← ← ← ← ←
                                                    ↓
                                          [After all strategies exhausted,
                                           fall back to point marker]
```

## 8. Implementation Plan

### 8.1 Phased Development Approach

#### Phase 1: Core Functionality (2-3 weeks)
- Set up project structure and development environment
- Implement location extraction with spaCy
- Build basic Nominatim client
- Create simple boundary selection logic
- Develop initial map visualization

#### Phase 2: Caching & Rate Limiting (1-2 weeks)
- Implement SQLite-based cache
- Develop cache management utilities
- Build rate limiting mechanism
- Create cache statistics tracking

#### Phase 3: Gemini Integration (2-3 weeks)
- Set up Google Cloud authentication
- Implement Gemini Flash 2.0 orchestrator
- Build documentation access mechanism
- Develop multi-stage search strategies
- Create result validation logic

#### Phase 4: Refinement & Testing (1-2 weeks)
- Implement comprehensive testing
- Optimize performance
- Refine error handling
- Complete documentation
- Create example notebooks

### 8.2 Milestones & Deliverables

| Milestone | Description | Timeline |
|-----------|-------------|----------|
| M1 | Project setup and basic extraction | End of Week 1 |
| M2 | Basic boundary search implementation | End of Week 2 |
| M3 | Map visualization working | End of Week 3 |
| M4 | Cache system implemented | End of Week 4 |
| M5 | Rate limiting mechanism working | End of Week 5 |
| M6 | Gemini orchestrator functional | End of Week 6 |
| M7 | Multi-stage search implemented | End of Week 7 |
| M8 | Testing and refinement complete | End of Week 8 |

## 9. Risk Assessment

### 9.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|------------|
| Nominatim API changes | High | Low | Monitor API updates, implement adapter pattern |
| Gemini API availability | High | Low | Implement fallback search strategies |
| Cache performance issues | Medium | Medium | Optimize indexes, consider sharding |
| Rate limiting failures | High | Low | Implement circuit breaker pattern |
| NER accuracy issues | Medium | Medium | Provide manual correction options |

### 9.2 Project Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|------------|
| Timeline overruns | Medium | Medium | Buffer time in schedule, prioritize features |
| Scope creep | Medium | High | Strict adherence to PRD, change control process |
| Integration challenges | Medium | Medium | Early proof-of-concept testing |
| Documentation gaps | Medium | Low | Continuous documentation during development |

## 10. Acceptance Criteria

### 10.1 Core Functionality

- [x] Successfully extracts 90%+ of location mentions from test articles
- [x] Finds polygon boundaries for 85%+ of US locations
- [x] Implements smart boundary selection for nested locations
- [x] Creates interactive maps with proper styling and popups
- [x] Exports results to JSON for validation
- [x] Implements organized output management system

### 10.2 Caching System

- [x] Successfully caches and retrieves Nominatim results
- [x] Implements configurable TTL for cached data
- [x] Provides cache statistics
- [x] Achieves 10x+ performance improvement for cached queries
- [x] Implements automatic cleanup of expired cache entries

### 10.3 Rate Limiting

- [x] Enforces 1 request per second maximum
- [x] Sets proper HTTP headers
- [x] Implements retry mechanism with backoff
- [x] Handles API errors gracefully

### 10.4 Gemini Integration

- [x] Successfully orchestrates multi-stage searches
- [x] Accesses documentation for parameter optimization
- [x] Validates search results
- [x] Logs search attempts for debugging
- [x] Implements fallback mechanism for Gemini API failures
- [-] Achieves 20%+ improvement in polygon match rate over baseline (current tests show normal mode often outperforms Gemini for international locations)

## 10.5 Performance Evaluation

- [x] Provides tools to compare different search strategies
- [x] Generates visual reports for performance analysis
- [x] Tracks metrics like match rate, polygon rate, and processing time
- [x] Identifies specific limitations for future improvements

## 11. Appendices

### 11.1 Technology Stack

- **Programming Language**: Python 3.8+
- **NER**: spaCy with en_core_web_sm model
- **Data Processing**: Pandas, GeoPandas
- **Mapping**: Folium, Shapely
- **Database**: SQLite
- **AI Integration**: Google Generative AI (Gemini Flash 2.0)
- **HTTP Client**: Requests
- **Testing**: PyTest

### 11.2 Development Environment

- **Version Control**: Git/GitHub
- **Dependency Management**: Poetry or Pip with requirements.txt
- **Code Quality**: Black, isort, flake8, mypy
- **CI/CD**: GitHub Actions
- **Documentation**: Sphinx, MkDocs

### 11.3 API Reference Documentation

Detailed API documentation will be generated using Sphinx and hosted on GitHub Pages.

### 11.4 User Documentation

User guides will include:
- Installation instructions
- Basic usage examples
- Advanced configuration options
- Troubleshooting guide
- Performance optimization tips 