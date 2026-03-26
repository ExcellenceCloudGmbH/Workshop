from django.db import models
from lex.core.models.LexModel import LexModel


class ProductCategory(LexModel):
    """
    A product line handled by NovaTrans warehouses.

    Contains physical attributes used by the logistics calculations
    (weight, volume, shelf-life) plus the per-unit value used for
    financial risk modelling.
    """

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120, unique=True)
    sku_prefix = models.CharField(max_length=10)
    weight_kg = models.FloatField(help_text="Average weight per unit (kg)")
    volume_m3 = models.FloatField(help_text="Average volume per unit (m³)")
    unit_value = models.FloatField(help_text="Catalogue price per unit (EUR)")
    shelf_life_days = models.IntegerField(
        default=0, help_text="0 = non-perishable"
    )
    hazmat_class = models.CharField(
        max_length=10, blank=True, default="",
        help_text="UN hazmat class (empty = none)",
    )

    def __str__(self):
        return f"{self.name} [{self.sku_prefix}]"
