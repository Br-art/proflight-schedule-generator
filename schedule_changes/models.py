from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    vars_username = models.CharField(max_length=50, unique=True)
    real_name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.real_name} ({self.vars_username})"

class TravelAgency(models.Model):
    iata_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.iata_number})"

class ProcessedBooking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    pnr = models.CharField(max_length=10, unique=True)
    contact_name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=255, blank=True, null=True)
    passengers = models.TextField(blank=True, null=True)
    flights_summary = models.TextField(blank=True, null=True)
    raw_gds = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.pnr
