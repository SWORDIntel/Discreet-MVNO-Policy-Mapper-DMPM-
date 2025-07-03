"""
Webhook notification system for GHOST DMPM
Supports: Slack, Discord, Email, Generic webhooks
"""

import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional # Added Optional
import logging # For logging within the class

# Assuming GhostConfig is accessible via from ghost_dmpm.core.config import GhostConfig
# However, to avoid circular dependencies if webhooks are used by core components,
# it might be better to pass a simpler config dictionary or specific values.
# For now, following the directive to use GhostConfig.
from ghost_dmpm.core.config import GhostConfig

class GhostWebhooks:
    """
    Handles sending notifications via various webhook services.
    """
    def __init__(self, config: GhostConfig):
        """
        Initializes the GhostWebhooks system.

        Args:
            config (GhostConfig): The system's configuration object.
        """
        self.config = config
        self.logger = config.get_logger("GhostWebhooks") # Get a logger instance

        # Webhook configurations will be fetched from self.config as needed
        # e.g., self.config.get('webhooks.slack_url')
        self.slack_url = self.config.get('webhooks.slack_url')
        self.discord_url = self.config.get('webhooks.discord_url')
        self.email_config = self.config.get('webhooks.email_smtp', {}) # an empty dict if not present

        self.default_timeout = self.config.get('webhooks.timeout', 10) # Default timeout for requests
        self.default_retries = self.config.get('webhooks.retries', 3) # Default retries

    def _send_request_with_retry(self, url: str, method: str = "POST", payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> bool:
        """
        Internal helper to send HTTP requests with retry logic.
        """
        if not url:
            self.logger.error(f"No URL provided for generic webhook.")
            return False

        for attempt in range(self.default_retries):
            try:
                if method.upper() == "POST":
                    response = requests.post(url, json=payload, headers=headers, timeout=self.default_timeout)
                elif method.upper() == "GET": # Though less common for webhooks
                    response = requests.get(url, params=payload, headers=headers, timeout=self.default_timeout)
                else:
                    self.logger.error(f"Unsupported HTTP method: {method}")
                    return False

                response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
                self.logger.info(f"Successfully sent {method} request to {url} (attempt {attempt + 1}).")
                return True
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Failed to send {method} request to {url} (attempt {attempt + 1}/{self.default_retries}): {e}")
                if attempt == self.default_retries - 1: # Last attempt
                    self.logger.error(f"All {self.default_retries} retries failed for {method} request to {url}.")
                    return False
            except Exception as e: # Catch any other unexpected errors
                self.logger.error(f"Unexpected error sending {method} request to {url} (attempt {attempt + 1}): {e}", exc_info=True)
                return False
        return False # Should be unreachable if loop completes

    def send_slack(self, alert_title: str, message: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Sends a notification to Slack using a webhook URL.

        Args:
            alert_title (str): The main title/summary of the alert.
            message (str): The primary message content.
            details (Optional[Dict[str, Any]]): Additional details to include as fields.

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        if not self.slack_url:
            self.logger.warning("Slack URL not configured. Skipping Slack notification.")
            return False

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":ghost: GHOST DMPM Alert: {alert_title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]

        if details:
            fields = []
            for key, value in details.items():
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{key.replace('_', ' ').title()}*\n{value}"
                })
            if fields:
                 blocks.append({"type": "section", "fields": fields})

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
            ]
        })

        payload = {"blocks": blocks}
        headers = {'Content-Type': 'application/json'}

        self.logger.info(f"Sending Slack notification: {alert_title}")
        return self._send_request_with_retry(self.slack_url, payload=payload, headers=headers)

    def send_discord(self, alert_title: str, message: str, details: Optional[Dict[str, Any]] = None, color: int = 0x7289DA) -> bool:
        """
        Sends a notification to Discord using a webhook URL.

        Args:
            alert_title (str): The title for the embed.
            message (str): The description for the embed.
            details (Optional[Dict[str, Any]]): Additional details to include as fields in the embed.
            color (int): Decimal color code for the embed's side strip.

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        if not self.discord_url:
            self.logger.warning("Discord URL not configured. Skipping Discord notification.")
            return False

        embed = {
            "title": f":ghost: GHOST DMPM Alert: {alert_title}",
            "description": message,
            "color": color,
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "GHOST DMPM Notification System"}
        }

        if details:
            fields = []
            for key, value in details.items():
                fields.append({
                    "name": key.replace('_', ' ').title(),
                    "value": str(value), # Ensure value is string
                    "inline": len(str(value)) < 40 # Heuristic for inline
                })
            if fields:
                embed["fields"] = fields

        payload = {"embeds": [embed]}
        headers = {'Content-Type': 'application/json'}

        self.logger.info(f"Sending Discord notification: {alert_title}")
        return self._send_request_with_retry(self.discord_url, payload=payload, headers=headers)

    def send_email(self, subject: str, body_html: str, recipient_emails: list[str], body_text: Optional[str] = None) -> bool:
        """
        Sends an email notification using SMTP.

        Args:
            subject (str): The subject of the email.
            body_html (str): The HTML content of the email.
            recipient_emails (list[str]): A list of recipient email addresses.
            body_text (Optional[str]): Plain text version of the email body. If None, HTML body will be used.

        Returns:
            bool: True if the email was sent successfully to all recipients, False otherwise.
        """
        if not self.email_config or not all(k in self.email_config for k in ['host', 'port', 'username', 'password', 'sender_email']):
            self.logger.warning("Email SMTP settings not fully configured. Skipping email notification.")
            return False

        if not recipient_emails:
            self.logger.warning("No recipient emails provided for email notification.")
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[GHOST DMPM] {subject}"
        msg['From'] = self.email_config['sender_email']
        msg['To'] = ", ".join(recipient_emails)

        text_part = MIMEText(body_text if body_text else body_html, 'plain' if body_text else 'html')
        msg.attach(text_part)
        if body_text and body_html: # If both provided, add HTML part
             html_part = MIMEText(body_html, 'html')
             msg.attach(html_part)

        try:
            self.logger.info(f"Attempting to send email to {', '.join(recipient_emails)} with subject: {subject}")
            with smtplib.SMTP(self.email_config['host'], self.email_config['port']) as server:
                if self.email_config.get('use_tls', True): # Default to TLS
                    server.starttls()
                server.login(self.email_config['username'], self.email_config['password'])
                server.sendmail(self.email_config['sender_email'], recipient_emails, msg.as_string())
            self.logger.info(f"Email sent successfully to {', '.join(recipient_emails)}.")
            return True
        except smtplib.SMTPException as e:
            self.logger.error(f"SMTP error sending email: {e}", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending email: {e}", exc_info=True)
            return False

    def send_generic(self, url: str, payload: Dict[str, Any], method: str = "POST", headers: Optional[Dict[str, str]] = None) -> bool:
        """
        Sends a notification to a generic webhook URL.

        Args:
            url (str): The generic webhook URL.
            payload (Dict[str, Any]): The JSON payload to send.
            method (str): HTTP method to use (e.g., "POST", "GET"). Defaults to "POST".
            headers (Optional[Dict[str, str]]): Optional custom headers.

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        if not url: # Already checked in _send_request_with_retry, but good for direct calls too
            self.logger.error("Generic webhook URL not provided.")
            return False

        final_headers = {'Content-Type': 'application/json'}
        if headers:
            final_headers.update(headers)

        self.logger.info(f"Sending generic webhook notification to {url} via {method}.")
        return self._send_request_with_retry(url, method=method, payload=payload, headers=final_headers)

