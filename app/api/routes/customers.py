# app/api/routes/customers.py
from fastapi import APIRouter, Depends, UploadFile, File, Request
from app.services.kyc.verification_service import VerificationService
from app.schemas.customer import KYCSubmitRequest, KYCStatusResponse

router = APIRouter()

@router.post("/submit", response_model=KYCStatusResponse)
async def submit_kyc(
    form_data: KYCSubmitRequest,
    passport: UploadFile = File(...),
    selfie: UploadFile = File(...)
):
    ...
    # documents = [
    #     {"type": "passport", "path": await upload_to_s3(passport)},
    #     {"type": "selfie", "path": await upload_to_s3(selfie)}
    # ]
    # return await VerificationService.submit_kyc(
    #     user_id=1,  # Получать из auth
    #     form_data=form_data.dict(),
    #     documents=documents
    # )


@router.post("/some-action")
async def some_action(request: Request):
    # ... бизнес-логика ...
    pass
    # Отправка события в Kafka
    # request.app.state.kafka_producer.produce(
    #     topic="audit_logs",
    #     value=json.dumps({
    #         "event": "some_action",
    #         "user_id": user.id,
    #         "timestamp": datetime.utcnow().isoformat()
    #     })
    # )