import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException
from loguru import logger
from app.core.config import settings

class S3Service:
    def __init__(self):
        self.client = boto3.client(
            's3',
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
            config=boto3.session.Config(signature_version='s3v4')
        )
        self.bucket = settings.S3_BUCKET_NAME
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
            logger.info(f"Bucket {self.bucket} exists")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                self._create_bucket()
            elif error_code == '403':
                raise HTTPException(
                    status_code=500,
                    detail="Access to bucket denied - check credentials"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"S3 error: {str(e)}"
                )

    def _create_bucket(self):
        try:
            if settings.S3_ENDPOINT_URL:  # Для MinIO
                self.client.create_bucket(Bucket=self.bucket)
            else:  # Для AWS S3
                self.client.create_bucket(
                    Bucket=self.bucket,
                    CreateBucketConfiguration={
                        'LocationConstraint': settings.S3_REGION
                    }
                )
            logger.success(f"Created bucket: {self.bucket}")
        except ClientError as e:
            logger.error(f"Bucket creation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to create S3 bucket"
            )

    async def upload_file(self, file, object_name: str) -> str:
        try:
            self.client.upload_fileobj(
                Fileobj=file.file,
                Bucket=self.bucket,
                Key=object_name,
                ExtraArgs={
                    'ContentType': file.content_type,
                    'ACL': 'private'
                }
            )
            logger.success(f"Uploaded {object_name} to {self.bucket}")
            return f"s3://{self.bucket}/{object_name}"
        except ClientError as e:
            logger.error(f"Upload failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"File upload failed: {str(e)}"
            )
        
    async def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': object_name},
                ExpiresIn=expires
            )
            return url
        except ClientError as e:
            logger.error(f"URL generation failed: {e}")
            raise HTTPException(500, "Failed to generate download URL")

s3_service = S3Service()