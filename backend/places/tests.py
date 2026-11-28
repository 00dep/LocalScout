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
from .constants import NADIA_LOCATION_FILTERS
from .forms import UserRegistrationForm
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
                'accept_terms': 'on',
            })
    
    def test_signup_page_load(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('privacy'))
        self.assertContains(response, reverse('terms'))

    def test_privacy_terms_and_support_pages_are_available(self):
        for route_name in ('privacy', 'terms', 'support_requests'):
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)

        self.assertContains(
            self.client.get(reverse('support_requests')),
            'deeproy.space@yahoo.com',
        )

    def test_registration_rejects_password_that_fails_configured_validators(self):
        form = UserRegistrationForm(data={
            'username': 'weakpassworduser',
            'email': 'weak@example.com',
            'password': '123456',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_registration_accepts_password_that_passes_configured_validators(self):
        form = UserRegistrationForm(data={
            'username': 'securepassworduser',
            'email': 'secure@example.com',
            'password': 'UniqueStrongPass!82',
            'accept_terms': 'on',
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_registration_requires_terms_acceptance(self):
        form = UserRegistrationForm(data={
            'username': 'termsuser',
            'email': 'terms@example.com',
            'password': 'UniqueStrongPass!82',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('accept_terms', form.errors)

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
        self.client.force_login(self.user)
        
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

    def test_home_and_places_list_paginate_filtered_results(self):
        for index in range(12):
            Place.objects.create(
                name=f'Extra Place {index}',
                address='Ranaghat',
                location='Ranaghat',
                category=self.category,
                owner=self.user,
                is_approved=True,
            )

        for url in (reverse('home'), reverse('place_list')):
            first_page = self.client.get(url, {'location': 'Ranaghat'})
            second_page = self.client.get(url, {'location': 'Ranaghat', 'page': '2'})

            self.assertEqual(len(first_page.context['places']), 12)
            self.assertEqual(first_page.context['places'].paginator.count, 13)
            self.assertEqual(len(second_page.context['places']), 1)
            self.assertEqual(second_page.context['pagination_query'], 'location=Ranaghat')

    def test_home_location_filter_lists_selected_nadia_areas_and_matches_exactly(self):
        station_place = Place.objects.create(
            name='Badkulla Cafe',
            address='Badkulla',
            location='Badkulla',
            category=self.category,
            owner=self.user,
            is_approved=True,
        )

        response = self.client.get(reverse('home'), {'location': 'Badkulla'})

        self.assertEqual(len(NADIA_LOCATION_FILTERS), 7)
        self.assertEqual(response.context['stations'], NADIA_LOCATION_FILTERS)
        self.assertEqual(list(response.context['places'].object_list), [station_place])
        self.assertContains(response, '<option value="Badkulla" selected>')
        self.assertContains(response, 'All Locations')


    def test_toggle_save_place(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('toggle_save', kwargs={'pk': self.place.pk}))
        self.assertRedirects(
            response,
            reverse('place_detail', kwargs={'pk': self.place.pk}),
        )
        self.assertTrue(self.place.saved_by.filter(id=self.user.id).exists())

    def test_place_detail_shows_saved_state_and_rating_near_name(self):
        Review.objects.create(place=self.place, user=self.user, rating=4)
        self.place.rating = '4.0'
        self.place.save(update_fields=['rating'])
        self.place.saved_by.add(self.user)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('place_detail', kwargs={'pk': self.place.pk})
        )

        self.assertContains(response, 'aria-label="Place rating"')
        self.assertContains(response, '4.0')
        self.assertContains(response, '(1 rating)')
        self.assertContains(response, 'Remove from Wishlist')

    def test_place_detail_shows_empty_rating_state(self):
        response = self.client.get(
            reverse('place_detail', kwargs={'pk': self.place.pk})
        )

        self.assertContains(response, 'No ratings yet')

    def test_home_shows_rating_and_wishlist_option(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, 'No ratings yet')
        self.assertContains(response, 'Log in to save Test Cafe to your wishlist')

    def test_footer_shows_contact_links(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, 'WhatsApp: 9083835446')
        self.assertContains(response, 'https://wa.me/919083835446')
        self.assertContains(response, 'mailto:deeproy.space@yahoo.com')

    def test_home_shows_rating_score_and_saved_wishlist_state(self):
        Review.objects.create(place=self.place, user=self.user, rating=4)
        self.place.rating = '4.0'
        self.place.save(update_fields=['rating'])
        self.place.is_featured = True
        self.place.save(update_fields=['is_featured'])
        self.place.saved_by.add(self.user)
        self.client.force_login(self.user)

        response = self.client.get(reverse('home'))

        self.assertContains(response, '4.0 · 1')
        self.assertContains(response, 'Remove Test Cafe from wishlist')

    def test_home_wishlist_button_toggles_and_returns_home(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('toggle_save', kwargs={'pk': self.place.pk}),
            {'next': reverse('home')},
        )

        self.assertRedirects(response, reverse('home'))
        self.assertTrue(self.place.saved_by.filter(pk=self.user.pk).exists())

    def test_remove_from_wishlist_returns_to_wishlist(self):
        self.client.force_login(self.user)
        self.place.saved_by.add(self.user)

        response = self.client.post(
            reverse('toggle_save', kwargs={'pk': self.place.pk}),
            {'next': reverse('wishlist')},
        )

        self.assertRedirects(response, reverse('wishlist'))
        self.assertFalse(self.place.saved_by.filter(pk=self.user.pk).exists())
        self.assertNotContains(self.client.get(reverse('wishlist')), self.place.name)

    def test_toggle_save_ignores_external_redirect_url(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('toggle_save', kwargs={'pk': self.place.pk}),
            {'next': 'https://example.com'},
        )

        self.assertRedirects(
            response,
            reverse('place_detail', kwargs={'pk': self.place.pk}),
        )
        self.assertTrue(self.place.saved_by.filter(pk=self.user.pk).exists())

    def test_cannot_add_unapproved_place_to_wishlist(self):
        pending_place = Place.objects.create(
            name='Pending Cafe',
            address='Ranaghat',
            location='Ranaghat',
            owner=self.user,
            is_approved=False,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('toggle_save', kwargs={'pk': pending_place.pk})
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(pending_place.saved_by.filter(pk=self.user.pk).exists())

    def test_rating_submission_updates_average_and_saves_comment(self):
        other_user = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='reviewerpassword123',
        )
        Review.objects.create(place=self.place, user=other_user, rating=2)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('add_review', kwargs={'pk': self.place.pk}),
            {'rating': '4', 'comment': 'A lovely place'},
        )

        self.assertRedirects(
            response,
            reverse('place_detail', kwargs={'pk': self.place.pk}),
        )
        self.place.refresh_from_db()
        review = Review.objects.get(place=self.place, user=self.user)
        self.assertEqual(str(self.place.rating), '3.0')
        self.assertEqual(review.comment, 'A lovely place')

 
    def test_unauthorized_add_place_redirects(self):
     
        response = self.client.get(reverse('add_place'))
        self.assertEqual(response.status_code, 302)

    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
    })
    def test_add_place_saves_gallery_images(self):
        self.client.force_login(self.user)
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
        self.client.force_login(self.user)
        url = reverse('delete_place', kwargs={'pk': self.place.pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(url)
        self.assertRedirects(response, reverse('place_list'))
        self.assertFalse(Place.objects.filter(pk=self.place.pk).exists())

    def test_other_user_cannot_delete_menu_item_or_gallery_image(self):
        menu_item = MenuItem.objects.create(
            place=self.place,
            name='Owner Item',
            price='50.00',
        )
        gallery_image = PlaceImage.objects.create(
            place=self.place,
            image='places/gallery/owner-image.jpg',
        )
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpassword123',
        )
        self.client.force_login(other_user)

        menu_response = self.client.post(
            reverse('delete_menu_item', kwargs={'item_id': menu_item.pk})
        )
        gallery_response = self.client.post(
            reverse('delete_gallery_image', kwargs={'image_id': gallery_image.pk})
        )

        self.assertEqual(menu_response.status_code, 404)
        self.assertEqual(gallery_response.status_code, 404)
        self.assertTrue(MenuItem.objects.filter(pk=menu_item.pk).exists())
        self.assertTrue(PlaceImage.objects.filter(pk=gallery_image.pk).exists())

    def test_owner_can_delete_menu_item_and_gallery_image(self):
        menu_item = MenuItem.objects.create(
            place=self.place,
            name='Owner Item',
            price='50.00',
        )
        gallery_image = PlaceImage.objects.create(
            place=self.place,
            image='places/gallery/owner-image.jpg',
        )
        self.client.force_login(self.user)

        menu_response = self.client.post(
            reverse('delete_menu_item', kwargs={'item_id': menu_item.pk})
        )
        gallery_response = self.client.post(
            reverse('delete_gallery_image', kwargs={'image_id': gallery_image.pk})
        )

        self.assertRedirects(menu_response, reverse('edit_place', kwargs={'pk': self.place.pk}))
        self.assertRedirects(gallery_response, reverse('edit_place', kwargs={'pk': self.place.pk}))
        self.assertFalse(MenuItem.objects.filter(pk=menu_item.pk).exists())
        self.assertFalse(PlaceImage.objects.filter(pk=gallery_image.pk).exists())

    def test_login_is_locked_after_repeated_invalid_passwords(self):
        login_url = reverse('login')
        for _ in range(6):
            response = self.client.post(
                login_url,
                {'username': 'testuser', 'password': 'incorrect-password'},
            )

        self.assertEqual(response.status_code, 429)
        locked_response = self.client.post(
            login_url,
            {'username': 'testuser', 'password': 'testpassword123'},
        )
        self.assertEqual(locked_response.status_code, 429)

    def test_owner_can_edit_menu_item_from_place_management_page(self):
        menu_item = MenuItem.objects.create(
            place=self.place,
            name='Old Item',
            description='Old description',
            price='50.00',
            is_available=True,
        )
        self.client.force_login(self.user)

        edit_page = self.client.get(reverse('edit_place', kwargs={'pk': self.place.pk}))
        self.assertContains(edit_page, 'Manage Menu Items')
        self.assertContains(edit_page, 'Old Item')

        response = self.client.post(
            reverse('edit_menu_item', kwargs={'item_id': menu_item.pk}),
            {
                'name': 'Updated Item',
                'description': 'Updated description',
                'price': '75.50',
                'is_available': 'on',
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('edit_place', kwargs={'pk': self.place.pk})}#menu-management",
        )
        menu_item.refresh_from_db()
        self.assertEqual(menu_item.name, 'Updated Item')
        self.assertEqual(menu_item.description, 'Updated description')
        self.assertEqual(str(menu_item.price), '75.50')
        self.assertTrue(menu_item.is_available)

    def test_other_user_cannot_edit_menu_item(self):
        menu_item = MenuItem.objects.create(
            place=self.place,
            name='Owner Item',
            price='50.00',
        )
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpassword123',
        )
        self.client.force_login(other_user)

        response = self.client.post(
            reverse('edit_menu_item', kwargs={'item_id': menu_item.pk}),
            {
                'name': 'Changed by other user',
                'description': '',
                'price': '1.00',
            },
        )

        self.assertEqual(response.status_code, 404)
        menu_item.refresh_from_db()
        self.assertEqual(menu_item.name, 'Owner Item')

    def test_place_detail_shows_coordinate_map_and_directions(self):
        self.place.latitude = 23.2081
        self.place.longitude = 88.5732
        self.place.save(update_fields=['latitude', 'longitude'])

        response = self.client.get(
            reverse('place_detail', kwargs={'pk': self.place.pk})
        )

        self.assertContains(response, 'https://maps.google.com/maps?q=23.2081,88.5732')
        self.assertContains(response, 'Get Directions')
        self.assertContains(response, 'destination=23.2081,88.5732')

    def test_place_without_coordinates_links_to_address_search(self):
        response = self.client.get(
            reverse('place_detail', kwargs={'pk': self.place.pk})
        )

        self.assertContains(response, 'Search address on Google Maps')

    def test_profile_includes_user_role(self):
        profile = UserProfile.objects.create(user=self.user, role='owner')
        self.client.force_login(self.user)

        response = self.client.get(reverse('profile'))

        self.assertContains(response, profile.role)

    def test_google_login_fails_gracefully_when_not_configured(self):
        with self.settings(GOOGLE_CLIENT_ID=''):
            response = self.client.post(
                reverse('google_login_callback'),
                {'credential': 'token'},
            )

        self.assertRedirects(response, reverse('login'))

    @patch('places.views_legacy.id_token.verify_oauth2_token')
    def test_google_login_works_with_multiple_authentication_backends(self, verify_token):
        verify_token.return_value = {
            'email': 'googleuser@example.com',
            'given_name': 'Google',
            'family_name': 'User',
        }

        with self.settings(GOOGLE_CLIENT_ID='test-client-id'):
            response = self.client.post(
                reverse('google_login_callback'),
                {'credential': 'valid-token'},
            )

        self.assertRedirects(response, reverse('home'))
        self.assertEqual(
            int(self.client.session['_auth_user_id']),
            User.objects.get(email='googleuser@example.com').pk,
        )

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
        self.client.force_login(self.user)

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

    def test_place_detail_only_shows_menu_for_restaurant_or_cafe(self):
        self.assertContains(
            self.client.get(reverse('place_detail', kwargs={'pk': self.place.pk})),
            'Menu & Special Items',
        )

        park = Category.objects.create(name='Park')
        self.place.category = park
        self.place.save(update_fields=['category'])
        park_response = self.client.get(
            reverse('place_detail', kwargs={'pk': self.place.pk})
        )
        self.assertNotContains(park_response, 'Menu & Special Items')

        cafe = Category.objects.create(name='Cafe')
        self.place.category = cafe
        self.place.save(update_fields=['category'])
        cafe_response = self.client.get(
            reverse('place_detail', kwargs={'pk': self.place.pk})
        )
        self.assertContains(cafe_response, 'Menu & Special Items')

    def test_edit_page_menu_options_follow_selected_category(self):
        self.client.force_login(self.user)
        edit_url = reverse('edit_place', kwargs={'pk': self.place.pk})
        response = self.client.get(edit_url)
        self.assertContains(response, 'data-menu-management')
        self.assertNotContains(response, 'data-menu-management hidden')

        self.assertContains(response, 'Cafe')
        self.assertContains(response, 'Other')

        park = Category.objects.create(name='Park')
        self.place.category = park
        self.place.save(update_fields=['category'])
        response = self.client.get(edit_url)
        self.assertContains(response, 'data-menu-management hidden')
        self.assertContains(response, 'id="id_category"')

    def test_add_place_category_options_include_cafe_park_and_other(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('add_place'))

        self.assertContains(response, 'Restaurant')
        self.assertContains(response, 'Cafe')
        self.assertContains(response, 'Park')
        self.assertContains(response, 'Other')

    def test_owner_profile_has_share_link_for_approved_place(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('profile'))

        self.assertContains(response, 'Share Store Link')
        self.assertContains(
            response,
            reverse('place_detail', kwargs={'pk': self.place.pk}),
        )

    def test_owner_profile_explains_pending_place_share_restriction(self):
        self.place.is_approved = False
        self.place.save(update_fields=['is_approved'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('profile'))

        self.assertContains(response, 'Share link will work for others after admin approval.')
        self.assertNotContains(response, 'Share Store Link')

    def test_menu_item_cannot_be_deleted_with_get(self):
        item = MenuItem.objects.create(
            place=self.place,
            name='Tea',
            price='10.00',
        )
        self.client.force_login(self.user)

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
        self.client.force_login(self.user)

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