import os
import logging
from typing import List
from mailjet_rest import Client

ENABLE_EMAIL = os.environ.get("ENABLE_EMAIL", "false").lower() == "true"

# --------------------------------------------------
# Logging setup
# --------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)

# --------------------------------------------------
# Mailjet configuration
# --------------------------------------------------
MAILJET_API_KEY = os.environ.get("MAILJET_API_KEY")
MAILJET_API_SECRET = os.environ.get("MAILJET_API_SECRET")
EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "TradeAdvisor")

if not MAILJET_API_KEY or not MAILJET_API_SECRET:
    logger.warning("Mailjet API credentials not configured. Email sending disabled.")

if not EMAIL_FROM:
    logger.warning("EMAIL_FROM not set. Email sending disabled.")

mailjet = Client(
    auth=(MAILJET_API_KEY, MAILJET_API_SECRET),
    version="v3.1"
)

# --------------------------------------------------
# Core email sending
# --------------------------------------------------
def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    retry_count: int = 3
) -> bool:
    """
    Send HTML email using Mailjet API.
    Email sending is controlled by ENABLE_EMAIL feature flag.
    """

    # =========================
    # Feature flag: email off
    # =========================
    if not ENABLE_EMAIL:
        logger.info(
            "ENABLE_EMAIL=false — skipping email send to %s", to_email
        )
        return False

    # =========================
    # Configuration validation
    # =========================
    if not MAILJET_API_KEY or not MAILJET_API_SECRET or not EMAIL_FROM:
        logger.error("Mailjet email service not configured")
        raise Exception("Mailjet email service not configured")

    # =========================
    # Input validation
    # =========================
    if not to_email or "@" not in to_email:
        raise ValueError(f"Invalid email address: {to_email}")

    # =========================
    # Mailjet payload
    # =========================
    payload = {
        "Messages": [
            {
                "From": {
                    "Email": EMAIL_FROM,
                    "Name": EMAIL_FROM_NAME
                },
                "To": [
                    {"Email": to_email}
                ],
                "Subject": subject,
                "HTMLPart": html_body
            }
        ]
    }

    # =========================
    # Send with retries
    # =========================
    for attempt in range(1, retry_count + 1):
        try:
            result = mailjet.send.create(data=payload)
            response_json = result.json()

            logger.info(
                "Mailjet response (attempt %d/%d): %s",
                attempt,
                retry_count,
                response_json
            )

            if result.status_code == 200:
                logger.info("Email sent successfully to %s", to_email)
                return True

            logger.error(
                "Mailjet error (attempt %d/%d): status=%s response=%s",
                attempt,
                retry_count,
                result.status_code,
                response_json
            )

        except Exception:
            logger.exception(
                "Unexpected Mailjet exception (attempt %d/%d)",
                attempt,
                retry_count
            )
            if attempt == retry_count:
                raise

    return False
# --------------------------------------------------
# Bulk email support
# --------------------------------------------------
def send_bulk_email(
    recipients: List[str],
    subject: str,
    html_body: str
) -> dict:
    """
    Send same email to multiple recipients
    """

    results = {
        "success": 0,
        "failed": 0,
        "failed_addresses": []
    }

    for email in recipients:
        try:
            send_email(email, subject, html_body)
            results["success"] += 1
        except Exception as e:
            logger.error(f"Failed to send to {email}: {e}")
            results["failed"] += 1
            results["failed_addresses"].append(email)

    return results

# --------------------------------------------------
# HTML template helper
# --------------------------------------------------
def create_email_template(
    title: str,
    content: str,
    footer: str = None
) -> str:
    default_footer = (
        footer
        or "This is an automated message from TradeAdvisor. Please do not reply."
    )

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{
    font-family: Arial, sans-serif;
    max-width: 600px;
    margin: auto;
    padding: 20px;
    color: #333;
}}
.header {{
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    padding: 24px;
    text-align: center;
    border-radius: 8px 8px 0 0;
}}
.content {{
    background: #ffffff;
    padding: 24px;
    border: 1px solid #e2e8f0;
}}
.footer {{
    background: #f7fafc;
    padding: 16px;
    font-size: 12px;
    color: #666;
    text-align: center;
    border-radius: 0 0 8px 8px;
    border: 1px solid #e2e8f0;
}}
</style>
</head>
<body>
    <div class="header">
        <h1>📈 {title}</h1>
    </div>
    <div class="content">
        {content}
    </div>
    <div class="footer">
        {default_footer}
    </div>
</body>
</html>
"""

# --------------------------------------------------
# Test helper
# --------------------------------------------------
def test_email_configuration() -> bool:
    try:
        body = create_email_template(
            "Mailjet Test",
            "<p>Your TradeAdvisor Mailjet configuration is working.</p>"
        )
        send_email(EMAIL_FROM, "TradeAdvisor Mailjet Test", body)
        return True
    except Exception as e:
        logger.error(f"Mailjet test failed: {e}")
        return False
