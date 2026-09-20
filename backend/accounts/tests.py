from django.db import IntegrityError, transaction
from django.test import override_settings
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class UserModelTests(TestCase):
    def test_user_manager_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user(
            email='LEAD@EXAMPLE.COM',
            name='Lead User',
            password='strong-password',
            role=User.Role.ADMIN,
        )

        self.assertEqual(user.email, 'LEAD@example.com')
        self.assertTrue(user.check_password('strong-password'))
        self.assertNotEqual(user.password, 'strong-password')

    def test_email_is_unique_case_insensitively(self):
        User.objects.create_user(email='user@example.com', name='First')

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(email='USER@example.com', name='Second')


class AuthenticationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='auth@example.com', name='Auth User', password='strong-password', role=User.Role.ADMIN,
        )

    def test_login_returns_tokens_and_profile(self):
        response = self.client.post('/api/v1/auth/login/', {'email': 'auth@example.com', 'password': 'strong-password'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['data'])
        self.assertEqual(response.data['data']['user']['email'], self.user.email)

    def test_invalid_login_is_unauthorized(self):
        response = self.client.post('/api/v1/auth/login/', {'email': 'auth@example.com', 'password': 'wrong-password'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_registration_assigns_admin_role_without_accepting_role_input(self):
        response = self.client.post(
            '/api/v1/auth/register/',
            {'name': 'New Admin', 'email': 'new@example.com', 'password': 'strong-password', 'role': User.Role.TEAM_MEMBER},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['role'], User.Role.ADMIN)

    def test_duplicate_registration_returns_conflict(self):
        response = self.client.post(
            '/api/v1/auth/register/',
            {'name': 'Duplicate', 'email': self.user.email.upper(), 'password': 'strong-password'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    @override_settings(ALLOW_PUBLIC_ADMIN_REGISTRATION=False)
    def test_public_admin_registration_is_disabled_when_not_explicitly_enabled(self):
        response = self.client.post(
            '/api/v1/auth/register/',
            {'name': 'Blocked Admin', 'email': 'blocked@example.com', 'password': 'strong-password'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_logout_blacklists_refresh_token(self):
        login = self.client.post(
            '/api/v1/auth/login/',
            {'email': self.user.email, 'password': 'strong-password'},
            format='json',
        )
        refresh = login.data['data']['refresh']
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['data']['access']}")
        response = self.client.post('/api/v1/auth/logout/', {'refresh': refresh}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post('/api/v1/auth/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)