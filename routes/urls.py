from django.urls import path

from . import views

urlpatterns = [
    path("import", views.importTruckStop, name="importTruckStop"),
    path("search", views.search, name="search"),
]