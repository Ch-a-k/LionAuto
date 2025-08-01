#!/bin/bash
set -e

until curl -s -o /dev/null http://minio:9000/minio/health/ready; do
  echo "Waiting for MinIO to be ready..."
  sleep 2
done

mc alias set local http://minio:9000 ${S3_ACCESS_KEY} ${S3_SECRET_KEY}
mc mb local/${S3_BUCKET_NAME} || true
mc policy set download local/${S3_BUCKET_NAME} || true