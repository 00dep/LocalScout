"""API views for the places app."""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Q
from places.models import Place

@api_view(['GET'])
def api_search_places(request):
    query = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()
    places = Place.objects.filter(is_approved=True).select_related('category')

    if query:
        places = places.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(address__icontains=query))
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