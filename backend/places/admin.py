from django.contrib import admin
from .models import Place, Category, Review, PlaceImage, MenuItem, UserProfile


class PlaceImageInline(admin.TabularInline):
    model = PlaceImage
    extra = 1


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 1


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'location', 'owner', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'category', 'price_range', 'location')
    search_fields = ('name', 'description', 'address')
    actions = ['approve_places']
    
    inlines = [PlaceImageInline, MenuItemInline]

    def approve_places(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, "Selected stores have been approved successfully!")
    
    approve_places.short_description = "Approve selected stores"


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'place', 'price', 'is_available')
    list_filter = ('is_available', 'place')
    search_fields = ('name', 'description', 'place__name')


admin.site.register(Category)
admin.site.register(Review)
admin.site.register(UserProfile)
admin.site.register(PlaceImage)