from django import forms
from django.contrib.auth.models import User
from .models import MenuItem, Place


class UserRegistrationForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'At least 6 characters'}),
        min_length=6,
        label='Password'
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        # প্লেন টেক্সট পাসওয়ার্ডকে হ্যাশ করে সেভ করার জন্য set_password
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class PlaceForm(forms.ModelForm):
    class Meta:
        model = Place
        fields = [
            'name', 
            'category', 
            'description', 
            'address', 
            'location', 
            'opening_hours', 
            'phone', 
            'website', 
            'price_range', 
            'latitude', 
            'longitude', 
            'image'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Café Bliss'}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Write a short description about this spot...'}),
            'address': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full street address'}),
            'location': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'City or Neighborhood'}),
            'opening_hours': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 9:00 AM - 10:00 PM'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Contact number'}),
            'website': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://example.com'}),
            'price_range': forms.Select(attrs={'class': 'form-input'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 23.8103'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 90.4125'}),
        }


class MenuItemForm(forms.ModelForm):
    price = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'min': '0',
            'step': '0.01',
        }),
    )

    class Meta:
        model = MenuItem
        fields = ['name', 'description', 'price', 'is_available']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.TextInput(attrs={'class': 'form-input'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'h-4 w-4'}),
        }