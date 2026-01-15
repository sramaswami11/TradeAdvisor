import re
from typing import Optional

# =========================
# Email Validation
# =========================

def validate_email(email: str) -> bool:
    """
    Validate email format
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    # Additional length checks
    if len(email) > 254 or len(email) < 5:
        return False
    
    return bool(re.match(pattern, email))


# =========================
# Ticker Symbol Validation
# =========================

def validate_ticker(ticker: str) -> Optional[str]:
    """
    Validate and sanitize ticker symbol
    
    Args:
        ticker: Ticker symbol to validate
        
    Returns:
        Sanitized ticker if valid, None otherwise
    """
    if not ticker or not isinstance(ticker, str):
        return None
    
    # Remove whitespace and convert to uppercase
    ticker = ticker.strip().upper()
    
    # Length check (most tickers are 1-10 characters)
    if len(ticker) < 1 or len(ticker) > 10:
        return None
    
    # Only allow alphanumeric characters, dots, and hyphens
    # Common formats: AAPL, BRK.B, BF-A
    if not re.match(r'^[A-Z0-9.-]+$', ticker):
        return None
    
    # Additional security: prevent obvious injection attempts
    dangerous_patterns = [
        r'\.\.', # Directory traversal
        r'<script', # XSS
        r'javascript:', # XSS
        r'SELECT|INSERT|UPDATE|DELETE|DROP', # SQL keywords
        r'UNION|JOIN|WHERE', # SQL keywords
    ]
    
    ticker_lower = ticker.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, ticker_lower, re.IGNORECASE):
            return None
    
    return ticker


# =========================
# General Input Sanitization
# =========================

def sanitize_user_input(text: str, max_length: int = 100) -> str:
    """
    Basic sanitization for user inputs
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Truncate to max length
    text = text[:max_length]
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    return text


def sanitize_name(name: str) -> str:
    """
    Sanitize user name input
    
    Args:
        name: Name to sanitize
        
    Returns:
        Sanitized name
    """
    if not name or not isinstance(name, str):
        return ""
    
    # Remove dangerous characters but keep spaces, letters, hyphens
    name = re.sub(r'[^a-zA-Z\s\'-]', '', name)
    
    # Normalize whitespace
    name = ' '.join(name.split())
    
    # Limit length
    return name[:100]


# =========================
# SQL Injection Prevention
# =========================

def is_safe_string(text: str) -> bool:
    """
    Check if string is safe from SQL injection
    
    Note: This is a secondary defense. Always use parameterized queries!
    
    Args:
        text: String to check
        
    Returns:
        True if appears safe, False otherwise
    """
    if not text or not isinstance(text, str):
        return False
    
    # Dangerous SQL keywords and patterns
    dangerous = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)',
        r'(--|#|\/\*|\*\/)',  # SQL comments
        r'(\bUNION\b.*\bSELECT\b)',
        r'(\bOR\b.*=.*)',  # OR 1=1 style attacks
        r'[\'"`;]',  # Quote characters
    ]
    
    for pattern in dangerous:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    
    return True


# =========================
# XSS Prevention
# =========================

def sanitize_html_output(text: str) -> str:
    """
    Sanitize text for HTML output (basic XSS prevention)
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text safe for HTML output
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Escape HTML special characters
    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&#x27;",
        ">": "&gt;",
        "<": "&lt;",
    }
    
    return "".join(html_escape_table.get(c, c) for c in text)


# =========================
# URL Validation
# =========================

def validate_url(url: str) -> bool:
    """
    Validate URL format
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    # Basic URL pattern
    pattern = r'^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(/.*)?$'
    
    return bool(re.match(pattern, url))


# =========================
# Numeric Validation
# =========================

def validate_positive_int(value: any, min_value: int = 1, max_value: int = None) -> Optional[int]:
    """
    Validate and convert to positive integer
    
    Args:
        value: Value to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Returns:
        Integer if valid, None otherwise
    """
    try:
        num = int(value)
        
        if num < min_value:
            return None
        
        if max_value is not None and num > max_value:
            return None
        
        return num
    except (ValueError, TypeError):
        return None


def validate_percentage(value: any) -> Optional[float]:
    """
    Validate percentage value (0-100)
    
    Args:
        value: Value to validate
        
    Returns:
        Float if valid, None otherwise
    """
    try:
        num = float(value)
        
        if 0 <= num <= 100:
            return num
        
        return None
    except (ValueError, TypeError):
        return None