"""Logging configuration for ACDown Client."""

import logging
import sys
from typing import Optional


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging configuration.
    
    Args:
        verbose: If True, set log level to DEBUG, otherwise INFO
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("acdown")
    
    # Set log level
    log_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(log_level)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name (will be prefixed with 'acdown.')
        
    Returns:
        Logger instance
    """
    logger_name = f"acdown.{name}" if name else "acdown"
    return logging.getLogger(logger_name)
