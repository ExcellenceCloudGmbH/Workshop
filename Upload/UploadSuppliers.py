import pandas as pd
from django.db import models
from django_lifecycle import hook, AFTER_SAVE
from lex.audit_logging.handlers.LexLogger import LexLogger
from lex.core.models.LexModel import LexModel

from Workshop.Input.Supplier import Supplier


logger = LexLogger()


class UploadSuppliers(LexModel):
    """
    Upload **suppliers.csv** to populate the Supplier dimension table.
    """

    id = models.AutoField(primary_key=True)
    upload_name = models.CharField(max_length=200)
    data_file = models.FileField(upload_to="workshop_uploads/")
    upload_comment = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Supplier Upload: {self.upload_name}"

    @hook(AFTER_SAVE)
    def process_upload(self):
        Supplier.objects.filter().delete()

        df = pd.read_csv(self.data_file.path)
        created = []
        for _, row in df.iterrows():
            obj = Supplier(
                name=row["name"],
                country=row["country"],
                lead_time_days=int(row["lead_time_days"]),
                reliability_score=float(row["reliability_score"]),
                annual_capacity=int(row["annual_capacity"]),
                min_order_qty=int(row["min_order_qty"]),
            )
            created.append(obj)

        Supplier.objects.bulk_create(created)

        logger.add_heading("🚚 Supplier Upload Complete", level=2)
        logger.add_text(f"**File:** {self.data_file.name}")
        logger.add_text(f"**Records created:** {len(created)}")
        logger.add_table(
            headers=["Supplier", "Country", "Lead Time (d)", "Reliability"],
            rows=[
                [s.name, s.country, str(s.lead_time_days), f"{s.reliability_score:.0%}"]
                for s in created
            ],
        )
        logger.log()
