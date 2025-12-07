#!/usr/bin/env python
"""
Run the Biotech M&A Predictor API server.

This script starts the FastAPI server with proper configuration.
"""

import uvicorn
import logging
from src.config import settings

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Biotech M&A Predictor API server...")
    logger.info(f"Host: {settings.api_host}")
    logger.info(f"Port: {settings.api_port}")
    logger.info(f"Environment: {settings.log_level}")

    # Run the server
    uvicorn.run(
        "src.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,  # Enable auto-reload in development
        log_level=settings.log_level.lower(),
        access_log=True,
    )
