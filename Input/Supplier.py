from django.db import models
from lex.core.models.LexModel import LexModel


class Supplier(LexModel):
    """
    An international supplier that provides goods to NovaTrans warehouses.

    The *reliability_score* (0–1) directly influences delay probability
    in the supply-chain risk simulation.
    """

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120, unique=True)
    country = models.CharField(max_length=80)
    lead_time_days = models.IntegerField(help_text="Average lead time in days")
    reliability_score = models.FloatField(
        help_text="0.0 (unreliable) – 1.0 (perfect)"
    )
    annual_capacity = models.IntegerField(help_text="Max units per year")
    min_order_qty = models.IntegerField(help_text="Minimum order quantity")

    def __str__(self):
        return f"{self.name} ({self.country})"
