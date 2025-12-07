"""
Report Renderers - HTML and PDF rendering engines.

This module provides rendering capabilities to convert report data and templates
into HTML and PDF formats.
"""

import logging
from typing import Any, Dict, Optional
from pathlib import Path
from datetime import datetime
import tempfile

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from .templates import TemplateManager
from .generator import ReportContext, ReportType


logger = logging.getLogger(__name__)


class ReportRenderer:
    """Base class for report renderers."""

    def __init__(self, template_manager: TemplateManager):
        """
        Initialize the renderer.

        Args:
            template_manager: Template management system
        """
        self.template_manager = template_manager

    async def render(self, context: ReportContext) -> Any:
        """
        Render a report from context.

        Args:
            context: Report context with data

        Returns:
            Rendered output (format-specific)
        """
        raise NotImplementedError


class HTMLRenderer(ReportRenderer):
    """
    Renders reports as HTML.

    Converts report context and templates into formatted HTML suitable
    for email delivery or web display.
    """

    def __init__(
        self,
        template_manager: TemplateManager,
        include_inline_css: bool = True,
    ):
        """
        Initialize the HTML renderer.

        Args:
            template_manager: Template management system
            include_inline_css: Whether to inline CSS for email compatibility
        """
        super().__init__(template_manager)
        self.include_inline_css = include_inline_css

        logger.info("HTMLRenderer initialized")

    async def render(self, context: ReportContext) -> str:
        """
        Render report context as HTML.

        Args:
            context: Report context with data

        Returns:
            Rendered HTML string
        """
        try:
            # Get appropriate template for report type
            template_name = self.template_manager.get_template_for_report_type(
                context.report_type.value,
                format='html'
            )

            # Prepare template context
            template_context = self._prepare_context(context)

            # Render template
            html = self.template_manager.render_template(
                template_name,
                template_context,
                client_config=context.client_config,
            )

            # Optionally inline CSS for email compatibility
            if self.include_inline_css:
                html = await self._inline_css(html)

            logger.info(
                f"Rendered HTML report: {context.report_type.value}, "
                f"{len(html)} bytes"
            )

            return html

        except Exception as e:
            logger.error(f"Error rendering HTML report: {e}", exc_info=True)
            raise

    def _prepare_context(self, context: ReportContext) -> Dict[str, Any]:
        """
        Prepare template context from report context.

        Args:
            context: Report context

        Returns:
            Template context dictionary
        """
        template_context = {
            'generated_at': context.generated_at,
            'period_start': context.period_start,
            'period_end': context.period_end,
            'metadata': context.metadata,
            **context.data,  # Unpack all data fields
        }

        return template_context

    async def _inline_css(self, html: str) -> str:
        """
        Inline CSS for better email client compatibility.

        Args:
            html: HTML string with external/internal CSS

        Returns:
            HTML with inlined CSS
        """
        try:
            # For production, use a library like premailer
            # For now, just return as-is since CSS is already in <style> tags
            return html
        except Exception as e:
            logger.warning(f"Error inlining CSS: {e}")
            return html


