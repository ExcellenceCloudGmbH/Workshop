from django.db import models
from lex.core.models.LexModel import LexModel

from Workshop.Input.Warehouse import Warehouse
from Workshop.Input.ProductCategory import ProductCategory
from Workshop.Input.Supplier import Supplier


class ShipmentRecord(LexModel):
    """
    One inbound shipment to a NovaTrans warehouse.

    The shipment history CSV contains ~2 300 records covering 12 months
    of operations (Jan–Dec 2024).  These records are the raw input for
    every downstream calculation (demand forecasting, inventory
    optimisation, supplier risk scoring).
    """

    id = models.AutoField(primary_key=True)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="shipments"
    )
    product_category = models.ForeignKey(
        ProductCategory, on_delete=models.CASCADE, related_name="shipments"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="shipments"
    )
    ship_date = models.DateField()
    quantity = models.IntegerField()
    unit_cost = models.FloatField(help_text="Actual cost per unit for this shipment")
    delay_days = models.IntegerField(default=0, help_text="Days late vs. schedule")
    damage_rate = models.FloatField(default=0.0, help_text="Fraction of units damaged")
    order_id = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.order_id}: {self.warehouse} ← {self.product_category} ({self.ship_date})"
