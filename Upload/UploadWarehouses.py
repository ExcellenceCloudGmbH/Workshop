import pandas as pd
from django.db import models
from django_lifecycle import hook, AFTER_SAVE
from lex.audit_logging.handlers.LexLogger import LexLogger
from lex.core.models.LexModel import LexModel

from Workshop.Input.Warehouse import Warehouse


logger = LexLogger()


class UploadWarehouses(LexModel):
    """
    Upload **warehouses.csv** to populate the Warehouse dimension table.

    Attach the CSV, save, and the AFTER_SAVE hook will:
    1. Delete all previously-uploaded warehouse records from this file
    2. Read the CSV with pandas
    3. Bulk-create new Warehouse records
    4. Log a summary via LexLogger
    """

    id = models.AutoField(primary_key=True)
    upload_name = models.CharField(max_length=200)
    data_file = models.FileField(upload_to="workshop_uploads/")
    upload_comment = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Warehouse Upload: {self.upload_name}"

    @hook(AFTER_SAVE)
    def process_upload(self):
        Warehouse.objects.filter().delete()

        df = pd.read_csv(self.data_file.path)
        created = []
        for _, row in df.iterrows():
            obj = Warehouse(
                name=row["name"],
                region=row["region"],
                country=row["country"],
                capacity_units=int(row["capacity_units"]),
                operating_cost_monthly=float(row["operating_cost_monthly"]),
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
            )
            created.append(obj)

        Warehouse.objects.bulk_create(created)

        logger.add_heading("📦 Warehouse Upload Complete", level=2)
        logger.add_text(f"**File:** {self.data_file.name}")
        logger.add_text(f"**Records created:** {len(created)}")
        logger.add_table(
            headers=["Name", "Region", "Country", "Capacity"],
            rows=[[w.name, w.region, w.country, f"{w.capacity_units:,}"] for w in created],
        )
        logger.log()
