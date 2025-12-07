"""
Report Generator Service Package

This package provides comprehensive report generation capabilities for the
biotech M&A predictor system, including templating, rendering, and delivery.

Main Components:
    - ReportGenerator: Main orchestrator for generating all report types
    - TemplateManager: Jinja2 template loading and management
    - HTMLRenderer: HTML report generation
    - PDFRenderer: PDF report generation using WeasyPrint
    - EmailDelivery: Email delivery via SendGrid
    - S3Delivery: Upload reports to AWS S3
    - WebhookDelivery: POST reports to client endpoints

Report Types:
    - DailyDigest: Summary of all signals from past 24h
    - WeeklyWatchlist: Ranked M&A candidates with scores
    - DeepDiveReport: Comprehensive single-company analysis
    - AlertReport: Generated when scores change significantly

Example:
    >>> from reports import ReportGenerator
    >>> generator = ReportGenerator(db_pool, config)
    >>> report = await generator.generate_daily_digest()
    >>> await generator.deliver(report, ['email', 's3'])
"""

from .generator import ReportGenerator, ReportContext
from .templates import TemplateManager, ChartGenerator
from .renderers import HTMLRenderer, PDFRenderer, ReportRenderer
from .delivery import (
    DeliveryManager,
    EmailDelivery,
    S3Delivery,
    WebhookDelivery,
    DeliveryResult,
    DeliveryStatus,
)

__all__ = [
    # Main generator
    'ReportGenerator',
    'ReportContext',

    # Template management
    'TemplateManager',
    'ChartGenerator',

    # Renderers
    'ReportRenderer',
    'HTMLRenderer',
    'PDFRenderer',

    # Delivery
    'DeliveryManager',
    'EmailDelivery',
    'S3Delivery',
    'WebhookDelivery',
    'DeliveryResult',
    'DeliveryStatus',
]

__version__ = '1.0.0'
