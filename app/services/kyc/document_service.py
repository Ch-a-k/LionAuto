from uuid import uuid4
from fastapi import UploadFile, HTTPException
from app.services.store.s3 import get_s3_service
from app.enums.document_type import DocumentType

class DocumentService:
    ALLOWED_TYPES = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "application/pdf": "pdf"
    }

    @classmethod
    def _validate_file(cls, file: UploadFile):
        if file.content_type not in cls.ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {list(cls.ALLOWED_TYPES.keys())}"
            )

    @classmethod
    async def upload_document(cls, file: UploadFile, user_id: int, doc_type: DocumentType):
        cls._validate_file(file)
        
        ext = cls.ALLOWED_TYPES[file.content_type]
        object_name = f"users/{user_id}/{doc_type.value}-{uuid4()}.{ext}"
        
        try:
            return await get_s3_service().upload_file(file, object_name)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Document upload failed: {str(e)}"
            )