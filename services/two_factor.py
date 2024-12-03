import pyotp
from fastapi import HTTPException
from models import User

class TwoFactorService:
    @staticmethod
    def generate_secret():
        return pyotp.random_base32()

    @staticmethod
    def get_totp_uri(user: User, app_name: str = "MeowApp"):
        if not user.two_factor_secret:
            raise HTTPException(status_code=400, detail="2FA not set up for this user")
            
        totp = pyotp.TOTP(user.two_factor_secret)
        return totp.provisioning_uri(user.email, issuer_name=app_name)

    @staticmethod
    def verify_code(secret: str, code: str) -> bool:
        totp = pyotp.TOTP(secret)
        return totp.verify(code) 