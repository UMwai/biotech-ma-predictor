"""
Template Manager - Jinja2 template loading and chart generation.

This module manages report templates and generates visualizations for reports.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import base64
from io import BytesIO

from jinja2 import (
    Environment,
    FileSystemLoader,
    select_autoescape,
    TemplateNotFound,
)
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


logger = logging.getLogger(__name__)


class TemplateManager:
    """
    Manages Jinja2 templates for report generation.

    Handles template loading, caching, and rendering with support for
    custom filters and client-specific customizations.
    """

    def __init__(
        self,
        template_dir: Optional[str] = None,
        custom_filters: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the template manager.

        Args:
            template_dir: Directory containing templates (default: ./templates)
            custom_filters: Optional custom Jinja2 filters
        """
        if template_dir is None:
            # Default to templates/ directory relative to this file
            base_dir = Path(__file__).parent.parent.parent
            template_dir = base_dir / "templates" / "reports"

        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self._add_default_filters()
        if custom_filters:
            self.env.filters.update(custom_filters)

        logger.info(f"TemplateManager initialized with template_dir: {self.template_dir}")

    def _add_default_filters(self):
        """Add default Jinja2 filters for report formatting."""

        def format_datetime(value: Union[str, datetime], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
            """Format datetime values."""
            if isinstance(value, str):
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return value.strftime(fmt)

        def format_currency(value: float, currency: str = "USD") -> str:
            """Format currency values."""
            if currency == "USD":
                if value >= 1_000_000_000:
                    return f"${value/1_000_000_000:.2f}B"
                elif value >= 1_000_000:
                    return f"${value/1_000_000:.2f}M"
                elif value >= 1_000:
                    return f"${value/1_000:.2f}K"
                else:
                    return f"${value:.2f}"
            return f"{value:.2f} {currency}"

        def format_percent(value: float, decimals: int = 1) -> str:
            """Format percentage values."""
            return f"{value:.{decimals}f}%"

        def format_score(value: float) -> str:
            """Format score values with color indicators."""
            if value >= 75:
                color = "high"
            elif value >= 50:
                color = "medium"
            else:
                color = "low"
            return f'<span class="score-{color}">{value:.1f}</span>'

        def format_risk(value: str) -> str:
            """Format risk level with appropriate styling."""
            risk_colors = {
                'low': 'success',
                'medium': 'warning',
                'high': 'danger',
                'critical': 'danger',
            }
            color = risk_colors.get(value.lower(), 'secondary')
            return f'<span class="badge badge-{color}">{value.upper()}</span>'

        def truncate_text(value: str, length: int = 100) -> str:
            """Truncate text to specified length."""
            if len(value) <= length:
                return value
            return value[:length-3] + "..."

        # Register filters
        self.env.filters['datetime'] = format_datetime
        self.env.filters['currency'] = format_currency
        self.env.filters['percent'] = format_percent
        self.env.filters['score'] = format_score
        self.env.filters['risk'] = format_risk
        self.env.filters['truncate'] = truncate_text

    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any],
        client_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Render a template with given context.

        Args:
            template_name: Name of the template file
            context: Template context data
            client_config: Optional client-specific customizations

        Returns:
            Rendered template as string

        Raises:
            TemplateNotFound: If template doesn't exist
        """
        try:
            # Merge client config into context
            if client_config:
                context['branding'] = client_config

            # Add global context
            context.setdefault('generated_at', datetime.utcnow())
            context.setdefault('year', datetime.utcnow().year)

            template = self.env.get_template(template_name)
            rendered = template.render(**context)

            logger.debug(f"Rendered template: {template_name}")
            return rendered

        except TemplateNotFound:
            logger.error(f"Template not found: {template_name}")
            raise
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            raise

    def get_template_for_report_type(self, report_type: str, format: str = "html") -> str:
        """
        Get the appropriate template name for a report type.

        Args:
            report_type: Type of report (daily_digest, weekly_watchlist, etc.)
            format: Output format (html, pdf)

        Returns:
            Template filename
        """
        template_map = {
            'daily_digest': f'daily_digest.{format}.j2',
            'weekly_watchlist': f'weekly_watchlist.{format}.j2',
            'deep_dive': f'deep_dive.{format}.j2',
            'alert': f'alert.{format}.j2',
        }

        return template_map.get(report_type, f'{report_type}.{format}.j2')

    def create_default_templates(self):
        """Create default template files if they don't exist."""
        templates = {
            'daily_digest.html.j2': self._get_daily_digest_template(),
            'weekly_watchlist.html.j2': self._get_weekly_watchlist_template(),
            'deep_dive.html.j2': self._get_deep_dive_template(),
            'alert.html.j2': self._get_alert_template(),
            'base.html.j2': self._get_base_template(),
        }

        for filename, content in templates.items():
            filepath = self.template_dir / filename
            if not filepath.exists():
                filepath.write_text(content)
                logger.info(f"Created default template: {filename}")

    def _get_base_template(self) -> str:
        """Base HTML template with common structure."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Biotech M&A Report{% endblock %}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; background: white; }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header .date { opacity: 0.9; font-size: 0.9em; }
        .section { margin: 30px 0; padding: 20px; }
        .section h2 {
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .score-high { color: #28a745; font-weight: bold; }
        .score-medium { color: #ffc107; font-weight: bold; }
        .score-low { color: #dc3545; font-weight: bold; }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }
        .badge-success { background: #28a745; color: white; }
        .badge-warning { background: #ffc107; color: #333; }
        .badge-danger { background: #dc3545; color: white; }
        .badge-secondary { background: #6c757d; color: white; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
            color: #667eea;
        }
        .chart-container {
            margin: 20px 0;
            text-align: center;
        }
        .chart-container img {
            max-width: 100%;
            height: auto;
        }
        .footer {
            margin-top: 40px;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
            border-top: 1px solid #e0e0e0;
        }
        {% if branding and branding.custom_css %}
        {{ branding.custom_css | safe }}
        {% endif %}
    </style>
</head>
<body>
    <div class="header">
        {% if branding and branding.logo_url %}
        <img src="{{ branding.logo_url }}" alt="Logo" style="max-height: 60px; margin-bottom: 20px;">
        {% endif %}
        <h1>{% block header_title %}Biotech M&A Report{% endblock %}</h1>
        <div class="date">{{ generated_at | datetime("%B %d, %Y") }}</div>
    </div>

    <div class="container">
        {% block content %}{% endblock %}
    </div>

    <div class="footer">
        <p>&copy; {{ year }} Biotech M&A Predictor. All rights reserved.</p>
        <p><small>This report is confidential and intended for authorized recipients only.</small></p>
    </div>
</body>
</html>
"""

    def _get_daily_digest_template(self) -> str:
        """Template for daily digest report."""
        return """{% extends "base.html.j2" %}

{% block title %}Daily M&A Digest - {{ generated_at | datetime("%Y-%m-%d") }}{% endblock %}

{% block header_title %}Daily M&A Digest{% endblock %}

{% block content %}
<div class="section">
    <h2>Executive Summary</h2>
    <div class="card">
        <p><strong>{{ metadata.total_signals }}</strong> signals detected in the past 24 hours</p>
        <p><strong>{{ metadata.companies_mentioned }}</strong> companies with activity</p>
        <p><strong>{{ metadata.high_priority_alerts }}</strong> high-priority alerts</p>
    </div>
</div>

{% if alerts %}
<div class="section">
    <h2>High Priority Alerts</h2>
    {% for alert in alerts %}
    <div class="card">
        <h3>{{ alert.company_name }} ({{ alert.alert_type }})</h3>
        <p>Severity: {{ alert.severity | risk }}</p>
        <p><small>{{ alert.created_at | datetime }}</small></p>
    </div>
    {% endfor %}
</div>
{% endif %}

<div class="section">
    <h2>Top Score Changes</h2>
    <table>
        <thead>
            <tr>
                <th>Company</th>
                <th>Ticker</th>
                <th>Current Score</th>
                <th>24h Change</th>
                <th>Risk Level</th>
            </tr>
        </thead>
        <tbody>
            {% for company in companies[:10] %}
            <tr>
                <td>{{ company.name }}</td>
                <td>{{ company.ticker }}</td>
                <td>{{ company.ma_score | score | safe }}</td>
                <td>{% if company.score_change_24h > 0 %}+{% endif %}{{ company.score_change_24h }}</td>
                <td>{{ company.risk_level | risk | safe }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div class="section">
    <h2>Recent Signals</h2>
    {% for signal in signals[:20] %}
    <div class="card">
        <h4>{{ signal.company_name }} ({{ signal.ticker }}) - {{ signal.signal_type }}</h4>
        <p>Significance: {{ signal.significance_score | percent }}</p>
        <p><small>{{ signal.detected_at | datetime }}</small></p>
    </div>
    {% endfor %}
</div>

{% if charts %}
<div class="section">
    <h2>Visualizations</h2>
    {% if charts.signals_by_type %}
    <div class="chart-container">
        <img src="data:image/png;base64,{{ charts.signals_by_type }}" alt="Signals by Type">
    </div>
    {% endif %}
    {% if charts.top_movers %}
    <div class="chart-container">
        <img src="data:image/png;base64,{{ charts.top_movers }}" alt="Top Movers">
    </div>
    {% endif %}
</div>
{% endif %}
{% endblock %}
"""

    def _get_weekly_watchlist_template(self) -> str:
        """Template for weekly watchlist report."""
        return """{% extends "base.html.j2" %}

{% block title %}Weekly M&A Watchlist - Week of {{ generated_at | datetime("%Y-%m-%d") }}{% endblock %}

{% block header_title %}Weekly M&A Watchlist{% endblock %}

{% block content %}
<div class="section">
    <h2>Watchlist Summary</h2>
    <div class="card">
        <p><strong>{{ metadata.total_candidates }}</strong> companies on watchlist</p>
        <p><strong>{{ metadata.new_entrants }}</strong> new entrants this week</p>
        <p><strong>{{ metadata.score_improvements }}</strong> significant score improvements</p>
        <p>Average Score: <strong>{{ metadata.average_score | round(1) }}</strong></p>
    </div>
</div>

{% if new_candidates %}
<div class="section">
    <h2>New Watchlist Entrants</h2>
    <table>
        <thead>
            <tr>
                <th>Company</th>
                <th>Ticker</th>
                <th>M&A Score</th>
            </tr>
        </thead>
        <tbody>
            {% for company in new_candidates %}
            <tr>
                <td>{{ company.name }}</td>
                <td>{{ company.ticker }}</td>
                <td>{{ company.ma_score | score | safe }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}

<div class="section">
    <h2>Top M&A Candidates</h2>
    <table>
        <thead>
            <tr>
                <th>Rank</th>
                <th>Company</th>
                <th>Ticker</th>
                <th>M&A Score</th>
                <th>7d Change</th>
                <th>Market Cap</th>
                <th>Risk Level</th>
            </tr>
        </thead>
        <tbody>
            {% for company in candidates[:25] %}
            <tr>
                <td>{{ loop.index }}</td>
                <td>{{ company.name }}</td>
                <td>{{ company.ticker }}</td>
                <td>{{ company.ma_score | score | safe }}</td>
                <td>{% if company.score_change_7d > 0 %}+{% endif %}{{ company.score_change_7d }}</td>
                <td>{{ company.market_cap | currency }}</td>
                <td>{{ company.risk_level | risk | safe }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

{% if charts %}
<div class="section">
    <h2>Analytics</h2>
    {% if charts.score_distribution %}
    <div class="chart-container">
        <img src="data:image/png;base64,{{ charts.score_distribution }}" alt="Score Distribution">
    </div>
    {% endif %}
    {% if charts.top_candidates %}
    <div class="chart-container">
        <img src="data:image/png;base64,{{ charts.top_candidates }}" alt="Top Candidates">
    </div>
    {% endif %}
</div>
{% endif %}
{% endblock %}
"""

    def _get_deep_dive_template(self) -> str:
        """Template for deep-dive company report."""
        return """{% extends "base.html.j2" %}

{% block title %}Deep Dive: {{ metadata.company_name }}{% endblock %}

{% block header_title %}Deep Dive Analysis: {{ metadata.company_name }}{% endblock %}

{% block content %}
<div class="section">
    <h2>Company Overview</h2>
    <div class="card">
        <p><strong>Ticker:</strong> {{ company.ticker }}</p>
        <p><strong>Market Cap:</strong> {{ company.market_cap | currency }}</p>
        <p><strong>Therapeutic Areas:</strong> {{ company.therapeutic_areas | join(", ") }}</p>
        <p><strong>M&A Score:</strong> {{ metadata.ma_score | score | safe }}</p>
        <p><strong>Risk Level:</strong> {{ metadata.risk_level | risk | safe }}</p>
    </div>
</div>

<div class="section">
    <h2>M&A Score Components</h2>
    <table>
        <tr>
            <td>Pipeline Score</td>
            <td>{{ current_score.pipeline_score | score | safe }}</td>
        </tr>
        <tr>
            <td>Financial Score</td>
            <td>{{ current_score.financial_score | score | safe }}</td>
        </tr>
        <tr>
            <td>Strategic Fit Score</td>
            <td>{{ current_score.strategic_fit_score | score | safe }}</td>
        </tr>
    </table>
</div>

<div class="section">
    <h2>Pipeline ({{ metadata.pipeline_drugs }} candidates)</h2>
    <table>
        <thead>
            <tr>
                <th>Drug Name</th>
                <th>Indication</th>
                <th>Phase</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {% for drug in pipeline %}
            <tr>
                <td>{{ drug.drug_name }}</td>
                <td>{{ drug.indication }}</td>
                <td>{{ drug.phase }}</td>
                <td>{{ drug.status }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div class="section">
    <h2>Potential Acquirers</h2>
    <table>
        <thead>
            <tr>
                <th>Company</th>
                <th>Match Score</th>
                <th>Strategic Fit</th>
                <th>Rationale</th>
            </tr>
        </thead>
        <tbody>
            {% for acquirer in potential_acquirers %}
            <tr>
                <td>{{ acquirer.acquirer_name }}</td>
                <td>{{ acquirer.match_score | score | safe }}</td>
                <td>{{ acquirer.strategic_alignment | percent }}</td>
                <td>{{ acquirer.rationale | truncate(100) }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

{% if charts %}
<div class="section">
    <h2>Analytics</h2>
    {% if charts.score_timeline %}
    <div class="chart-container">
        <img src="data:image/png;base64,{{ charts.score_timeline }}" alt="Score Timeline">
    </div>
    {% endif %}
    {% if charts.score_breakdown %}
    <div class="chart-container">
        <img src="data:image/png;base64,{{ charts.score_breakdown }}" alt="Score Breakdown">
    </div>
    {% endif %}
</div>
{% endif %}
{% endblock %}
"""

    def _get_alert_template(self) -> str:
        """Template for alert report."""
        return """{% extends "base.html.j2" %}

{% block title %}Alert: {{ metadata.company_name }}{% endblock %}

{% block header_title %}M&A Alert: {{ metadata.alert_type | upper }}{% endblock %}

{% block content %}
<div class="section">
    <h2 style="color: #dc3545;">ALERT: {{ metadata.company_name }}</h2>
    <div class="card" style="border-left: 4px solid #dc3545;">
        <p><strong>Alert Type:</strong> {{ metadata.alert_type }}</p>
        <p><strong>Severity:</strong> {{ metadata.severity | risk | safe }}</p>
        <p><strong>Score Change:</strong> {% if metadata.score_change > 0 %}+{% endif %}{{ metadata.score_change }}</p>
        <p><strong>Current Score:</strong> {{ current_score.ma_score | score | safe }}</p>
    </div>
</div>

<div class="section">
    <h2>Company Information</h2>
    <div class="card">
        <p><strong>Name:</strong> {{ company.name }}</p>
        <p><strong>Ticker:</strong> {{ company.ticker }}</p>
        <p><strong>Market Cap:</strong> {{ company.market_cap | currency }}</p>
    </div>
</div>

{% if trigger_signals %}
<div class="section">
    <h2>Triggering Signals</h2>
    {% for signal in trigger_signals %}
    <div class="card">
        <h4>{{ signal.signal_type }}</h4>
        <p>Significance: {{ signal.significance_score | percent }}</p>
        <p><small>{{ signal.detected_at | datetime }}</small></p>
    </div>
    {% endfor %}
</div>
{% endif %}

{% if charts and charts.score_trend %}
<div class="section">
    <h2>Recent Score Trend</h2>
    <div class="chart-container">
        <img src="data:image/png;base64,{{ charts.score_trend }}" alt="Score Trend">
    </div>
</div>
{% endif %}
{% endblock %}
"""


