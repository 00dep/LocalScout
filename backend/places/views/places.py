"""Place listing, detail, creation, and management views."""
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from places.models import Place, Category, PlaceImage, MenuItem
from places.forms import PlaceForm

CITIES = ['Ranaghat', 'Krishnanagar', 'Kalyani']

def home(request):
    places = Place.objects.filter(is_approved=True).select_related('category').order_by("-created_at")
    query = request.GET.get('q')
    if query:
        places = places.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(address__icontains=query) | Q(category__name__icontains=query))
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
        places = places.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(address__icontains=query))
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
    is_already_rated = request.user.is_authenticated and place.reviews.filter(user=request.user).exists()
    return render(request, "places/place_detail.html", {
        "place": place,
        "is_already_rated": is_already_rated,
        "total_ratings_count": place.reviews.count(),
        "is_in_wishlist": request.user.is_authenticated and place.saved_by.filter(id=request.user.id).exists(),
    })

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
            for img in request.FILES.getlist('gallery_images'):
                PlaceImage.objects.create(place=edited_place, image=img)
            messages.success(request, "Store updated successfully! Gallery images added.")
            return redirect('edit_place', pk=place.pk)
    else:
        form = PlaceForm(instance=place)
    return render(request, 'places/edit_place.html', {'form': form, 'place': place})

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
@require_POST
def add_menu_item(request, pk):
    place = get_object_or_404(Place, pk=pk, owner=request.user)
    name = request.POST.get('name')
    price = request.POST.get('price')
    if name and price:
        MenuItem.objects.create(place=place, name=name, description=request.POST.get('description', ''), price=price)
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