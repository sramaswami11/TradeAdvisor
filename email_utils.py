import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Email configuration from environment variables
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# Validate email configuration
if not EMAIL_USER or not EMAIL_PASSWORD:
    logger.warning("Email credentials not configured. Email functionality will be disabled.")


def send_email(to_email: str, subject: str, html_body: str, retry_count: int = 3) -> bool:
    """
    Send HTML email with error handling and retry logic
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_body: HTML content of the email
        retry_count: Number of retry attempts on failure
        
    Returns:
        True if email sent successfully, False otherwise
    """
    # Check if email is configured
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logger.error("Email credentials not configured")
        raise Exception("Email service not configured")
    
    # Validate email address (basic check)
    if not to_email or '@' not in to_email:
        logger.error(f"Invalid email address: {to_email}")
        raise ValueError("Invalid email address")
    
    for attempt in range(retry_count):
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = EMAIL_USER
            msg["To"] = to_email
            msg["Subject"] = subject
            
            # Attach HTML content
            msg.attach(MIMEText(html_body, "html"))
            
            # Send email
            with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=10) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            raise Exception("Email authentication failed. Check credentials.")
            
        except smtplib.SMTPException as e:
            logger.warning(f"SMTP error on attempt {attempt + 1}/{retry_count}: {e}")
            if attempt == retry_count - 1:
                raise Exception(f"Failed to send email after {retry_count} attempts")
                
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            if attempt == retry_count - 1:
                raise Exception(f"Failed to send email: {str(e)}")
    
    return False


def send_bulk_email(recipients: List[str], subject: str, html_body: str) -> dict:
    """
    Send the same email to multiple recipients
    
    Args:
        recipients: List of recipient email addresses
        subject: Email subject
        html_body: HTML content of the email
        
    Returns:
        Dictionary with success/failure counts and failed addresses
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


def create_email_template(title: str, content: str, footer: str = None) -> str:
    """
    Create a standardized HTML email template
    
    Args:
        title: Email title/header
        content: Main email content (HTML)
        footer: Optional footer text
        
    Returns:
        Complete HTML email string
    """
    default_footer = footer or "This is an automated message from TradeAdvisor. Please do not reply to this email."
    
    template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }}
            .content {{
                background: #ffffff;
                padding: 30px;
                border-left: 1px solid #e2e8f0;
                border-right: 1px solid #e2e8f0;
            }}
            .footer {{
                background: #f7fafc;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #666;
                border-radius: 0 0 10px 10px;
                border: 1px solid #e2e8f0;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background: #4299e1;
                color: white !important;
                text-decoration: none;
                border-radius: 5px;
                margin: 10px 0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #e2e8f0;
            }}
            th {{
                background: #4299e1;
                color: white;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1 style="margin: 0;">📈 {title}</h1>
        </div>
        <div class="content">
            {content}
        </div>
        <div class="footer">
            <p>{default_footer}</p>
            <p style="margin-top: 10px;">
                <a href="https://tradeadvisor.com" style="color: #4299e1; text-decoration: none;">TradeAdvisor</a>
            </p>
        </div>
    </body>
    </html>
    """
    
    return template


def test_email_configuration() -> bool:
    """
    Test email configuration by sending a test email
    
    Returns:
        True if test successful, False otherwise
    """
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logger.error("Email not configured")
        return False
    
    try:
        test_body = create_email_template(
            "Email Configuration Test",
            "<p>This is a test email to verify your TradeAdvisor email configuration is working correctly.</p>"
        )
        
        send_email(EMAIL_USER, "TradeAdvisor Test Email", test_body)
        return True
        
    except Exception as e:
        logger.error(f"Email test failed: {e}")
        return False