from django.urls import path
from . import views

urlpatterns = [
    path('', views.process_pnr, name='process_pnr'),
]