class PDFRenderer(ReportRenderer):
    """
    Renders reports as PDF using WeasyPrint.

    Converts HTML reports into professional PDF documents suitable
    for archival and distribution.
    """

    def __init__(
        self,
        template_manager: TemplateManager,
        custom_css: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the PDF renderer.

        Args:
            template_manager: Template management system
            custom_css: Optional custom CSS for PDF styling
            base_url: Base URL for resolving relative paths
        """
        super().__init__(template_manager)
        self.custom_css = custom_css
        self.base_url = base_url

        # Configure fonts for better PDF rendering
        self.font_config = FontConfiguration()

        logger.info("PDFRenderer initialized")

    async def render(
        self,
        html_content: str,
        context: ReportContext,
        output_path: Optional[str] = None,
    ) -> bytes:
        """
        Render HTML content as PDF.

        Args:
            html_content: HTML string to convert
            context: Report context (for metadata)
            output_path: Optional path to save PDF file

        Returns:
            PDF as bytes
        """
        try:
            # Prepare CSS
            css_list = []
            if self.custom_css:
                css_list.append(CSS(string=self.custom_css, font_config=self.font_config))

            # Add PDF-specific CSS
            pdf_css = self._get_pdf_css()
            css_list.append(CSS(string=pdf_css, font_config=self.font_config))

            # Create HTML object
            html_obj = HTML(
                string=html_content,
                base_url=self.base_url,
            )

            # Render to PDF
            pdf_bytes = html_obj.write_pdf(
                stylesheets=css_list,
                font_config=self.font_config,
            )

            # Optionally save to file
            if output_path:
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_bytes(pdf_bytes)
                logger.info(f"PDF saved to: {output_path}")

            logger.info(
                f"Rendered PDF report: {context.report_type.value}, "
                f"{len(pdf_bytes)} bytes"
            )

            return pdf_bytes

        except Exception as e:
            logger.error(f"Error rendering PDF report: {e}", exc_info=True)
            raise

    def _get_pdf_css(self) -> str:
        """
        Get PDF-specific CSS for optimal printing.

        Returns:
            CSS string
        """
        return """
        @page {
            size: A4;
            margin: 2cm;
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }

        body {
            background: white !important;
        }

        .header {
            page-break-before: always;
        }

        .section {
            page-break-inside: avoid;
        }

        .card {
            page-break-inside: avoid;
        }

        table {
            page-break-inside: auto;
        }

        tr {
            page-break-inside: avoid;
            page-break-after: auto;
        }

        /* Ensure charts don't break across pages */
        .chart-container {
            page-break-inside: avoid;
        }

        /* Better print colors */
        .score-high { color: #1a7f37 !important; }
        .score-medium { color: #bf8700 !important; }
        .score-low { color: #cf222e !important; }

        /* Ensure badges are visible in print */
        .badge {
            border: 1px solid currentColor;
        }
        """

    async def render_from_context(
        self,
        context: ReportContext,
        html_renderer: HTMLRenderer,
        output_path: Optional[str] = None,
    ) -> bytes:
        """
        Convenience method to render PDF directly from context.

        Args:
            context: Report context
            html_renderer: HTML renderer to use
            output_path: Optional path to save PDF

        Returns:
            PDF as bytes
        """
        # First render to HTML
        html_content = await html_renderer.render(context)

        # Then convert to PDF
        return await self.render(html_content, context, output_path)


class PDFMetadataEnricher:
    """
    Enriches PDF files with metadata.

    Adds metadata like title, author, subject, keywords to PDF files.
    """

    @staticmethod
    def add_metadata(
        pdf_bytes: bytes,
        title: str,
        author: str = "Biotech M&A Predictor",
        subject: Optional[str] = None,
        keywords: Optional[list] = None,
    ) -> bytes:
        """
        Add metadata to PDF bytes.

        Args:
            pdf_bytes: Original PDF bytes
            title: Document title
            author: Document author
            subject: Document subject
            keywords: List of keywords

        Returns:
            PDF bytes with metadata
        """
        try:
            # Note: WeasyPrint doesn't support metadata directly
            # For production, use PyPDF2 or similar to add metadata
            # This is a placeholder implementation

            # from PyPDF2 import PdfReader, PdfWriter
            # reader = PdfReader(BytesIO(pdf_bytes))
            # writer = PdfWriter()
            #
            # for page in reader.pages:
            #     writer.add_page(page)
            #
            # writer.add_metadata({
            #     '/Title': title,
            #     '/Author': author,
            #     '/Subject': subject or '',
            #     '/Keywords': ', '.join(keywords) if keywords else '',
            # })
            #
            # output = BytesIO()
            # writer.write(output)
            # return output.getvalue()

            logger.debug(f"Metadata enrichment called for: {title}")
            return pdf_bytes

        except Exception as e:
            logger.warning(f"Error adding PDF metadata: {e}")
            return pdf_bytes


class ReportArchiver:
    """
    Archives generated reports to disk.

    Organizes reports by date and type for easy retrieval.
    """

    def __init__(self, archive_dir: str = "/tmp/reports"):
        """
        Initialize the archiver.

        Args:
            archive_dir: Base directory for archived reports
        """
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ReportArchiver initialized with dir: {archive_dir}")

    async def archive_report(
        self,
        report_content: bytes,
        report_type: str,
        format: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Archive a report to disk.

        Args:
            report_content: Report content as bytes
            report_type: Type of report
            format: Report format (html, pdf)
            metadata: Optional metadata

        Returns:
            Path to archived file
        """
        try:
            # Create directory structure: archive_dir/YYYY/MM/DD/
            now = datetime.utcnow()
            date_path = self.archive_dir / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
            date_path.mkdir(parents=True, exist_ok=True)

            # Generate filename
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            filename = f"{report_type}_{timestamp}.{format}"
            filepath = date_path / filename

            # Write report
            filepath.write_bytes(report_content)

            # Write metadata if provided
            if metadata:
                import json
                metadata_path = filepath.with_suffix(f'.{format}.meta.json')
                metadata_path.write_text(json.dumps(metadata, indent=2, default=str))

            logger.info(f"Report archived to: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Error archiving report: {e}", exc_info=True)
            raise

    async def get_archived_report(
        self,
        report_type: str,
        date: datetime,
        format: str = "pdf",
    ) -> Optional[bytes]:
        """
        Retrieve an archived report.

        Args:
            report_type: Type of report
            date: Report date
            format: Report format

        Returns:
            Report content as bytes, or None if not found
        """
        try:
            date_path = self.archive_dir / str(date.year) / f"{date.month:02d}" / f"{date.day:02d}"

            # Find matching file
            pattern = f"{report_type}_*.{format}"
            matches = list(date_path.glob(pattern))

            if matches:
                # Return most recent if multiple
                latest = sorted(matches)[-1]
                return latest.read_bytes()

            logger.warning(f"No archived report found: {report_type} on {date.date()}")
            return None

        except Exception as e:
            logger.error(f"Error retrieving archived report: {e}")
            return None

    async def cleanup_old_reports(self, days_to_keep: int = 90):
        """
        Clean up archived reports older than specified days.

        Args:
            days_to_keep: Number of days to retain reports
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            deleted_count = 0

            # Walk through archive directory
            for year_dir in self.archive_dir.iterdir():
                if not year_dir.is_dir():
                    continue

                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue

                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir():
                            continue

                        # Parse directory date
                        try:
                            dir_date = datetime(
                                int(year_dir.name),
                                int(month_dir.name),
                                int(day_dir.name)
                            )

                            if dir_date < cutoff_date:
                                # Delete all files in directory
                                for file in day_dir.iterdir():
                                    file.unlink()
                                    deleted_count += 1

                                # Remove empty directory
                                day_dir.rmdir()

                        except (ValueError, OSError) as e:
                            logger.warning(f"Error processing directory {day_dir}: {e}")

            logger.info(f"Cleaned up {deleted_count} old report files")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
