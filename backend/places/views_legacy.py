import random
from datetime import timedelta
from decimal import Decimal
import resend
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Place, Category, Review, UserProfile, PlaceImage, MenuItem
from .forms import UserRegistrationForm, PlaceForm

# 📍 City List
CITIES = ['Ranaghat', 'Krishnanagar', 'Kalyani']


@api_view(['GET'])
def api_search_places(request):
    query = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()

    places = Place.objects.filter(is_approved=True).select_related('category')

    if query:
        places = places.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(address__icontains=query)
        )
    if location:
        places = places.filter(location__iexact=location)

    data = [
        {
            'id': p.id,
            'name': p.name,
            'address': p.address,
            'rating': getattr(p, 'rating', None),
            'image': p.image.url if p.image else None,
            'category': p.category.name if p.category else "General"
        } for p in places[:8]
    ]
    return Response(data)


def signup_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            role = form.cleaned_data.get('role', 'customer')

            # ১. ডাটাবেজে ইউজারনেম বা ইমেইল ইতিমধ্যে আছে কিনা পরীক্ষা
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username is already taken.")
                return render(request, 'places/signup.html', {'form': form})

            if User.objects.filter(email=email).exists():
                messages.error(request, "Email is already registered.")
                return render(request, 'places/signup.html', {'form': form})

            # ২. 6-Digit random OTP তৈরি ও Session Storage
            otp = str(random.randint(100000, 999999))
            request.session['signup_data'] = {
                'username': username,
                'email': email,
                'password': password,
                'role': role,
                'otp': otp,
                'otp_expires_at': (timezone.now() + timedelta(minutes=10)).isoformat(),
            }

            resend_api_key = getattr(settings, 'RESEND_API_KEY', '').strip()
            if settings.DEBUG and not resend_api_key.startswith('re_'):
                messages.warning(request, f"Development mode: your OTP is {otp}")
                return redirect('verify_otp')

            # ৩. Resend SDK ব্যবহার করে OTP ইমেইল পাঠানো
            try:
                resend.api_key = resend_api_key
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'onboarding@resend.dev')

                resend.Emails.send({
                    "from": from_email,
                    "to": [email],
                    "subject": "Verify Your Email - OTP",
                    "html": f"<p>Hello <strong>{username}</strong>,</p>"
                            f"<p>Your OTP for registration is: <strong>{otp}</strong></p>"
                            f"<p>Do not share this code with anyone.</p>",
                })
                
                messages.success(request, f"An OTP code has been sent to {email}")
                return redirect('verify_otp')
            except Exception as e:
                print("Email Error:", e)
                if settings.DEBUG:
                    messages.warning(request, f"Development mode: email could not be sent, so your OTP is {otp}")
                    return redirect('verify_otp')
                messages.error(request, "Signup failed because the OTP email could not be sent. Check your RESEND_API_KEY and try again.")
                return render(request, 'places/signup.html', {'form': form})
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = UserRegistrationForm()

    return render(request, 'places/signup.html', {'form': form})


def verify_otp_view(request):
    signup_data = request.session.get('signup_data')

    if not signup_data:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('signup')

    if request.method == 'POST':
        user_otp = ''.join(request.POST.get('otp', '').strip().split())
        expires_at = signup_data.get('otp_expires_at')
        try:
            otp_expired = expires_at and timezone.now() >= timezone.datetime.fromisoformat(expires_at)
        except (TypeError, ValueError):
            otp_expired = False

        if otp_expired:
            messages.error(request, "This OTP has expired. Please sign up again to receive a new code.")
        elif user_otp == signup_data.get('otp'):
            # ৪. OTP ঠিক থাকলে User তৈরি করা
            user = User.objects.create_user(
                username=signup_data['username'],
                email=signup_data['email'],
                password=signup_data['password']
            )
            # নির্বাচন করা Role অনুযায়ী UserProfile সেট করা
            user_role = signup_data.get('role', 'customer')
            UserProfile.objects.get_or_create(user=user, defaults={'role': user_role})

            del request.session['signup_data']

            login(request, user)
            messages.success(request, "Account verified & created successfully!")
            return redirect('home')
        else:
            messages.error(request, "Invalid OTP! Please enter the correct code.")

    return render(request, 'places/verify_otp.html', {'email': signup_data.get('email')})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # 🔒 নিরাপদ রিডাইরেক্ট ভ্যালিডেশন
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure()
            ):
                return redirect(next_url)
            
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'places/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('home')


@login_required
def add_place(request):
    if request.method == 'POST':
        form = PlaceForm(request.POST, request.FILES) 
        if form.is_valid():
            place = form.save(commit=False)
            place.owner = request.user 
            place.is_approved = False
            place.save()
            return redirect('store_pending')
    else:
        form = PlaceForm()

    return render(request, 'places/add_place.html', {'form': form})


@login_required
def store_pending(request):
    return render(request, 'places/store_pending.html')


@login_required
def profile_view(request):
    user_stores = Place.objects.filter(owner=request.user).select_related('category').order_by('-created_at')
    return render(request, 'places/profile.html', {'user_stores': user_stores})


@require_POST
def google_login_callback(request):
    token = request.POST.get("credential")
    if not token:
        return redirect("home")

    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

        email = idinfo["email"]
        username = email.split("@")[0]

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": username,
                "first_name": idinfo.get("given_name", ""),
                "last_name": idinfo.get("family_name", ""),
            }
        )

        if created:
            UserProfile.objects.get_or_create(user=user, defaults={'role': 'customer'})

        login(request, user)

    except ValueError:
        messages.error(request, "Google login failed.")
        return redirect("home")

    # 🔒 নিরাপদ রিডাইরেক্ট ভ্যালিডেশন
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure()
    ):
        return redirect(next_url)

    return redirect("home")


