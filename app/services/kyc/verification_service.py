# app/services/kyc/verification_service.py
from fastapi import UploadFile
from tortoise.transactions import atomic
from app.models import User, CustomerDocument
from app.enums.customer_status import CustomerStatus
from app.services.kyc.document_service import DocumentService

class VerificationService:
    @staticmethod
    @atomic()
    async def submit_kyc(user_id: int, form_data: dict, documents: list):
        user = await User.get(id=user_id)
        
        # Сохраняем документы
        for doc in documents:
            await CustomerDocument.create(
                user=user,
                type=doc['type'],
                s3_path=doc['path'],
                is_approved=False
            )
        # Обновляем статус
        user.status = CustomerStatus.UNDER_REVIEW
        await user.save()


async def process_kyc(user_id: int, passport: UploadFile, selfie: UploadFile):
    passport_path = await DocumentService.upload_document(passport, user_id, "passport")
    selfie_path = await DocumentService.upload_document(selfie, user_id, "selfie")