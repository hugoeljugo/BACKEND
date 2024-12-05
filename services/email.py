from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import random
import string
from datetime import datetime, timedelta
from core.config import get_settings
import logging
from urllib.parse import urlencode

settings = get_settings()

logger = logging.getLogger(__name__)

def generate_verification_code() -> str:
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(to_email: str, verification_code: str) -> bool:
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
        msg['To'] = to_email
        msg['Subject'] = "Verify your email address"

        # Create verification link with the code as a parameter
        params = urlencode({'code': verification_code, 'email': to_email})
        verification_link = f"http://localhost:5173/verify-email?{params}"

        # Plain text version
        text_body = f"""
        Welcome to {settings.EMAIL_FROM_NAME}!
        
        You can verify your email address in two ways:

        1. Click the verification link below:
        {verification_link}

        2. Or use this verification code: {verification_code}
           Go to http://localhost:5173/verify-email and enter the code manually.
        
        Both the link and code will expire in {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes.
        """
        
        # HTML version
        html_body = f"""
        <html>
            <body>
                <h2>Welcome to {settings.EMAIL_FROM_NAME}!</h2>
                <p>You can verify your email address in two ways:</p>
                
                <h3>Option 1: Click the verification link</h3>
                <p><a href="{verification_link}">Click here to verify your email</a></p>
                
                <h3>Option 2: Use the verification code</h3>
                <p>Your verification code is: <strong>{verification_code}</strong></p>
                <p>Go to <a href="http://localhost:5173/verify-email">the verification page</a> and enter the code manually.</p>
                
                <p><em>Both the link and code will expire in {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes.</em></p>
            </body>
        </html>
        """
        
        # Attach both versions
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            #server.starttls()
            #server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
            
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        return False 