class ChartGenerator:
    """
    Generates charts and visualizations for reports.

    Supports both matplotlib (static) and plotly (interactive) charts.
    """

    def __init__(self, default_style: str = "seaborn-v0_8-darkgrid"):
        """
        Initialize the chart generator.

        Args:
            default_style: Default matplotlib style
        """
        self.default_style = default_style
        try:
            plt.style.use(default_style)
        except:
            # Fallback if style not available
            pass

        logger.info("ChartGenerator initialized")

    async def create_bar_chart(
        self,
        data: List[Dict[str, Any]],
        x_field: str,
        y_field: Optional[str] = None,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        figsize: tuple = (10, 6),
    ) -> str:
        """
        Create a bar chart and return as base64-encoded PNG.

        Args:
            data: List of data dictionaries
            x_field: Field name for x-axis
            y_field: Field name for y-axis (or count if None)
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            figsize: Figure size tuple

        Returns:
            Base64-encoded PNG image
        """
        try:
            fig, ax = plt.subplots(figsize=figsize)

            if y_field:
                # Use specific y values
                x_values = [item.get(x_field, '') for item in data]
                y_values = [item.get(y_field, 0) for item in data]
            else:
                # Count occurrences
                from collections import Counter
                x_values_raw = [item.get(x_field, '') for item in data]
                counts = Counter(x_values_raw)
                x_values = list(counts.keys())
                y_values = list(counts.values())

            ax.bar(x_values, y_values, color='#667eea')
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xlabel(xlabel or x_field, fontsize=12)
            ax.set_ylabel(ylabel or 'Count', fontsize=12)
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)

            return image_base64

        except Exception as e:
            logger.error(f"Error creating bar chart: {e}")
            return ""

    async def create_line_chart(
        self,
        data: List[Dict[str, Any]],
        x_field: str,
        y_fields: List[str],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        figsize: tuple = (12, 6),
    ) -> str:
        """
        Create a line chart with multiple series.

        Args:
            data: List of data dictionaries
            x_field: Field name for x-axis
            y_fields: List of field names for y-axis series
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            figsize: Figure size tuple

        Returns:
            Base64-encoded PNG image
        """
        try:
            fig, ax = plt.subplots(figsize=figsize)

            x_values = [item.get(x_field) for item in data]

            # Handle datetime x-axis
            if x_values and isinstance(x_values[0], (datetime, str)):
                if isinstance(x_values[0], str):
                    x_values = [datetime.fromisoformat(x.replace('Z', '+00:00')) for x in x_values]
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))

            colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe']

            for idx, y_field in enumerate(y_fields):
                y_values = [item.get(y_field, 0) for item in data]
                color = colors[idx % len(colors)]
                ax.plot(x_values, y_values, marker='o', label=y_field, color=color, linewidth=2)

            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xlabel(xlabel or x_field, fontsize=12)
            ax.set_ylabel(ylabel or 'Value', fontsize=12)
            ax.legend()
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)

            return image_base64

        except Exception as e:
            logger.error(f"Error creating line chart: {e}")
            return ""

    async def create_pie_chart(
        self,
        data: Dict[str, float],
        title: str = "",
        figsize: tuple = (8, 8),
    ) -> str:
        """
        Create a pie chart.

        Args:
            data: Dictionary mapping labels to values
            title: Chart title
            figsize: Figure size tuple

        Returns:
            Base64-encoded PNG image
        """
        try:
            fig, ax = plt.subplots(figsize=figsize)

            labels = list(data.keys())
            values = list(data.values())
            colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b']

            ax.pie(
                values,
                labels=labels,
                autopct='%1.1f%%',
                colors=colors,
                startangle=90,
            )
            ax.set_title(title, fontsize=14, fontweight='bold')
            plt.tight_layout()

            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)

            return image_base64

        except Exception as e:
            logger.error(f"Error creating pie chart: {e}")
            return ""

    async def create_histogram(
        self,
        data: List[float],
        bins: int = 20,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "Frequency",
        figsize: tuple = (10, 6),
    ) -> str:
        """
        Create a histogram.

        Args:
            data: List of numeric values
            bins: Number of bins
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            figsize: Figure size tuple

        Returns:
            Base64-encoded PNG image
        """
        try:
            fig, ax = plt.subplots(figsize=figsize)

            ax.hist(data, bins=bins, color='#667eea', alpha=0.7, edgecolor='black')
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xlabel(xlabel, fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
            ax.grid(True, alpha=0.3, axis='y')
            plt.tight_layout()

            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)

            return image_base64

        except Exception as e:
            logger.error(f"Error creating histogram: {e}")
            return ""

    async def create_plotly_chart(
        self,
        chart_type: str,
        data: Any,
        **kwargs,
    ) -> str:
        """
        Create an interactive Plotly chart and return as HTML div.

        Args:
            chart_type: Type of Plotly chart
            data: Chart data
            **kwargs: Additional chart parameters

        Returns:
            HTML div with embedded Plotly chart
        """
        try:
            if chart_type == "scatter":
                fig = px.scatter(data, **kwargs)
            elif chart_type == "line":
                fig = px.line(data, **kwargs)
            elif chart_type == "bar":
                fig = px.bar(data, **kwargs)
            else:
                raise ValueError(f"Unsupported chart type: {chart_type}")

            # Update layout
            fig.update_layout(
                template="plotly_white",
                font=dict(family="Arial, sans-serif"),
            )

            return fig.to_html(include_plotlyjs='cdn', div_id='plotly-chart')

        except Exception as e:
            logger.error(f"Error creating Plotly chart: {e}")
            return ""
