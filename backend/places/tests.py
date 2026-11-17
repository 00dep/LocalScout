import os
from io import BytesIO
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from PIL import Image
from .models import Place, Category, MenuItem, PlaceImage, Review, UserProfile

class LocalScoutTestSuite(TestCase):
    TEST_OTP = '123456'

    def setUp(self):
        self.client = Client()
        
        self.user = User.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='testpassword123'
        )
        
        self.category = Category.objects.create(name='Restaurant')
        self.place = Place.objects.create(
            name='Test Cafe',
            address='Ranaghat',
            location='Ranaghat',
            category=self.category,
            owner=self.user,
            is_approved=True
        )

    def signup_with_test_otp(self, username, email):
        with patch('places.views_legacy.generate_otp', return_value=self.TEST_OTP):
            return self.client.post(reverse('signup'), {
                'username': username,
                'email': email,
                'password': 'testpassword123',
            })
    
    def test_signup_page_load(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)

    def test_signup_without_resend_key_uses_development_otp(self):
        with self.settings(DEBUG=True, RESEND_API_KEY=''):
            response = self.signup_with_test_otp('otpuser', 'otpuser@example.com')

        self.assertRedirects(response, reverse('verify_otp'))
        signup_data = self.client.session['signup_data']
        self.assertNotIn('password', signup_data)
        self.assertNotIn('otp', signup_data)
        self.assertNotEqual(signup_data['password_hash'], 'testpassword123')

        response = self.client.post(
            reverse('verify_otp'),
            {'otp': self.TEST_OTP},
        )

        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(username='otpuser')
        self.assertTrue(user.check_password('testpassword123'))

    def test_otp_is_invalidated_after_five_incorrect_attempts(self):
        with self.settings(DEBUG=True, RESEND_API_KEY=''):
            self.signup_with_test_otp('limitedotp', 'limited@example.com')

        for _ in range(5):
            response = self.client.post(reverse('verify_otp'), {'otp': '000000'})

        self.assertRedirects(response, reverse('signup'))
        self.assertNotIn('signup_data', self.client.session)
        self.assertFalse(User.objects.filter(username='limitedotp').exists())

    def test_expired_otp_shows_clear_error(self):
        with self.settings(DEBUG=True, RESEND_API_KEY=''):
            self.signup_with_test_otp('expiredotp', 'expired@example.com')

        session = self.client.session
        session['signup_data']['otp_expires_at'] = '2000-01-01T00:00:00+00:00'
        session.save()

        response = self.client.post(reverse('verify_otp'), {'otp': '000000'})

        self.assertContains(response, 'This OTP has expired')
        self.assertNotIn('signup_data', self.client.session)

    def test_malformed_otp_expiry_fails_closed(self):
        with self.settings(DEBUG=True, RESEND_API_KEY=''):
            self.signup_with_test_otp('malformedotp', 'malformed@example.com')

        session = self.client.session
        session['signup_data']['otp_expires_at'] = 'not-a-date'
        session.save()

        response = self.client.post(
            reverse('verify_otp'),
            {'otp': self.TEST_OTP},
        )

        self.assertContains(response, 'This OTP has expired')
        self.assertFalse(User.objects.filter(username='malformedotp').exists())

    
    def test_login_and_logout(self):
        login_success = self.client.login(username='testuser', password='testpassword123')
        self.assertTrue(login_success)
        
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    
    def test_places_search(self):
        response = self.client.get(reverse('place_list'), {'q': 'Test Cafe'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Cafe')


    def test_toggle_save_place(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.post(reverse('toggle_save', kwargs={'pk': self.place.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.place.saved_by.filter(id=self.user.id).exists())

 
    def test_unauthorized_add_place_redirects(self):
     
        response = self.client.get(reverse('add_place'))
        self.assertEqual(response.status_code, 302)

    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
    })
    def test_add_place_saves_gallery_images(self):
        self.client.login(username='testuser', password='testpassword123')
        image_buffer = BytesIO()
        Image.new('RGB', (1, 1)).save(image_buffer, format='PNG')
        image_buffer.seek(0)
        gallery_image = SimpleUploadedFile(
            'gallery.png',
            image_buffer.read(),
            content_type='image/png',
        )

        response = self.client.post(reverse('add_place'), {
            'name': 'Gallery Cafe',
            'category': self.category.pk,
            'description': 'A small cafe',
            'address': 'Ranaghat',
            'location': 'Ranaghat',
            'opening_hours': '10 AM - 10 PM',
            'phone': '',
            'website': '',
            'price_range': '$$',
            'latitude': '',
            'longitude': '',
            'gallery_images': [gallery_image],
        })

        self.assertRedirects(response, reverse('store_pending'))
        place = Place.objects.get(name='Gallery Cafe')
        self.assertEqual(place.gallery_images.count(), 1)

    def test_delete_place_confirmation_page_loads_and_post_deletes(self):
        self.client.login(username='testuser', password='testpassword123')
        url = reverse('delete_place', kwargs={'pk': self.place.pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(url)
        self.assertRedirects(response, reverse('place_list'))
        self.assertFalse(Place.objects.filter(pk=self.place.pk).exists())

    def test_profile_includes_user_role(self):
        profile = UserProfile.objects.create(user=self.user, role='owner')
        self.client.login(username='testuser', password='testpassword123')

        response = self.client.get(reverse('profile'))

        self.assertContains(response, profile.role)

    def test_google_login_fails_gracefully_when_not_configured(self):
        with self.settings(GOOGLE_CLIENT_ID=''):
            response = self.client.post(
                reverse('google_login_callback'),
                {'credential': 'token'},
            )

        self.assertRedirects(response, reverse('login'))

    def test_user_cannot_create_duplicate_review_for_same_place(self):
        Review.objects.create(place=self.place, user=self.user, rating=4)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(place=self.place, user=self.user, rating=5)

    def test_unapproved_place_detail_is_hidden_from_public(self):
        pending_place = Place.objects.create(
            name='Pending Cafe',
            address='Ranaghat',
            location='Ranaghat',
            owner=self.user,
            is_approved=False,
        )

        response = self.client.get(
            reverse('place_detail', kwargs={'pk': pending_place.pk})
        )

        self.assertEqual(response.status_code, 404)

    def test_owner_can_view_unapproved_place_detail(self):
        pending_place = Place.objects.create(
            name='Pending Cafe',
            address='Ranaghat',
            location='Ranaghat',
            owner=self.user,
            is_approved=False,
        )
        self.client.login(username='testuser', password='testpassword123')

        response = self.client.get(
            reverse('place_detail', kwargs={'pk': pending_place.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Share link will work for others after admin approval.')
        self.assertNotContains(response, 'Share Store Link')

    def test_anonymous_visitor_can_open_approved_place_link(self):
        response = self.client.get(
            reverse('place_detail', kwargs={'pk': self.place.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Share Store Link')

    def test_owner_profile_has_share_link_for_approved_place(self):
        self.client.login(username='testuser', password='testpassword123')

        response = self.client.get(reverse('profile'))

        self.assertContains(response, 'Share Store Link')
        self.assertContains(
            response,
            reverse('place_detail', kwargs={'pk': self.place.pk}),
        )

    def test_owner_profile_explains_pending_place_share_restriction(self):
        self.place.is_approved = False
        self.place.save(update_fields=['is_approved'])
        self.client.login(username='testuser', password='testpassword123')

        response = self.client.get(reverse('profile'))

        self.assertContains(response, 'Share link will work for others after admin approval.')
        self.assertNotContains(response, 'Share Store Link')

    def test_menu_item_cannot_be_deleted_with_get(self):
        item = MenuItem.objects.create(
            place=self.place,
            name='Tea',
            price='10.00',
        )
        self.client.login(username='testuser', password='testpassword123')

        response = self.client.get(
            reverse('delete_menu_item', kwargs={'item_id': item.pk})
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(MenuItem.objects.filter(pk=item.pk).exists())

    def test_gallery_image_cannot_be_deleted_with_get(self):
        image = PlaceImage.objects.create(
            place=self.place,
            image='places/gallery/test.jpg',
        )
        self.client.login(username='testuser', password='testpassword123')

        response = self.client.get(
            reverse('delete_gallery_image', kwargs={'image_id': image.pk})
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(PlaceImage.objects.filter(pk=image.pk).exists())

    def test_bootstrap_admin_creates_superuser_from_environment(self):
        env = {
            'DJANGO_BOOTSTRAP_ADMIN_USERNAME': 'localscout-admin',
            'DJANGO_BOOTSTRAP_ADMIN_EMAIL': 'admin@example.com',
            'DJANGO_BOOTSTRAP_ADMIN_PASSWORD': 'StrongUniquePassword!47',
        }

        with patch.dict(os.environ, env):
            call_command('bootstrap_admin')

        admin_user = User.objects.get(username='localscout-admin')
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.check_password(env['DJANGO_BOOTSTRAP_ADMIN_PASSWORD']))

    def test_bootstrap_admin_is_idempotent(self):
        admin_user = User.objects.create_superuser(
            username='localscout-admin',
            email='admin@example.com',
            password='OriginalPassword!47',
        )
        env = {
            'DJANGO_BOOTSTRAP_ADMIN_USERNAME': 'localscout-admin',
            'DJANGO_BOOTSTRAP_ADMIN_EMAIL': 'admin@example.com',
            'DJANGO_BOOTSTRAP_ADMIN_PASSWORD': 'DifferentPassword!47',
        }

        with patch.dict(os.environ, env):
            call_command('bootstrap_admin')

        admin_user.refresh_from_db()
        self.assertTrue(admin_user.check_password('OriginalPassword!47'))
        self.assertFalse(admin_user.check_password(env['DJANGO_BOOTSTRAP_ADMIN_PASSWORD']))

    def test_bootstrap_admin_rejects_partial_environment(self):
        env = {'DJANGO_BOOTSTRAP_ADMIN_USERNAME': 'localscout-admin'}
        variable_names = (
            'DJANGO_BOOTSTRAP_ADMIN_USERNAME',
            'DJANGO_BOOTSTRAP_ADMIN_EMAIL',
            'DJANGO_BOOTSTRAP_ADMIN_PASSWORD',
        )

        with patch.dict(os.environ, {}, clear=False):
            for name in variable_names:
                os.environ.pop(name, None)
            os.environ.update(env)

            with self.assertRaisesMessage(CommandError, 'must all be set together'):
                call_command('bootstrap_admin')

    def test_bootstrap_admin_does_not_promote_existing_regular_user(self):
        User.objects.create_user(
            username='localscout-admin',
            email='user@example.com',
            password='RegularPassword!47',
        )
        env = {
            'DJANGO_BOOTSTRAP_ADMIN_USERNAME': 'localscout-admin',
            'DJANGO_BOOTSTRAP_ADMIN_EMAIL': 'admin@example.com',
            'DJANGO_BOOTSTRAP_ADMIN_PASSWORD': 'StrongUniquePassword!47',
        }

        with patch.dict(os.environ, env):
            with self.assertRaisesMessage(CommandError, 'already exists'):
                call_command('bootstrap_admin')

        regular_user = User.objects.get(username='localscout-admin')
        self.assertFalse(regular_user.is_staff)
        self.assertFalse(regular_user.is_superuser)