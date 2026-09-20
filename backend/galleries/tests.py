from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from accounts.models import User
from events.models import Event, EventMember
from photos.models import Photo

from .models import Gallery, GalleryPhoto


class GalleryModelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', name='Admin', role=User.Role.ADMIN,
        )
        self.event = Event.objects.create(name='Launch event', created_by=self.admin)
        self.other_event = Event.objects.create(name='Other event', created_by=self.admin)
        self.gallery = Gallery.objects.create(
            event=self.event,
            public_identifier='launch-gallery',
            pin_hash='hashed-pin',
        )
        self.photo = Photo.objects.create(
            event=self.event,
            uploaded_by=self.admin,
            filename='launch.jpg',
            storage_key='events/launch/launch.jpg',
            file_size=1024,
        )

    def test_gallery_photo_relationship_is_available_from_both_sides(self):
        selection = GalleryPhoto.objects.create(gallery=self.gallery, photo=self.photo)

        self.assertEqual(list(self.gallery.gallery_photos.all()), [selection])
        self.assertEqual(list(self.photo.gallery_selections.all()), [selection])

    def test_gallery_rejects_photo_from_another_event(self):
        other_photo = Photo.objects.create(
            event=self.other_event,
            uploaded_by=self.admin,
            filename='other.jpg',
            storage_key='events/other/other.jpg',
            file_size=1024,
        )
        selection = GalleryPhoto(gallery=self.gallery, photo=other_photo)

        with self.assertRaises(ValidationError):
            selection.full_clean()


class GalleryApiPermissionTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='api-gallery-admin@example.com', name='Admin', password='strong-password', role=User.Role.ADMIN)
        self.member = User.objects.create_user(email='api-gallery-member@example.com', name='Member', password='strong-password', role=User.Role.TEAM_MEMBER)
        self.event = Event.objects.create(name='Private event', created_by=self.admin)
        EventMember.objects.create(event=self.event, user=self.member)
        self.photo = Photo.objects.create(event=self.event, uploaded_by=self.member, filename='image.jpg', storage_key='events/private/image.jpg', file_size=1024)

    def test_team_member_cannot_create_or_publish_gallery(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(f'/api/v1/galleries/events/{self.event.id}/', {'pin': '1234'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        gallery = Gallery.objects.create(event=self.event, public_identifier='private-gallery', pin_hash='not-used')
        GalleryPhoto.objects.create(gallery=gallery, photo=self.photo)
        response = self.client.post(f'/api/v1/galleries/{gallery.id}/publish/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_select_photo_from_another_event(self):
        other_event = Event.objects.create(name='Other event', created_by=self.admin)
        other_photo = Photo.objects.create(event=other_event, uploaded_by=self.admin, filename='other.jpg', storage_key='events/other/other.jpg', file_size=1024)
        gallery = Gallery.objects.create(event=self.event, public_identifier='selected-gallery', pin_hash='not-used')
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/api/v1/galleries/{gallery.id}/photos/', {'photo_id': str(other_photo.id)}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_requires_pin_and_only_sees_published_selection(self):
        gallery = Gallery.objects.create(event=self.event, public_identifier='customer-gallery', pin_hash=make_password('1234'))
        GalleryPhoto.objects.create(gallery=gallery, photo=self.photo)
        response = self.client.post('/api/v1/public/galleries/customer-gallery/verify-pin/', {'pin': 'wrong'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.get('/api/v1/public/galleries/customer-gallery/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        gallery.published = True
        gallery.published_at = timezone.now()
        gallery.save(update_fields=['published', 'published_at'])
        response = self.client.post('/api/v1/public/galleries/customer-gallery/verify-pin/', {'pin': 'wrong'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.post('/api/v1/public/galleries/customer-gallery/verify-pin/', {'pin': '1234'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data['data']['gallery_access_token']
        response = self.client.get('/api/v1/public/galleries/customer-gallery/', HTTP_X_GALLERY_TOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['photos']), 1)
        self.assertNotIn('storage_key', response.data['data']['photos'][0])

    def test_member_cannot_access_unrelated_gallery(self):
        other_admin = User.objects.create_user(
            email='other-gallery-admin@example.com', name='Other Admin', password='strong-password', role=User.Role.ADMIN,
        )
        other_event = Event.objects.create(name='Other event', created_by=other_admin)
        other_gallery = Gallery.objects.create(
            event=other_event, public_identifier='unrelated-gallery', pin_hash=make_password('1234'),
        )

        self.client.force_authenticate(self.member)
        response = self.client.get(f'/api/v1/galleries/{other_gallery.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_gallery_access_handles_invalid_unpublished_and_repeated_wrong_pins(self):
        response = self.client.post('/api/v1/public/galleries/missing-gallery/verify-pin/', {'pin': '1234'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        unpublished_gallery = Gallery.objects.create(
            event=self.event,
            public_identifier='draft-gallery',
            pin_hash=make_password('4321'),
        )
        response = self.client.post(f'/api/v1/public/galleries/{unpublished_gallery.public_identifier}/verify-pin/', {'pin': '4321'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        gallery = Gallery.objects.create(
            event=self.event,
            public_identifier='rate-limited-gallery',
            pin_hash=make_password('1234'),
            published=True,
            published_at=timezone.now(),
        )
        for _ in range(4):
            response = self.client.post(f'/api/v1/public/galleries/{gallery.public_identifier}/verify-pin/', {'pin': 'wrong'}, format='json')
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.post(f'/api/v1/public/galleries/{gallery.public_identifier}/verify-pin/', {'pin': 'wrong'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_customer_can_access_published_gallery_with_valid_pin_and_empty_gallery(self):
        gallery = Gallery.objects.create(
            event=self.event,
            public_identifier='public-gallery',
            pin_hash=make_password('1234'),
            published=True,
            published_at=timezone.now(),
        )
        GalleryPhoto.objects.create(gallery=gallery, photo=self.photo)

        response = self.client.post(f'/api/v1/public/galleries/{gallery.public_identifier}/verify-pin/', {'pin': '1234'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data['data']['gallery_access_token']

        response = self.client.get(f'/api/v1/public/galleries/{gallery.public_identifier}/', HTTP_X_GALLERY_TOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']['photos']), 1)

        empty_gallery = Gallery.objects.create(
            event=self.event,
            public_identifier='empty-gallery',
            pin_hash=make_password('5678'),
            published=True,
            published_at=timezone.now(),
        )
        response = self.client.post(f'/api/v1/public/galleries/{empty_gallery.public_identifier}/verify-pin/', {'pin': '5678'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        empty_token = response.data['data']['gallery_access_token']

        response = self.client.get(f'/api/v1/public/galleries/{empty_gallery.public_identifier}/', HTTP_X_GALLERY_TOKEN=empty_token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['photos'], [])

    def test_public_photo_urls_handle_missing_photo_and_s3_failure(self):
        gallery = Gallery.objects.create(
            event=self.event,
            public_identifier='photo-url-gallery',
            pin_hash=make_password('9999'),
            published=True,
            published_at=timezone.now(),
        )
        GalleryPhoto.objects.create(gallery=gallery, photo=self.photo)

        response = self.client.post(f'/api/v1/public/galleries/{gallery.public_identifier}/verify-pin/', {'pin': '9999'}, format='json')
        token = response.data['data']['gallery_access_token']

        self.photo.delete()
        response = self.client.get(f'/api/v1/public/galleries/{gallery.public_identifier}/photos/{self.photo.id}/url/', HTTP_X_GALLERY_TOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        new_photo = Photo.objects.create(
            event=self.event,
            uploaded_by=self.admin,
            filename='another.jpg',
            storage_key='events/private/another.jpg',
            file_size=512,
        )
        GalleryPhoto.objects.create(gallery=gallery, photo=new_photo)

        with patch('galleries.public_views.create_download_url', side_effect=RuntimeError('S3 unavailable')):
            response = self.client.get(f'/api/v1/public/galleries/{gallery.public_identifier}/photos/{new_photo.id}/url/', HTTP_X_GALLERY_TOKEN=token)
            self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)