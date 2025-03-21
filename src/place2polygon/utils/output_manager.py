"""
Output manager for Place2Polygon.

This module handles the organization and management of output files such as maps,
reports, and other generated content from the Place2Polygon tool.
"""

import os
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Union, List

# Default output directory structure
DEFAULT_OUTPUT_DIR = "place2polygon_output"
MAP_DIR = "maps"
REPORT_DIR = "reports"
CACHE_DIR = "cache"
DATA_DIR = "data"

class OutputManager:
    """
    Manages output files and directories for Place2Polygon.
    
    This class provides functionality to create, organize, and manage output files
    in a structured directory hierarchy.
    """
    
    def __init__(self, base_dir: Optional[str] = None, create_dirs: bool = True):
        """
        Initialize the OutputManager with a base directory.
        
        Args:
            base_dir: Base directory for all outputs. Defaults to "place2polygon_output" 
                     in the current working directory.
            create_dirs: Whether to create the directory structure automatically.
        """
        # Use provided base directory or default
        self.base_dir = Path(base_dir) if base_dir else Path(DEFAULT_OUTPUT_DIR)
        
        # Define subdirectories
        self.map_dir = self.base_dir / MAP_DIR
        self.report_dir = self.base_dir / REPORT_DIR
        self.cache_dir = self.base_dir / CACHE_DIR
        self.data_dir = self.base_dir / DATA_DIR
        
        # Create directory structure if requested
        if create_dirs:
            self._create_directory_structure()
    
    def _create_directory_structure(self) -> None:
        """Create the directory structure if it doesn't exist."""
        for directory in [self.base_dir, self.map_dir, self.report_dir, 
                          self.cache_dir, self.data_dir]:
            directory.mkdir(exist_ok=True, parents=True)
    
    def get_map_path(self, filename: Optional[str] = None) -> Path:
        """
        Get a path for a map file.
        
        Args:
            filename: Optional specific filename. If not provided, creates a timestamped name.
            
        Returns:
            Path object for the map file.
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"map_{timestamp}.html"
        
        # Make sure directory exists
        self.map_dir.mkdir(exist_ok=True, parents=True)
        return self.map_dir / filename
    
    def get_report_path(self, filename: Optional[str] = None, 
                        report_type: str = "performance") -> Path:
        """
        Get a path for a report file.
        
        Args:
            filename: Optional specific filename. If not provided, creates a timestamped name.
            report_type: Type of report (e.g., "performance", "dashboard").
            
        Returns:
            Path object for the report file.
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = "json" if report_type == "performance" else "html"
            filename = f"{report_type}_{timestamp}.{extension}"
        
        # Make sure directory exists
        self.report_dir.mkdir(exist_ok=True, parents=True)
        return self.report_dir / filename
    
    def get_data_path(self, filename: Optional[str] = None, 
                      data_type: str = "locations") -> Path:
        """
        Get a path for a data file.
        
        Args:
            filename: Optional specific filename. If not provided, creates a timestamped name.
            data_type: Type of data (e.g., "locations", "boundaries").
            
        Returns:
            Path object for the data file.
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{data_type}_{timestamp}.json"
        
        # Make sure directory exists
        self.data_dir.mkdir(exist_ok=True, parents=True)
        return self.data_dir / filename
    
    def get_cache_dir(self) -> Path:
        """
        Get the cache directory path.
        
        Returns:
            Path object for the cache directory.
        """
        # Make sure directory exists
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        return self.cache_dir
    
    def clean_old_files(self, max_age_days: int = 30, 
                        directories: Optional[List[str]] = None) -> int:
        """
        Clean up old files from the output directories.
        
        Args:
            max_age_days: Maximum age of files in days before they're deleted.
            directories: List of directory names to clean. Defaults to all directories.
            
        Returns:
            Number of files deleted.
        """
        # Determine which directories to clean
        dirs_to_clean = []
        if not directories:
            dirs_to_clean = [self.map_dir, self.report_dir, self.data_dir]
        else:
            dir_map = {
                "maps": self.map_dir,
                "reports": self.report_dir,
                "data": self.data_dir
            }
            dirs_to_clean = [dir_map[d] for d in directories if d in dir_map]
        
        # Calculate cutoff time
        cutoff_time = time.time() - (max_age_days * 86400)  # 86400 seconds in a day
        
        # Count deleted files
        deleted_count = 0
        
        # Clean each directory
        for directory in dirs_to_clean:
            if not directory.exists():
                continue
                
            for file_path in directory.glob("*"):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
        
        return deleted_count
    
    def list_outputs(self, output_type: Optional[str] = None, 
                     max_items: int = 10) -> List[str]:
        """
        List available output files.
        
        Args:
            output_type: Type of outputs to list ("maps", "reports", "data", or None for all).
            max_items: Maximum number of items to return per category.
            
        Returns:
            List of file paths relative to the base directory.
        """
        results = []
        
        # Determine which directories to list
        dirs_to_list = []
        if not output_type:
            dirs_to_list = [("maps", self.map_dir), ("reports", self.report_dir), 
                           ("data", self.data_dir)]
        else:
            dir_map = {
                "maps": self.map_dir,
                "reports": self.report_dir,
                "data": self.data_dir
            }
            if output_type in dir_map:
                dirs_to_list = [(output_type, dir_map[output_type])]
        
        # List files in each directory
        for dir_name, directory in dirs_to_list:
            if not directory.exists():
                continue
                
            files = sorted(directory.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)
            
            for file_path in files[:max_items]:
                if file_path.is_file():
                    relative_path = file_path.relative_to(self.base_dir)
                    results.append(str(relative_path))
        
        return results

# Create a default output manager instance
default_output_manager = OutputManager() 