import os
import re
import uuid

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from PIL import Image, UnidentifiedImageError
from io import BytesIO

ALLOWED_IMAGE_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
}


def _get_s3_client():
    if not settings.AWS_STORAGE_BUCKET_NAME or not settings.AWS_REGION:
        raise ImproperlyConfigured('AWS_STORAGE_BUCKET_NAME and AWS_REGION must be configured for photo uploads.')

    client_kwargs = {
        'region_name': settings.AWS_REGION,
        'config': Config(signature_version='s3v4'),
    }
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
        client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY

    return boto3.client('s3', **client_kwargs)


def build_storage_key(event_id, filename):
    safe_name = filename.replace('\\', '/').split('/')[-1].strip()
    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '-', safe_name).strip('._-') or 'photo'
    if not os.path.splitext(safe_name)[1]:
        safe_name = f'{safe_name}-{uuid.uuid4().hex}'
    return f'events/{event_id}/photos/{uuid.uuid4().hex}/{safe_name}'


def delete_uploaded_object(storage_key):
    client = _get_s3_client()
    client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=storage_key)
    return True


def create_upload_url(storage_key, file_size, content_type=None):
    if not settings.AWS_STORAGE_BUCKET_NAME:
        raise ImproperlyConfigured('AWS_STORAGE_BUCKET_NAME must be configured for photo uploads.')

    normalized_type = (content_type or '').strip().lower()
    if normalized_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValueError('Unsupported image content type for upload.')

    client = _get_s3_client()
    params = {
        'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
        'Key': storage_key,
        'ContentLength': file_size,
        'ContentType': normalized_type,
    }
    return client.generate_presigned_url(
        'put_object',
        Params=params,
        ExpiresIn=600,
        HttpMethod='PUT',
    )


def create_download_url(storage_key):
    if not settings.AWS_STORAGE_BUCKET_NAME:
        raise ImproperlyConfigured('AWS_STORAGE_BUCKET_NAME must be configured for photo downloads.')
    client = _get_s3_client()
    return client.generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': storage_key},
        ExpiresIn=300,
        HttpMethod='GET',
    )


def verify_uploaded_object(storage_key, expected_size, expected_content_type=None):
    if not settings.AWS_STORAGE_BUCKET_NAME:
        raise ImproperlyConfigured('AWS_STORAGE_BUCKET_NAME must be configured for photo uploads.')
    client = _get_s3_client()
    metadata = client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=storage_key)
    if metadata.get('ContentLength') != expected_size:
        raise ValueError('Uploaded object size does not match the declared file size.')
    actual = (metadata.get('ContentType') or '').lower()
    if expected_content_type:
        if actual not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValueError('Uploaded object content type is not a supported image type.')
        if actual != expected_content_type.lower():
            raise ValueError('Uploaded object content type does not match the validated upload declaration.')

    client = _get_s3_client()
    body = client.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=storage_key)['Body'].read()
    try:
        with Image.open(BytesIO(body)) as image:
            image.verify()
            detected_type = {
                'JPEG': 'image/jpeg',
                'PNG': 'image/png',
                'WEBP': 'image/webp',
            }.get(image.format)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('Uploaded object is not a valid supported image.') from exc

    if detected_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValueError('Uploaded object is not a valid supported image.')
    if expected_content_type and detected_type != expected_content_type.lower():
        raise ValueError('Uploaded object content does not match the validated upload declaration.')
    return metadata