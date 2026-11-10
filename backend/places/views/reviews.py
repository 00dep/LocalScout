"""Review and rating views."""
from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from places.models import Place, Review

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

    Review.objects.create(place=place, user=request.user, rating=rating_val, comment="")
    all_reviews = place.reviews.all()
    count = all_reviews.count()

    if count > 0:
        avg_val = sum(r.rating for r in all_reviews) / count
        place.rating = Decimal(str(round(avg_val, 1)))
        place.save()

    messages.success(request, "Thank you for rating this place!")
    return redirect("place_detail", pk=pk)