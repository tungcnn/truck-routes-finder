from django.db import models


# Create your models here.
class FuelStop(models.Model):
    truckStopId = models.BigIntegerField()
    name = models.TextField()
    address = models.TextField()
    city = models.TextField()
    state = models.TextField()
    rackId = models.TextField()
    retailPrice = models.FloatField()
    googleMapId = models.TextField()

    def __str__(self):
        return self.name