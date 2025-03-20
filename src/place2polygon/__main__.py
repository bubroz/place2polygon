"""
Entry point for the place2polygon package.
This allows running the CLI directly with `python -m place2polygon`.
"""

import logging
import sys
from typing import Optional

import typer

from place2polygon.cli import app

if __name__ == "__main__":
    app() 