from pydantic import BaseModel

class BasicResponse(BaseModel):
    message: str
    
class BasicFileResponse(BasicResponse):
    file_name: str
    
class TwoFactorSetupResponse(BaseModel):
    qr_uri: str
    secret: str