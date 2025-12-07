"""
FastAPI application for the Biotech M&A Predictor.

This package provides REST API endpoints for accessing company data,
M&A predictions, reports, and alerts.
"""

from src.api.app import create_app

__all__ = ["create_app"]
