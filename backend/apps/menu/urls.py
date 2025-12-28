from django.urls import path
from apps.menu import views

urlpatterns = [
    path("categories/", views.CategoryListView.as_view(), name="menu-categories"),
    path("products/", views.ProductListCreateView.as_view(), name="menu-products"),
]
