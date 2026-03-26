from django.db import models
from lex.core.models.LexModel import LexModel


class Warehouse(LexModel):
    """
    A global distribution hub operated by NovaTrans.

    Each warehouse serves a geographic region and has a fixed storage
    capacity and monthly operating cost.  These records are populated
    by the *UploadWarehouses* upload model.
    """

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120, unique=True)
    region = models.CharField(
        max_length=20,
        choices=[
            ("EMEA", "Europe, Middle East & Africa"),
            ("APAC", "Asia-Pacific"),
            ("AMERICAS", "Americas"),
            ("MEA", "Middle East & Africa"),
        ],
    )
    country = models.CharField(max_length=80)
    capacity_units = models.IntegerField(help_text="Max storable units")
    operating_cost_monthly = models.FloatField(help_text="Monthly cost in EUR")
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return f"{self.name} ({self.region})"