# Example usage (for testing purposes, typically not part of the library code)
if __name__ == '__main__':
    # This example requires a dummy GhostConfig or a real one.
    # For simplicity, we'll mock parts of it.
    class MockGhostConfig:
        def __init__(self):
            self.data = {
                "webhooks": {
                    "slack_url": os.environ.get("SLACK_TEST_URL"), # Read from env for testing
                    "discord_url": os.environ.get("DISCORD_TEST_URL"), # Read from env
                    "email_smtp": {
                        "host": "smtp.example.com", # Replace with your SMTP server
                        "port": 587,
                        "username": "user@example.com",
                        "password": "password",
                        "sender_email": "ghost@example.com",
                        "use_tls": True
                    },
                    "timeout": 10,
                    "retries": 2
                },
                "logging": {"level": "INFO"} # Basic logging for example
            }
            self.project_root = Path(".") # Dummy project root

        def get(self, key, default=None):
            keys = key.split('.')
            val = self.data
            try:
                for k in keys:
                    val = val[k]
                return val
            except KeyError:
                return default

        def get_logger(self, name):
            # Basic logger for example
            logger = logging.getLogger(name)
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                logger.addHandler(handler)
                logger.setLevel(self.get(f"logging.level", "INFO"))
            return logger

    print("GhostWebhooks Example Usage (requires environment variables for URLs/credentials)")

    # Create a mock config. In real use, this comes from the application.
    mock_config = MockGhostConfig()

    webhooks = GhostWebhooks(mock_config)

    # Test Slack (set SLACK_TEST_URL environment variable)
    if mock_config.get("webhooks.slack_url"):
        print("\nTesting Slack...")
        slack_sent = webhooks.send_slack(
            alert_title="Test Slack Alert",
            message="This is a *test message* from GhostWebhooks to Slack.",
            details={"mvno_name": "TestMVNO", "score_change": "+0.5", "reason": "Policy update detected"}
        )
        print(f"Slack send status: {'Success' if slack_sent else 'Failed'}")
    else:
        print("\nSLACK_TEST_URL not set. Skipping Slack test.")

    # Test Discord (set DISCORD_TEST_URL environment variable)
    if mock_config.get("webhooks.discord_url"):
        print("\nTesting Discord...")
        discord_sent = webhooks.send_discord(
            alert_title="Test Discord Alert",
            message="This is a test message from GhostWebhooks to Discord.",
            details={"event_type": "System Maintenance", "status": "Scheduled", "duration_hours": 2},
            color=0xFF5733 # Orange color
        )
        print(f"Discord send status: {'Success' if discord_sent else 'Failed'}")
    else:
        print("\nDISCORD_TEST_URL not set. Skipping Discord test.")

    # Test Email (configure email_smtp in MockGhostConfig or use env vars if you adapt it)
    # Note: This will attempt a real email send. Use with caution and valid credentials.
    # For this example, it's mostly placeholder unless credentials are real.
    print("\nTesting Email...")
    if mock_config.get("webhooks.email_smtp.host") != "smtp.example.com": # Basic check if it's not placeholder
        email_sent = webhooks.send_email(
            subject="GHOST DMPM Test Email",
            body_html="<h1>Test Email</h1><p>This is a <b>test email</b> from GhostWebhooks.</p>",
            recipient_emails=["your_test_email@example.com"], # Replace with a test recipient
            body_text="Test Email\nThis is a test email from GhostWebhooks."
        )
        print(f"Email send status: {'Success' if email_sent else 'Failed'}")
    else:
        print("SMTP settings in MockGhostConfig are placeholders. Skipping actual Email test.")

    # Test Generic Webhook (use a service like webhook.site for testing)
    generic_test_url = os.environ.get("GENERIC_TEST_URL")
    if generic_test_url:
        print("\nTesting Generic Webhook...")
        generic_sent = webhooks.send_generic(
            url=generic_test_url,
            payload={"event": "test_event", "data": {"value1": "abc", "value2": 123}},
            headers={"X-Custom-Header": "GhostDMPMTest"}
        )
        print(f"Generic webhook send status: {'Success' if generic_sent else 'Failed'}")
    else:
        print("\nGENERIC_TEST_URL not set. Skipping Generic Webhook test.")

    print("\nExample usage finished.")

# Required config structure in ghost_config.json for webhooks:
# {
#   "webhooks": {
#     "slack_url": "YOUR_SLACK_WEBHOOK_URL_HERE_OR_NULL",
#     "discord_url": "YOUR_DISCORD_WEBHOOK_URL_HERE_OR_NULL",
#     "email_smtp": {
#       "host": "smtp.example.com",
#       "port": 587,
#       "username": "your_email_username",
#       "password": "your_email_password",
#       "sender_email": "notifications@ghostdmpm.example.com",
#       "use_tls": true // or false if not using TLS/STARTTLS
#     },
#     "timeout": 10, // Optional: default timeout for HTTP requests
#     "retries": 3   // Optional: default number of retries for HTTP requests
#   }
# }

# To use this module:
# from ghost_dmpm.core.config import GhostConfig
# from ghost_dmpm.enhancements.webhooks import GhostWebhooks
#
# config = GhostConfig()
# webhook_sender = GhostWebhooks(config)
# webhook_sender.send_slack("New MVNO Policy Change", "Details about the change...", {"mvno": "ExampleTel"})
# webhook_sender.send_email("Important System Alert", "<html><body>...</body></html>", ["admin@example.com"])
# ... etc.