def home(request):
    places = Place.objects.filter(is_approved=True).select_related('category').order_by("-created_at")
    
    query = request.GET.get('q')
    if query:
        places = places.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(address__icontains=query) |
            Q(category__name__icontains=query)
        )

    cat_id = request.GET.get('category')
    if cat_id:
        places = places.filter(category_id=cat_id)

    location_name = request.GET.get('location')
    if location_name:
        places = places.filter(location__iexact=location_name.strip())

    context = {
        "places": places,
        "featured": Place.objects.filter(is_featured=True, is_approved=True).select_related('category').order_by("-created_at")[:6],
        "categories": Category.objects.all(),
        "cities": CITIES,
        "selected_location": location_name,
    }
    return render(request, "places/home.html", context)


def place_list(request):
    places = Place.objects.filter(is_approved=True).select_related('category', 'owner').order_by("-created_at")
    categories = Category.objects.all()

    query = request.GET.get("q")
    if query:
        places = places.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(address__icontains=query)
        )

    current_category = None
    cat_id = request.GET.get("category")

    if cat_id:
        places = places.filter(category_id=cat_id)
        current_category = get_object_or_404(Category, id=cat_id)

    location_name = request.GET.get("location")
    if location_name:
        places = places.filter(location__iexact=location_name.strip())

    return render(request, "places/place_list.html", {
        "places": places,
        "categories": categories,
        "current_category": current_category,
        "selected_location": location_name,
        "cities": CITIES,
    })


def place_detail(request, pk):
    place = get_object_or_404(Place.objects.select_related('category', 'owner'), pk=pk)

    is_already_rated = False
    if request.user.is_authenticated:
        is_already_rated = Review.objects.filter(place=place, user=request.user).exists()

    total_ratings_count = place.reviews.count()

    return render(request, "places/place_detail.html", {
        "place": place,
        "is_already_rated": is_already_rated,
        "total_ratings_count": total_ratings_count,
        "is_saved": (
            request.user.is_authenticated and
            place.saved_by.filter(id=request.user.id).exists()
        ),
    })


@login_required
@require_POST
def add_review(request, pk):
    place = get_object_or_404(Place, pk=pk)

    if Review.objects.filter(place=place, user=request.user).exists():
        messages.warning(request, "You have already rated this place!")
        return redirect("place_detail", pk=pk)

    try:
        rating_val = int(request.POST.get("rating", 5))
    except (ValueError, TypeError):
        rating_val = 5

    if rating_val < 1 or rating_val > 5:
        rating_val = 5

    Review.objects.create(
        place=place,
        user=request.user,
        rating=rating_val,
        comment=""
    )

    all_reviews = place.reviews.all()
    count = all_reviews.count()

    if count > 0:
        avg_val = sum(r.rating for r in all_reviews) / count
        place.rating = Decimal(str(round(avg_val, 1)))
        place.save()

    messages.success(request, "Thank you for rating this place!")
    return redirect("place_detail", pk=pk)


@login_required
@require_POST
def toggle_save(request, pk):
    place = get_object_or_404(Place, pk=pk)

    if place.saved_by.filter(id=request.user.id).exists():
        place.saved_by.remove(request.user)
    else:
        place.saved_by.add(request.user)

    return redirect("place_detail", pk=pk)


@login_required
def wishlist(request):
    return render(request, "places/wishlist.html", {
        "saved_places": request.user.saved_places.filter(is_approved=True).select_related('category').order_by("-created_at")
    })


@login_required
def edit_place(request, pk):
    place = get_object_or_404(Place, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        form = PlaceForm(request.POST, request.FILES, instance=place)
        if form.is_valid():
            edited_place = form.save(commit=False)
            edited_place.is_approved = False
            edited_place.save()

            images = request.FILES.getlist('gallery_images')
            for img in images:
                PlaceImage.objects.create(place=edited_place, image=img)

            messages.success(request, "Store updated successfully! Gallery images added.")
            return redirect('edit_place', pk=place.pk)
    else:
        form = PlaceForm(instance=place)
        
    return render(request, 'places/edit_place.html', {
        'form': form, 
        'place': place
    })


@login_required
def delete_place(request, pk):
    place = get_object_or_404(Place, pk=pk)
    if request.user != place.owner and not request.user.is_staff:
        return redirect('place_detail', pk=place.pk)
    if request.method == 'POST':
        place.delete()
        messages.success(request, "Store deleted successfully.")
        return redirect('place_list')
    return render(request, 'places/delete_confirm.html', {'place': place})


@login_required
@require_POST
def add_menu_item(request, pk):
    place = get_object_or_404(Place, pk=pk, owner=request.user)
    name = request.POST.get('name')
    description = request.POST.get('description', '')
    price = request.POST.get('price')

    if name and price:
        MenuItem.objects.create(
            place=place,
            name=name,
            description=description,
            price=price
        )
        messages.success(request, "Menu item added successfully!")
    else:
        messages.error(request, "Please fill in all required fields.")

    return redirect('edit_place', pk=place.pk)


@login_required
def delete_menu_item(request, item_id):
    item = get_object_or_404(MenuItem, id=item_id, place__owner=request.user)
    place_pk = item.place.pk
    item.delete()
    messages.success(request, "Menu item deleted successfully!")
    return redirect('edit_place', pk=place_pk)


@login_required
def delete_gallery_image(request, image_id):
    img = get_object_or_404(PlaceImage, id=image_id, place__owner=request.user)
    place_pk = img.place.pk
    img.delete()
    messages.success(request, "Gallery image removed!")
    return redirect('edit_place', pk=place_pk)