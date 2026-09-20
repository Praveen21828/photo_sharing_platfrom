from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from photos.models import Photo

from .models import Event, EventMember


class EventModelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', name='Admin', role=User.Role.ADMIN,
        )
        self.member = User.objects.create_user(
            email='member@example.com', name='Member', role=User.Role.TEAM_MEMBER,
        )
        self.event = Event.objects.create(name='Launch event', created_by=self.admin)

    def test_event_member_relationships_are_available_from_both_sides(self):
        membership = EventMember.objects.create(event=self.event, user=self.member)

        self.assertEqual(list(self.event.memberships.all()), [membership])
        self.assertEqual(list(self.member.event_memberships.all()), [membership])

    def test_event_member_assignment_is_unique(self):
        EventMember.objects.create(event=self.event, user=self.member)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventMember.objects.create(event=self.event, user=self.member)

    def test_event_protects_creator_deletion(self):
        with self.assertRaises(ProtectedError):
            self.admin.delete()

    def test_team_member_assignment_rejects_admin(self):
        membership = EventMember(event=self.event, user=self.admin)

        with self.assertRaises(ValidationError):
            membership.full_clean()


class EventApiPermissionTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='api-admin@example.com', name='Admin', password='strong-password', role=User.Role.ADMIN)
        self.member = User.objects.create_user(email='api-member@example.com', name='Member', password='strong-password', role=User.Role.TEAM_MEMBER)
        self.outsider = User.objects.create_user(email='api-outsider@example.com', name='Outsider', password='strong-password', role=User.Role.TEAM_MEMBER)
        self.event = Event.objects.create(name='Private event', created_by=self.admin)
        EventMember.objects.create(event=self.event, user=self.member)
        self.photo = Photo.objects.create(
            event=self.event,
            uploaded_by=self.member,
            filename='event-photo.jpg',
            storage_key='events/private/event-photo.jpg',
            file_size=1024,
        )

    def test_admin_can_create_event(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/v1/events/', {'name': 'New event'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['name'], 'New event')
        self.assertEqual(response.data['data']['created_by']['id'], str(self.admin.id))

    def test_event_name_must_not_be_blank(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/v1/events/', {'name': '   '}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authorized_user_can_view_event_details_and_photos(self):
        self.client.force_authenticate(self.member)
        response = self.client.get(f'/api/v1/events/{self.event.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['id'], str(self.event.id))

        response = self.client.get(f'/api/v1/photos/events/{self.event.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['results'][0]['id'], str(self.photo.id))

    def test_invalid_event_id_is_not_resolved(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/v1/events/not-a-uuid/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_sees_assigned_event_but_outsider_does_not(self):
        self.client.force_authenticate(self.member)
        response = self.client.get('/api/v1/events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)

        self.client.force_authenticate(self.outsider)
        response = self.client.get(f'/api/v1/events/{self.event.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_cannot_create_or_update_events(self):
        self.client.force_authenticate(self.member)
        response = self.client.post('/api/v1/events/', {'name': 'Not allowed'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.patch(f'/api/v1/events/{self.event.id}/', {'name': 'Changed'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_cannot_assign_team_members(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(f'/api/v1/events/{self.event.id}/members/', {'user_id': str(self.outsider.id)}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_assign_team_member_and_duplicate_is_conflict(self):
        new_member = User.objects.create_user(
            email='api-new-member@example.com',
            name='New Member',
            password='strong-password',
            role=User.Role.TEAM_MEMBER,
        )
        self.client.force_authenticate(self.admin)
        payload = {'user_id': str(new_member.id)}

        response = self.client.post(f'/api/v1/events/{self.event.id}/members/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.post(f'/api/v1/events/{self.event.id}/members/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_event_member_list_requires_event_access(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.get(f'/api/v1/events/{self.event.id}/members/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_event_access_is_rejected(self):
        response = self.client.get('/api/v1/events/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)