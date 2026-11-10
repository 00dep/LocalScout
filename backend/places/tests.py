from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Place, Category, Review

class LocalScoutTestSuite(TestCase):
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

    
    def test_signup_page_load(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)

    def test_signup_without_resend_key_uses_development_otp(self):
        with self.settings(DEBUG=True, RESEND_API_KEY=''):
            response = self.client.post(reverse('signup'), {
                'username': 'otpuser',
                'email': 'otpuser@example.com',
                'password': 'testpassword123',
            })

        self.assertRedirects(response, reverse('verify_otp'))
        otp = self.client.session['signup_data']['otp']

        response = self.client.post(reverse('verify_otp'), {'otp': otp})

        self.assertRedirects(response, reverse('home'))
        self.assertTrue(User.objects.filter(username='otpuser').exists())

    def test_expired_otp_shows_clear_error(self):
        with self.settings(DEBUG=True, RESEND_API_KEY=''):
            self.client.post(reverse('signup'), {
                'username': 'expiredotp',
                'email': 'expired@example.com',
                'password': 'testpassword123',
            })

        session = self.client.session
        session['signup_data']['otp_expires_at'] = '2000-01-01T00:00:00+00:00'
        session.save()

        response = self.client.post(reverse('verify_otp'), {'otp': '000000'})

        self.assertContains(response, 'This OTP has expired')

    
    def test_login_and_logout(self):
        login_success = self.client.login(username='testuser', password='testpassword123')
        self.assertTrue(login_success)
        
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)

    
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