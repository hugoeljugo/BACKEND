from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import random
import string
from datetime import datetime, timedelta
from core.config import get_settings
import logging

settings = get_settings()

logger = logging.getLogger(__name__)

def generate_verification_code() -> str:
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(to_email: str, verification_code: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
        msg['To'] = to_email
        msg['Subject'] = "Verify your email address"

        body = f"""
        Welcome to {settings.EMAIL_FROM_NAME}!
        
        Your verification code is: {verification_code}
        
        This code will expire in {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes.
        """
        
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            #server.starttls()
            #server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
            
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        return False 