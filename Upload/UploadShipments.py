import pandas as pd
from django.db import models
from django_lifecycle import hook, AFTER_SAVE
from lex.audit_logging.handlers.LexLogger import LexLogger
from lex.core.models.LexModel import LexModel

from Workshop.Input.ShipmentRecord import ShipmentRecord
from Workshop.Input.Warehouse import Warehouse
from Workshop.Input.ProductCategory import ProductCategory
from Workshop.Input.Supplier import Supplier


logger = LexLogger()


class UploadShipments(LexModel):
    """
    Upload **shipment_history.csv** — the main transactional dataset.

    This is the heaviest upload (~2 300 rows).  The hook resolves each
    row's warehouse / product / supplier foreign keys by name, then
    bulk-creates ShipmentRecord objects.
    """

    id = models.AutoField(primary_key=True)
    upload_name = models.CharField(max_length=200)
    data_file = models.FileField(upload_to="workshop_uploads/")
    upload_comment = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Shipment Upload: {self.upload_name}"

    @hook(AFTER_SAVE)
    def process_upload(self):
        ShipmentRecord.objects.filter().delete()

        df = pd.read_csv(self.data_file.path, parse_dates=["ship_date"])

        # Build lookup caches so we don't hit the DB per row
        wh_cache = {w.name: w for w in Warehouse.objects.all()}
        prod_cache = {p.name: p for p in ProductCategory.objects.all()}
        sup_cache = {s.name: s for s in Supplier.objects.all()}

        created = []
        skipped = []
        for idx, row in df.iterrows():
            wh = wh_cache.get(row["warehouse"])
            prod = prod_cache.get(row["product_category"])
            sup = sup_cache.get(row["supplier"])

            if not all([wh, prod, sup]):
                skipped.append(row["order_id"])
                continue

            obj = ShipmentRecord(
                warehouse=wh,
                product_category=prod,
                supplier=sup,
                ship_date=row["ship_date"].date(),
                quantity=int(row["quantity"]),
                unit_cost=float(row["unit_cost"]),
                delay_days=int(row["delay_days"]),
                damage_rate=float(row["damage_rate"]),
                order_id=row["order_id"],
            )
            created.append(obj)

        ShipmentRecord.objects.bulk_create(created, batch_size=500)

        # ── Log summary ──────────────────────────────────────────────
        logger.add_heading("📊 Shipment History Upload Complete", level=2)
        logger.add_text(f"**File:** {self.data_file.name}")
        logger.add_text(f"**Records created:** {len(created):,}")
        if skipped:
            logger.add_text(f"**⚠️ Skipped (unresolved FK):** {len(skipped)}")

        # Per-warehouse breakdown
        wh_counts = df["warehouse"].value_counts()
        logger.add_heading("Shipments per Warehouse", level=3)
        logger.add_table(
            headers=["Warehouse", "Shipments"],
            rows=[[wh, str(cnt)] for wh, cnt in wh_counts.items()],
        )

        # Per-product breakdown
        prod_counts = df["product_category"].value_counts()
        logger.add_heading("Shipments per Product", level=3)
        logger.add_table(
            headers=["Product", "Shipments"],
            rows=[[p, str(c)] for p, c in prod_counts.head(12).items()],
        )

        # Delay statistics
        avg_delay = df["delay_days"].mean()
        max_delay = df["delay_days"].max()
        on_time_pct = (df["delay_days"] == 0).mean() * 100
        logger.add_heading("Delivery Performance", level=3)
        logger.add_table(
            headers=["Metric", "Value"],
            rows=[
                ["On-time rate", f"{on_time_pct:.1f}%"],
                ["Average delay", f"{avg_delay:.1f} days"],
                ["Worst delay", f"{max_delay} days"],
            ],
        )
        logger.log()
