import pandas as pd
from django.db import models
from django_lifecycle import hook, AFTER_SAVE
from lex.audit_logging.handlers.LexLogger import LexLogger
from lex.core.models.LexModel import LexModel

from Workshop.Input.ProductCategory import ProductCategory


logger = LexLogger()


class UploadProducts(LexModel):
    """
    Upload **product_categories.csv** to populate the ProductCategory
    dimension table.
    """

    id = models.AutoField(primary_key=True)
    upload_name = models.CharField(max_length=200)
    data_file = models.FileField(upload_to="workshop_uploads/")
    upload_comment = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Product Upload: {self.upload_name}"

    @hook(AFTER_SAVE)
    def process_upload(self):
        ProductCategory.objects.filter().delete()

        df = pd.read_csv(self.data_file.path)
        created = []
        for _, row in df.iterrows():
            obj = ProductCategory(
                name=row["name"],
                sku_prefix=row["sku_prefix"],
                weight_kg=float(row["weight_kg"]),
                volume_m3=float(row["volume_m3"]),
                unit_value=float(row["unit_value"]),
                shelf_life_days=int(row["shelf_life_days"]),
                hazmat_class=str(row["hazmat_class"]) if pd.notna(row["hazmat_class"]) else "",
            )
            created.append(obj)

        ProductCategory.objects.bulk_create(created)

        logger.add_heading("🏷️ Product Category Upload Complete", level=2)
        logger.add_text(f"**File:** {self.data_file.name}")
        logger.add_text(f"**Records created:** {len(created)}")
        logger.add_table(
            headers=["Name", "SKU", "Unit Value (€)", "Weight (kg)"],
            rows=[
                [p.name, p.sku_prefix, f"{p.unit_value:,.2f}", f"{p.weight_kg:.1f}"]
                for p in created
            ],
        )
        logger.log()
