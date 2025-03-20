# Place2Polygon Examples

This directory contains examples demonstrating how to use the Place2Polygon package.

## Jupyter Notebooks

- [basic_usage.ipynb](basic_usage.ipynb): Basic usage examples for extracting locations from text, finding polygon boundaries, and creating interactive maps.

## Running the Examples

To run the examples, you'll need Jupyter Notebook or Jupyter Lab installed:

```bash
pip install jupyter

# From the examples directory
jupyter notebook basic_usage.ipynb
```

## Setting Up Gemini Integration

Some examples use Google's Gemini Flash 2.0 for enhanced polygon searches. To use these features:

1. Obtain a Google API key from the [Google AI Studio](https://ai.google.dev/)
2. Set up the API key in your environment:
   ```bash
   export GOOGLE_API_KEY="your-api-key"
   ```
   or use the setup command:
   ```bash
   python -m place2polygon.cli setup_gemini
   ``` 