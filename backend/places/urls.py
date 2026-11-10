from django.urls import path
from . import views

urlpatterns = [
    # General & Pages
    path('', views.home, name='home'),
    path('places/', views.place_list, name='place_list'),
    path('place/<int:pk>/', views.place_detail, name='place_detail'),
    path('add-place/', views.add_place, name='add_place'),
    path('store-pending/', views.store_pending, name='store_pending'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('profile/', views.profile_view, name='profile'),

    # Actions (Review, Save, Edit, Delete, Menu & Gallery)
    path('place/<int:pk>/review/', views.add_review, name='add_review'),
    path('place/<int:pk>/save/', views.toggle_save, name='toggle_save'),
    path('place/<int:pk>/edit/', views.edit_place, name='edit_place'),
    path('place/<int:pk>/delete/', views.delete_place, name='delete_place'),  # <--- এই লাইনটি যোগ করুন
    path('place/<int:pk>/add-menu/', views.add_menu_item, name='add_menu_item'),
    path('menu-item/<int:item_id>/delete/', views.delete_menu_item, name='delete_menu_item'),
    path('gallery-image/<int:image_id>/delete/', views.delete_gallery_image, name='delete_gallery_image'),

    # Auth & Email Verification
    path('signup/', views.signup_view, name='signup'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'), 
    path('google-login-callback/', views.google_login_callback, name='google_login_callback'),

    # API
    path('api/search/', views.api_search_places, name='api_search_places'),
]