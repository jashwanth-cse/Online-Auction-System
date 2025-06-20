from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('explore/', views.explore, name='explore'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('list/', views.list_item, name='list_item'),
    path('item/<str:item_id>/', views.item_detail, name='item_detail'),
    path('item/<str:item_id>/end/', views.end_auction, name='end_auction'),
    path('item/<str:item_id>/result/', views.auction_result, name='auction_result'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('profile/', views.profile, name='profile'),
]