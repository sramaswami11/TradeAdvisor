import os
import smtplib
import pytest
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================
# Load env vars
# =========================

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# =========================
# Pytest markers
# =========================

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not EMAIL_USER or not EMAIL_PASSWORD,
        reason="EMAIL_USER or EMAIL_PASSWORD environment variables not set"
    )
]

# =========================
# Email config
# =========================

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587

TO_EMAIL = "sramaswami11@gmail.com"  # send to yourself for sanity test

# =========================
# Test
# =========================

def test_smtp_email_sanity():
    """
    Sends a real email to verify SMTP credentials.
    This is an integration test and will be skipped unless
    EMAIL_USER and EMAIL_PASSWORD are configured.
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_USER
    msg["To"] = TO_EMAIL
    msg["Subject"] = "TradeAdvisor SMTP Sanity Test ✅"

    html_body = """
    <h2>🎉 Success!</h2>
    <p>If you received this email, then:</p>
    <ul>
      <li>Gmail SMTP is working</li>
      <li>Your App Password is valid</li>
      <li>Python smtplib is configured correctly</li>
    </ul>
    <p>You are good to go 🚀</p>
    """

    msg.attach(MIMEText(html_body, "html"))

    print(">>> Connecting to Gmail SMTP...")

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        print(">>> Logging in as", EMAIL_USER)
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, TO_EMAIL, msg.as_string())

    print("✅ Sanity test email sent successfully!")
