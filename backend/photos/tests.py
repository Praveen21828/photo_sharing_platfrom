import uuid
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from PIL import Image

from accounts.models import User
from events.models import Event

from .models import Photo
from .serializers import PhotoUploadSerializer
from .services import build_storage_key, verify_uploaded_object


class PhotoModelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', name='Admin', role=User.Role.ADMIN,
        )
        self.event = Event.objects.create(name='Launch event', created_by=self.admin)

    def test_photo_belongs_to_event_and_uploader(self):
        photo = Photo.objects.create(
            event=self.event,
            uploaded_by=self.admin,
            filename='launch.jpg',
            storage_key='events/launch/launch.jpg',
            file_size=1024,
        )

        self.assertEqual(list(self.event.photos.all()), [photo])
        self.assertEqual(list(self.admin.uploaded_photos.all()), [photo])

    def test_storage_key_is_unique(self):
        photo_data = {
            'event': self.event,
            'uploaded_by': self.admin,
            'filename': 'launch.jpg',
            'storage_key': 'events/launch/launch.jpg',
            'file_size': 1024,
        }
        Photo.objects.create(**photo_data)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Photo.objects.create(**photo_data)

    def test_zero_file_size_is_invalid(self):
        photo = Photo(
            event=self.event,
            uploaded_by=self.admin,
            filename='empty.jpg',
            storage_key='events/launch/empty.jpg',
            file_size=0,
        )

        with self.assertRaises(ValidationError):
            photo.full_clean()

    def test_photo_uploader_must_have_a_platform_role(self):
        user = User.objects.create_user(
            email='unassigned@example.com', name='Unassigned', role='UNKNOWN',
        )
        photo = Photo(
            event=self.event,
            uploaded_by=user,
            filename='invalid.jpg',
            storage_key='events/launch/invalid.jpg',
            file_size=1024,
        )

        with self.assertRaises(ValidationError):
            photo.full_clean()


class PhotoAuthorizationApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='photo-admin@example.com', name='Admin', password='strong-password', role=User.Role.ADMIN)
        self.member = User.objects.create_user(email='photo-member@example.com', name='Member', password='strong-password', role=User.Role.TEAM_MEMBER)
        self.other_member = User.objects.create_user(email='photo-other@example.com', name='Other', password='strong-password', role=User.Role.TEAM_MEMBER)
        self.event = Event.objects.create(name='Assigned event', created_by=self.admin)
        from events.models import EventMember
        EventMember.objects.create(event=self.event, user=self.member)
        self.photo = Photo.objects.create(event=self.event, uploaded_by=self.other_member, filename='other.jpg', storage_key='events/assigned/other.jpg', file_size=1024)

    def test_team_member_cannot_view_another_users_photo(self):
        self.client.force_authenticate(self.member)
        response = self.client.get(f'/api/v1/photos/{self.photo.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PhotoUploadSecurityTests(TestCase):
    @patch('photos.services._get_s3_client')
    def test_uploaded_object_must_be_a_valid_declared_image(self, mock_get_client):
        image_data = BytesIO()
        Image.new('RGB', (1, 1), color='white').save(image_data, format='JPEG')
        payload = image_data.getvalue()
        mock_client = mock_get_client.return_value
        mock_client.head_object.return_value = {'ContentLength': len(payload), 'ContentType': 'image/jpeg'}
        mock_client.get_object.return_value = {'Body': BytesIO(payload)}

        with self.settings(AWS_STORAGE_BUCKET_NAME='demo-bucket', AWS_REGION='eu-north-1'):
            verify_uploaded_object('events/test/photo.jpg', len(payload), 'image/jpeg')

        mock_client.get_object.return_value = {'Body': BytesIO(b'not an image')}
        mock_client.head_object.return_value = {'ContentLength': 12, 'ContentType': 'image/jpeg'}
        with self.settings(AWS_STORAGE_BUCKET_NAME='demo-bucket', AWS_REGION='eu-north-1'):
            with self.assertRaises(ValueError):
                verify_uploaded_object('events/test/photo.jpg', 12, 'image/jpeg')

    def test_photo_serializer_does_not_expose_storage_key(self):
        admin = User.objects.create_user(email='serializer-admin@example.com', name='Admin')
        event = Event.objects.create(name='Serializer event', created_by=admin)
        photo = Photo.objects.create(
            event=event,
            uploaded_by=admin,
            filename='safe.jpg',
            storage_key='events/private/safe.jpg',
            file_size=1024,
        )

        from .serializers import PhotoSerializer
        representation = PhotoSerializer(photo).data

        self.assertNotIn('storage_key', representation)

    def test_upload_serializer_rejects_unsupported_image_type(self):
        serializer = PhotoUploadSerializer(data={
            'filename': 'danger.php',
            'file_size': 2048,
            'content_type': 'application/x-php',
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('content_type', serializer.errors)

    def test_upload_serializer_rejects_oversized_photo(self):
        serializer = PhotoUploadSerializer(data={
            'filename': 'large.jpg',
            'file_size': 11 * 1024 * 1024,
            'content_type': 'image/jpeg',
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('file_size', serializer.errors)

    def test_storage_key_is_sanitized_and_unique(self):
        event_id = uuid.uuid4()
        key1 = build_storage_key(event_id, '../../weird/../evil.php')
        key2 = build_storage_key(event_id, 'photo.jpg')

        self.assertTrue(key1.startswith(f'events/{event_id}/photos/'))
        self.assertNotIn('..', key1)
        self.assertNotEqual(key1, key2)

    @patch('photos.services.boto3.client')
    def test_create_upload_url_uses_content_type_and_env_settings(self, mock_client):
        mock_client.return_value.generate_presigned_url.return_value = 'https://example.com/upload'

        with self.settings(AWS_STORAGE_BUCKET_NAME='demo-bucket', AWS_REGION='eu-north-1', AWS_ACCESS_KEY_ID='abc', AWS_SECRET_ACCESS_KEY='def'):
            from photos.services import create_upload_url
            url = create_upload_url('events/test/photos/upload.jpg', 2048, 'image/jpeg')

        self.assertEqual(url, 'https://example.com/upload')
        mock_client.assert_called_once()
        kwargs = mock_client.call_args.kwargs
        self.assertEqual(kwargs['region_name'], 'eu-north-1')
