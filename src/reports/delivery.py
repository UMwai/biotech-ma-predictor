"""
Report Delivery - Email, S3, and webhook delivery mechanisms.

This module handles the delivery of generated reports through various channels
with retry logic and delivery tracking.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import asyncio
import json
from pathlib import Path

from pydantic import BaseModel, Field, EmailStr
import httpx
import boto3
from botocore.exceptions import ClientError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail,
    Email,
    To,
    Content,
    Attachment,
    FileContent,
    FileName,
    FileType,
    Disposition,
)
import base64


logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    """Status of delivery attempts."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class DeliveryResult(BaseModel):
    """Result of a delivery attempt."""
    method: str
    status: DeliveryStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    recipient: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class DeliveryConfig:
    """Configuration for delivery mechanisms."""
    # Email
    sendgrid_api_key: Optional[str] = None
    from_email: str = "reports@biotech-ma.com"
    from_name: str = "Biotech M&A Predictor"

    # S3
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_prefix: str = "reports"

    # Webhook
    webhook_timeout: int = 30
    webhook_max_retries: int = 3

    # General
    max_retry_attempts: int = 3
    retry_delay_seconds: int = 5


class BaseDelivery:
    """Base class for delivery mechanisms."""

    def __init__(self, config: DeliveryConfig):
        """
        Initialize delivery mechanism.

        Args:
            config: Delivery configuration
        """
        self.config = config

    async def deliver(
        self,
        content: Union[str, bytes],
        recipient: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeliveryResult:
        """
        Deliver content to recipient.

        Args:
            content: Content to deliver
            recipient: Recipient identifier
            metadata: Optional metadata

        Returns:
            Delivery result
        """
        raise NotImplementedError

    async def _retry_with_backoff(
        self,
        func,
        *args,
        max_attempts: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """
        Retry a function with exponential backoff.

        Args:
            func: Async function to retry
            max_attempts: Maximum retry attempts
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        max_attempts = max_attempts or self.config.max_retry_attempts
        last_exception = None

        for attempt in range(max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    delay = self.config.retry_delay_seconds * (2 ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {max_attempts} attempts failed")

        raise last_exception


class EmailDelivery(BaseDelivery):
    """
    Delivers reports via email using SendGrid.

    Supports HTML and PDF attachments with customizable templates.
    """

    def __init__(self, config: DeliveryConfig):
        """
        Initialize email delivery.

        Args:
            config: Delivery configuration with SendGrid API key
        """
        super().__init__(config)

        if not config.sendgrid_api_key:
            raise ValueError("SendGrid API key is required for email delivery")

        self.client = SendGridAPIClient(config.sendgrid_api_key)

        logger.info("EmailDelivery initialized")

    async def deliver(
        self,
        content: Union[str, bytes],
        recipient: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeliveryResult:
        """
        Send report via email.

        Args:
            content: HTML content or report data
            recipient: Email address
            metadata: Optional metadata (subject, attachments, etc.)

        Returns:
            Delivery result
        """
        metadata = metadata or {}

        try:
            result = await self._retry_with_backoff(
                self._send_email,
                content,
                recipient,
                metadata,
            )

            return DeliveryResult(
                method="email",
                status=DeliveryStatus.SUCCESS,
                recipient=recipient,
                message=f"Email sent successfully to {recipient}",
                metadata={"sendgrid_response": result},
            )

        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}")
            return DeliveryResult(
                method="email",
                status=DeliveryStatus.FAILED,
                recipient=recipient,
                error=str(e),
            )

    async def _send_email(
        self,
        content: Union[str, bytes],
        recipient: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Internal method to send email via SendGrid.

        Args:
            content: Email content
            recipient: Email address
            metadata: Email metadata

        Returns:
            SendGrid response
        """
        # Prepare email components
        from_email = Email(self.config.from_email, self.config.from_name)
        to_email = To(recipient)

        subject = metadata.get(
            'subject',
            f"Biotech M&A Report - {datetime.utcnow().strftime('%Y-%m-%d')}"
        )

        # Determine content type
        if isinstance(content, bytes):
            # If bytes, assume it's an attachment
            html_content = metadata.get('html_content', '<p>Please see attached report.</p>')
        else:
            html_content = content

        mail = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )

        # Add attachments
        attachments = metadata.get('attachments', [])
        for attachment_data in attachments:
            attachment = Attachment(
                file_content=FileContent(attachment_data['content']),
                file_name=FileName(attachment_data['filename']),
                file_type=FileType(attachment_data.get('type', 'application/pdf')),
                disposition=Disposition('attachment'),
            )
            mail.add_attachment(attachment)

        # Add PDF attachment if content is bytes
        if isinstance(content, bytes) and metadata.get('report_type'):
            pdf_filename = f"{metadata['report_type']}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
            attachment = Attachment(
                file_content=FileContent(base64.b64encode(content).decode()),
                file_name=FileName(pdf_filename),
                file_type=FileType('application/pdf'),
                disposition=Disposition('attachment'),
            )
            mail.add_attachment(attachment)

        # Send email
        response = self.client.send(mail)

        return {
            'status_code': response.status_code,
            'headers': dict(response.headers),
        }

    async def send_bulk_email(
        self,
        content: Union[str, bytes],
        recipients: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[DeliveryResult]:
        """
        Send the same report to multiple recipients.

        Args:
            content: Report content
            recipients: List of email addresses
            metadata: Optional metadata

        Returns:
            List of delivery results
        """
        tasks = [
            self.deliver(content, recipient, metadata)
            for recipient in recipients
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    DeliveryResult(
                        method="email",
                        status=DeliveryStatus.FAILED,
                        recipient=recipients[i],
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)

        return processed_results


class S3Delivery(BaseDelivery):
    """
    Delivers reports to AWS S3.

    Uploads reports to organized S3 buckets with metadata tagging.
    """

    def __init__(self, config: DeliveryConfig):
        """
        Initialize S3 delivery.

        Args:
            config: Delivery configuration with S3 settings
        """
        super().__init__(config)

        if not config.s3_bucket:
            raise ValueError("S3 bucket name is required for S3 delivery")

        self.s3_client = boto3.client('s3', region_name=config.s3_region)
        self.bucket = config.s3_bucket

        logger.info(f"S3Delivery initialized for bucket: {self.bucket}")

    async def deliver(
        self,
        content: Union[str, bytes],
        recipient: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeliveryResult:
        """
        Upload report to S3.

        Args:
            content: Report content
            recipient: S3 key/path (can be client ID or custom path)
            metadata: Optional metadata

        Returns:
            Delivery result
        """
        metadata = metadata or {}

        try:
            result = await self._retry_with_backoff(
                self._upload_to_s3,
                content,
                recipient,
                metadata,
            )

            return DeliveryResult(
                method="s3",
                status=DeliveryStatus.SUCCESS,
                recipient=f"s3://{self.bucket}/{result['key']}",
                message=f"Uploaded to S3: {result['key']}",
                metadata=result,
            )

        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            return DeliveryResult(
                method="s3",
                status=DeliveryStatus.FAILED,
                recipient=recipient,
                error=str(e),
            )

    async def _upload_to_s3(
        self,
        content: Union[str, bytes],
        recipient: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Internal method to upload to S3.

        Args:
            content: Content to upload
            recipient: Base path/client ID
            metadata: Upload metadata

        Returns:
            Upload details
        """
        # Generate S3 key
        now = datetime.utcnow()
        report_type = metadata.get('report_type', 'report')
        format_ext = metadata.get('format', 'pdf')

        # Organize by client/date: reports/client_id/YYYY/MM/DD/report_type_timestamp.ext
        s3_key = (
            f"{self.config.s3_prefix}/"
            f"{recipient}/"
            f"{now.year}/{now.month:02d}/{now.day:02d}/"
            f"{report_type}_{now.strftime('%Y%m%d_%H%M%S')}.{format_ext}"
        )

        # Convert string to bytes if needed
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
            content_type = 'text/html'
        else:
            content_bytes = content
            content_type = metadata.get('content_type', 'application/pdf')

        # Prepare upload arguments
        upload_args = {
            'Bucket': self.bucket,
            'Key': s3_key,
            'Body': content_bytes,
            'ContentType': content_type,
            'Metadata': {
                k: str(v) for k, v in metadata.items()
                if k not in ['content', 'attachments']
            },
        }

        # Add server-side encryption
        upload_args['ServerSideEncryption'] = 'AES256'

        # Upload to S3 (synchronous boto3 call in executor)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.s3_client.put_object(**upload_args)
        )

        # Generate presigned URL for download
        presigned_url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': s3_key},
            ExpiresIn=86400,  # 24 hours
        )

        return {
            'key': s3_key,
            'bucket': self.bucket,
            'url': presigned_url,
            'size': len(content_bytes),
        }

    async def list_reports(
        self,
        client_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        List reports for a client in S3.

        Args:
            client_id: Client identifier
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of report metadata
        """
        try:
            prefix = f"{self.config.s3_prefix}/{client_id}/"

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.s3_client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=prefix,
                )
            )

            reports = []
            for obj in response.get('Contents', []):
                # Parse date from key
                key = obj['Key']
                reports.append({
                    'key': key,
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'url': self.s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': self.bucket, 'Key': key},
                        ExpiresIn=86400,
                    ),
                })

            return reports

        except ClientError as e:
            logger.error(f"Error listing S3 reports: {e}")
            return []


class WebhookDelivery(BaseDelivery):
    """
    Delivers reports via HTTP webhook.

    POSTs report data to client-specified endpoints with retry logic.
    """

    def __init__(self, config: DeliveryConfig):
        """
        Initialize webhook delivery.

        Args:
            config: Delivery configuration
        """
        super().__init__(config)

        self.client = httpx.AsyncClient(
            timeout=config.webhook_timeout,
            follow_redirects=True,
        )

        logger.info("WebhookDelivery initialized")

    async def deliver(
        self,
        content: Union[str, bytes],
        recipient: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeliveryResult:
        """
        Send report to webhook endpoint.

        Args:
            content: Report content
            recipient: Webhook URL
            metadata: Optional metadata

        Returns:
            Delivery result
        """
        metadata = metadata or {}

        try:
            result = await self._retry_with_backoff(
                self._post_webhook,
                content,
                recipient,
                metadata,
                max_attempts=self.config.webhook_max_retries,
            )

            return DeliveryResult(
                method="webhook",
                status=DeliveryStatus.SUCCESS,
                recipient=recipient,
                message=f"Webhook delivered successfully: {result['status']}",
                metadata=result,
            )

        except Exception as e:
            logger.error(f"Failed to deliver webhook to {recipient}: {e}")
            return DeliveryResult(
                method="webhook",
                status=DeliveryStatus.FAILED,
                recipient=recipient,
                error=str(e),
            )

    async def _post_webhook(
        self,
        content: Union[str, bytes],
        recipient: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Internal method to POST to webhook.

        Args:
            content: Content to send
            recipient: Webhook URL
            metadata: Request metadata

        Returns:
            Response details
        """
        # Prepare payload
        payload = {
            'report_type': metadata.get('report_type'),
            'generated_at': metadata.get('generated_at', datetime.utcnow()).isoformat(),
            'metadata': metadata,
        }

        # Add content based on type
        if isinstance(content, bytes):
            # Send as base64-encoded attachment
            payload['content'] = base64.b64encode(content).decode()
            payload['content_encoding'] = 'base64'
            payload['content_type'] = metadata.get('content_type', 'application/pdf')
        else:
            # Send as string
            payload['content'] = content
            payload['content_type'] = 'text/html'

        # Add authentication if provided
        headers = {}
        if 'webhook_secret' in metadata:
            headers['X-Webhook-Secret'] = metadata['webhook_secret']
        if 'webhook_signature' in metadata:
            headers['X-Webhook-Signature'] = metadata['webhook_signature']

        # POST to webhook
        response = await self.client.post(
            recipient,
            json=payload,
            headers=headers,
        )

        response.raise_for_status()

        return {
            'status': response.status_code,
            'response': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text[:1000],
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class DeliveryManager:
    """
    Manages multiple delivery mechanisms.

    Orchestrates report delivery across email, S3, and webhook channels.
    """

    def __init__(self, config: DeliveryConfig):
        """
        Initialize delivery manager.

        Args:
            config: Delivery configuration
        """
        self.config = config

        # Initialize delivery mechanisms
        self.deliveries: Dict[str, BaseDelivery] = {}

        if config.sendgrid_api_key:
            self.deliveries['email'] = EmailDelivery(config)

        if config.s3_bucket:
            self.deliveries['s3'] = S3Delivery(config)

        self.deliveries['webhook'] = WebhookDelivery(config)

        logger.info(
            f"DeliveryManager initialized with methods: {list(self.deliveries.keys())}"
        )

    async def deliver_report(
        self,
        report: Dict[str, Any],
        methods: List[str],
        recipients: Union[str, List[str]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[DeliveryResult]:
        """
        Deliver a report using specified methods.

        Args:
            report: Report data with rendered content
            methods: List of delivery methods ('email', 's3', 'webhook')
            recipients: Recipient(s) for delivery
            metadata: Optional metadata

        Returns:
            List of delivery results
        """
        if isinstance(recipients, str):
            recipients = [recipients]

        metadata = metadata or {}
        metadata.update(report.get('metadata', {}))

        results = []

        for method in methods:
            if method not in self.deliveries:
                logger.warning(f"Delivery method not configured: {method}")
                results.append(
                    DeliveryResult(
                        method=method,
                        status=DeliveryStatus.FAILED,
                        error=f"Delivery method not configured: {method}",
                    )
                )
                continue

            delivery = self.deliveries[method]

            # Determine content based on method and available formats
            if method == 'email':
                # Prefer HTML for email
                content = report.get('formats', {}).get('html', '')
                # Add PDF as attachment
                if 'pdf' in report.get('formats', {}):
                    pdf_content = report['formats']['pdf']
                    metadata.setdefault('attachments', []).append({
                        'content': base64.b64encode(pdf_content).decode(),
                        'filename': f"{report.get('report_type', 'report')}.pdf",
                        'type': 'application/pdf',
                    })
            elif method == 's3':
                # Prefer PDF for S3
                content = report.get('formats', {}).get('pdf', '')
                metadata['format'] = 'pdf'
            else:
                # For webhooks, send structured data
                content = json.dumps(report)

            # Deliver to each recipient
            for recipient in recipients:
                result = await delivery.deliver(content, recipient, metadata)
                results.append(result)

                # Log result
                if result.status == DeliveryStatus.SUCCESS:
                    logger.info(f"Successfully delivered via {method} to {recipient}")
                else:
                    logger.error(f"Failed to deliver via {method} to {recipient}: {result.error}")

        return results

    async def schedule_delivery(
        self,
        report_generator_func,
        methods: List[str],
        recipients: Union[str, List[str]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[DeliveryResult]:
        """
        Generate a report and deliver it.

        Args:
            report_generator_func: Async function that generates the report
            methods: Delivery methods
            recipients: Recipients
            metadata: Optional metadata

        Returns:
            List of delivery results
        """
        try:
            # Generate report
            report = await report_generator_func()

            # Deliver report
            results = await self.deliver_report(report, methods, recipients, metadata)

            return results

        except Exception as e:
            logger.error(f"Error in scheduled delivery: {e}", exc_info=True)
            return [
                DeliveryResult(
                    method="all",
                    status=DeliveryStatus.FAILED,
                    error=f"Report generation failed: {str(e)}",
                )
            ]

    async def close(self):
        """Close all delivery mechanisms."""
        for delivery in self.deliveries.values():
            if hasattr(delivery, 'close'):
                await delivery.close()

        logger.info("DeliveryManager closed")


class DeliveryTracker:
    """
    Tracks delivery attempts and results.

    Maintains a log of all delivery attempts for auditing and debugging.
    """

    def __init__(self, db_pool=None):
        """
        Initialize delivery tracker.

        Args:
            db_pool: Optional database pool for persistent tracking
        """
        self.db_pool = db_pool
        self.in_memory_log: List[DeliveryResult] = []

        logger.info("DeliveryTracker initialized")

    async def log_delivery(self, result: DeliveryResult):
        """
        Log a delivery result.

        Args:
            result: Delivery result to log
        """
        # Add to in-memory log
        self.in_memory_log.append(result)

        # Persist to database if available
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO delivery_log
                        (method, status, timestamp, recipient, message, error, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                        result.method,
                        result.status.value,
                        result.timestamp,
                        result.recipient,
                        result.message,
                        result.error,
                        json.dumps(result.metadata),
                    )
            except Exception as e:
                logger.error(f"Error persisting delivery log: {e}")

    async def get_delivery_history(
        self,
        method: Optional[str] = None,
        recipient: Optional[str] = None,
        limit: int = 100,
    ) -> List[DeliveryResult]:
        """
        Retrieve delivery history.

        Args:
            method: Optional method filter
            recipient: Optional recipient filter
            limit: Maximum results

        Returns:
            List of delivery results
        """
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    query = "SELECT * FROM delivery_log WHERE 1=1"
                    params = []

                    if method:
                        params.append(method)
                        query += f" AND method = ${len(params)}"

                    if recipient:
                        params.append(recipient)
                        query += f" AND recipient = ${len(params)}"

                    query += f" ORDER BY timestamp DESC LIMIT {limit}"

                    rows = await conn.fetch(query, *params)

                    return [
                        DeliveryResult(
                            method=row['method'],
                            status=DeliveryStatus(row['status']),
                            timestamp=row['timestamp'],
                            recipient=row['recipient'],
                            message=row['message'],
                            error=row['error'],
                            metadata=json.loads(row['metadata']) if row['metadata'] else {},
                        )
                        for row in rows
                    ]
            except Exception as e:
                logger.error(f"Error retrieving delivery history: {e}")

        # Fallback to in-memory log
        filtered = self.in_memory_log

        if method:
            filtered = [r for r in filtered if r.method == method]

        if recipient:
            filtered = [r for r in filtered if r.recipient == recipient]

        return filtered[-limit:]
