from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='category_images/', blank=True, null=True)

    def __str__(self):
        return self.name


class Place(models.Model):
    PRICE_CHOICES = [
        ('$', 'Budget ($)'),
        ('$$', 'Moderate ($$)'),
        ('$$$', 'Expensive ($$$)'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='places')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    address = models.CharField(max_length=300)
    location = models.CharField(max_length=100, help_text="e.g. Ranaghat, Krishnanagar, Kalyani")
    opening_hours = models.CharField(max_length=100, default="10:00 AM - 10:00 PM")
    phone = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    price_range = models.CharField(max_length=5, choices=PRICE_CHOICES, default='$$')
    
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    map_embed_url = models.TextField(blank=True, null=True)
    
    image = models.ImageField(upload_to='places/', blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('0.0'))
    
    is_approved = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    saved_by = models.ManyToManyField(User, related_name='saved_places', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    # 🌟 প্রথম ১৫ দিন পর্যন্ত NEW ব্যাজ দেখানোর ডাইনামিক প্রপার্টি
    @property
    def is_new(self):
        if not self.created_at:
            return True
        return timezone.now() <= self.created_at + timedelta(days=15)


class PlaceImage(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='places/gallery/')
    caption = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Image for {self.place.name}"


class MenuItem(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='menu_items')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.place.name}"


class Review(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.place.name} ({self.rating}★)"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, default='customer')

    def __str__(self):
        return f"{self.user.username} Profile"