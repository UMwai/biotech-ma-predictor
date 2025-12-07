"""
API routes package.

Contains all REST API endpoint definitions organized by resource.
"""

from src.api.routes import companies, predictions, reports, alerts

__all__ = ["companies", "predictions", "reports", "alerts"]
