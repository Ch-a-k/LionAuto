import io
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from uuid import uuid4
from typing import Annotated
from enum import Enum
from app.services.store.s3contabo import s3_service
from PIL import Image, ImageFilter, ImageStat
import imghdr
import os
from loguru import logger
from PIL.ExifTags import TAGS
from PyPDF2 import PdfReader
import clamd
from app.core.config import settings
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/documents", tags=["Documents"])

class DocumentType(str, Enum):
    passport = "passport"
    driver_license = "driver_license"
    id_card = "id_card"

class User:
    id: str


def scan_for_viruses(file: UploadFile):
    try:
        # Connect via TCP instead of Unix socket
        cd = clamd.ClamdNetworkSocket(
            host=settings.CLAMAV_HOST,
            port=settings.CLAMAV_PORT,
            timeout=30
        )
        
        # Reset and read file
        file.file.seek(0)
        result = cd.instream(file.file)
        logger.debug(result)
        file.file.seek(0)
        
    except clamd.ConnectionError as e:
        logger.error(f"ClamAV connection failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Virus scanning service is currently unavailable"
        )
    except Exception as e:
        logger.error(f"ClamAV scan failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Virus scanning failed"
        )

    if result and result.get('stream') and result['stream'][0] == 'FOUND':
        virus_name = result['stream'][1]
        logger.warning(f"Virus detected: {virus_name}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Virus detected: {virus_name}"
        )

def check_pdf_encryption(file: UploadFile):
    """Проверка PDF-файла на наличие шифрования"""
    file.file.seek(0)
    reader = PdfReader(file.file)
    file.file.seek(0)

    if reader.is_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF file is encrypted. Please upload an unprotected document."
        )

def check_image_exif(file: UploadFile):
    """Проверка изображения на подозрительные EXIF-данные"""
    if file.content_type == "application/pdf":
        return  # для PDF не проверяем EXIF

    file.file.seek(0)
    image = Image.open(io.BytesIO(file.file.read()))
    file.file.seek(0)

    exif_data = image.getexif()
    if exif_data:
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            # Можно здесь добавить доп. проверки на подозрительные поля, если нужно
            if tag == "MakerNote" and value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Image contains embedded cryptographic data."
                )


def validate_file_size(file: UploadFile, max_size_mb: int = 5):
    """Проверка размера файла"""
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)  # Reset file pointer
    
    max_size = max_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {max_size_mb}MB"
        )

def validate_file_type(file: UploadFile):
    """Проверка типа файла"""
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    content_type = file.content_type
    
    if content_type not in allowed_types:
        # Дополнительная проверка для случаев, когда content_type может быть неправильным
        file.file.seek(0)
        file_header = file.file.read(1024)
        file.file.seek(0)
        
        if file_header.startswith(b'%PDF'):
            detected_type = "application/pdf"
        else:
            detected_type = imghdr.what(None, h=file_header)
            if detected_type == "jpeg":
                detected_type = "image/jpeg"
            elif detected_type == "png":
                detected_type = "image/png"
            else:
                detected_type = None
        
        if detected_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_types)}"
            )

def validate_image(file: UploadFile):
    """Проверка изображения (для не-PDF файлов)"""
    if file.content_type == "application/pdf":
        return  # Пропускаем PDF
    
    try:
        # Загружаем изображение
        file.file.seek(0)
        image = Image.open(io.BytesIO(file.file.read()))
        file.file.seek(0)
        
        # Проверка разрешения
        width, height = image.size
        if width < 1280 or height < 720:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image resolution too low. Minimum required: 1280x720 px"
            )
        
        # Проверка резкости (алгоритм Лапласиана)
        sharpness = calculate_sharpness(image)
        if sharpness < 95:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image is too blurry (sharpness score: {sharpness:.1f}%). Minimum required: 95%"
            )
        
        # Проверка на черно-белое изображение (для цветных документов)
        if is_grayscale(image):
            logger.warning(f"Black and white image detected for file {file.filename}")
            # Можно добавить исключение, если требуется цветное изображение
            # raise HTTPException(...)
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image file: {str(e)}"
        )

def calculate_sharpness(image) -> float:
    """Вычисление резкости изображения с помощью алгоритма Лапласиана"""
    # Конвертируем в grayscale для упрощения вычислений
    gray = image.convert('L')
    
    # Применяем фильтр Лапласиана
    laplacian = gray.filter(ImageFilter.FIND_EDGES)
    
    # Вычисляем дисперсию (меру резкости)
    variance = ImageStat.Stat(laplacian).var[0]
    
    # Нормализуем значение (эмпирически подобранные коэффициенты)
    sharpness = min(variance / 10, 100)  # Максимальное значение 100%
    
    return sharpness

def is_grayscale(image) -> bool:
    """Проверка, является ли изображение черно-белым"""
    # Если изображение уже в режиме 'L' (grayscale)
    if image.mode == 'L':
        return True
    
    # Проверяем разницу между каналами
    rgb = image.convert('RGB')
    stat = ImageStat.Stat(rgb)
    
    # Если стандартные отклонения каналов примерно равны - изображение grayscale
    if sum(stat.stddev) / 3 < 10:  # Эмпирический порог
        return True
    
    # Дополнительная проверка: сравниваем средние значения каналов
    means = stat.mean
    if max(means) - min(means) < 10:  # Эмпирический порог
        return True
    
    return False

@router.post("/upload", 
             responses={
                 200: {"description": "File uploaded successfully"},
                 400: {"description": "Invalid file type or size"},
                 401: {"description": "Unauthorized"},
                 415: {"description": "Unsupported media type"},
                 500: {"description": "Internal server error"}
             })
async def upload_document(
    file: Annotated[UploadFile, File(description="Document file to upload (jpg, png, pdf up to 5MB)")],
    doc_type: Annotated[DocumentType, "Type of document"],
    current_user: Annotated[User, Depends(get_current_user)]
) -> JSONResponse:
    """
    Upload a document with quality validation
    
    - **file**: Document file (jpg/png/pdf up to 5MB)
    - **doc_type**: Type of document (passport, driver_license, etc.)
    - Returns: S3 path, download URL and metadata
    """
    try:
        # 1. Проверка типа файла
        validate_file_type(file)
        
        # 2. Проверка размера файла (5MB максимум)
        validate_file_size(file, max_size_mb=5)
        
        # 3. Проверка качества изображения (для не-PDF)
        validate_image(file)
        
        # 4. Проверка на вирусы
        scan_for_viruses(file)

        # 5. Проверка PDF на шифрование
        if file.content_type == "application/pdf":
            check_pdf_encryption(file)
        else:
            # 6. Проверка изображения на EXIF криптографию
            check_image_exif(file)
        # Generate unique filename
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else ''
        object_name = f"users/{current_user.id}/{doc_type.value}-{uuid4()}.{file_ext}"
        
        # Upload to S3
        s3_path = await s3_service.upload_file(file, object_name)
        download_url = await s3_service.get_presigned_url(object_name)
        
        # Log successful upload
        logger.info(f"User {current_user.id} uploaded {doc_type.value} document: {object_name}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "s3_path": s3_path,
                "download_url": download_url,
                "expires_in": "1 hour",
                "document_type": doc_type.value,
                "user_id": str(current_user.id),
                "filename": file.filename
            }
        )
        
    except HTTPException as e:
        logger.error(f"Document upload failed for user {current_user.id}: {e.detail}")
        raise
    except Exception as e:
        logger.critical(f"Unexpected error during document upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process document upload"
        )