from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from app.enums.document_type import DocumentType

class DocumentBase(BaseModel):
    type: DocumentType
    s3_path: str

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: int
    is_approved: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class UploadDocumentResponse(BaseModel):
    s3_path: str = Field(..., description="Path to the file in S3 storage")
    download_url: str = Field(..., description="Pre-signed URL to download the file")
    expires_in: str = Field(..., description="Expiration duration for the download URL")
    document_type: str = Field(..., description="Type of uploaded document")
    user_id: str = Field(..., description="ID of the user who uploaded the document")
    filename: str = Field(..., description="Original filename of the uploaded document")