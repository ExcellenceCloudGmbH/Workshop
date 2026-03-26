"""
Step 1 — Sequential Inventory Analysis
=======================================

A plain **CalculationModel** that analyses a *single warehouse* when
the user clicks **Calculate**.

What it demonstrates
--------------------
* The CalculationModel state-machine  (NOT_CALCULATED → IN_PROGRESS → SUCCESS)
* Heavy per-record computation  (safety stock, EOQ, carrying cost)
* Rich LexLogger output  (tables, headings, timing)

Why it's slow
-------------
This model processes ONE warehouse at a time.  To cover all 8 hubs
the user must trigger each individually — there is no batch dispatch
and no parallelism.  The next steps will solve that.
"""

import time
import math

import numpy as np
from django.db import models
from lex.core.models.CalculationModel import CalculationModel
from lex.audit_logging.handlers.LexLogger import LexLogger

from Workshop.Input.Warehouse import Warehouse
from Workshop.Input.ProductCategory import ProductCategory
from Workshop.Input.ShipmentRecord import ShipmentRecord


logger = LexLogger()


class InventoryOptimizer(CalculationModel):

    id = models.AutoField(primary_key=True)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE,
        help_text="Select the warehouse to analyse",
    )

    # ── Computed outputs (filled by calculate()) ─────────────────────
    total_products_analysed = models.IntegerField(default=0)
    total_safety_stock_units = models.FloatField(default=0)
    total_carrying_cost_eur = models.FloatField(default=0)
    avg_service_level = models.FloatField(default=0)
    computation_seconds = models.FloatField(default=0)

    def __str__(self):
        return f"Inventory Analysis — {self.warehouse}"

    # ─────────────────────────────────────────────────────────────────
    #  Core calculation — called when user clicks "Calculate"
    # ─────────────────────────────────────────────────────────────────
    def calculate(self):
        t0 = time.perf_counter()

        products = ProductCategory.objects.all()
        shipments = ShipmentRecord.objects.filter(warehouse=self.warehouse)

        if not shipments.exists():
            logger.add_heading("⚠️ No shipment data", level=2)
            logger.add_text(f"Warehouse **{self.warehouse.name}** has no shipment records.")
            logger.log()
            return

        logger.add_heading(f"📦 Inventory Optimisation — {self.warehouse.name}", level=2)
        logger.add_text(
            f"Analysing **{products.count()} products** across "
            f"**{shipments.count():,} shipment records** …"
        )
        logger.add_horizontal_rule()

        result_rows = []
        total_safety = 0.0
        total_carrying = 0.0
        service_levels = []

        for product in products:
            prod_ships = shipments.filter(product_category=product)
            if not prod_ships.exists():
                continue

            quantities = np.array(list(prod_ships.values_list("quantity", flat=True)), dtype=float)
            delays = np.array(list(prod_ships.values_list("delay_days", flat=True)), dtype=float)
            costs = np.array(list(prod_ships.values_list("unit_cost", flat=True)), dtype=float)

            # ── Statistical analysis ────────────────────────────────
            mean_demand = float(np.mean(quantities))
            std_demand = float(np.std(quantities, ddof=1)) if len(quantities) > 1 else 0.0
            mean_lead = max(float(np.mean(delays)) + 1, 1.0)  # +1 = min transit
            std_lead = float(np.std(delays, ddof=1)) if len(delays) > 1 else 0.0
            avg_cost = float(np.mean(costs))

            # ── Bootstrap confidence intervals (500 iterations) ─────
            n_boot = 500
            boot_demands = np.zeros(n_boot)
            for i in range(n_boot):
                sample = np.random.choice(quantities, size=len(quantities), replace=True)
                boot_demands[i] = np.mean(sample)
            ci_lower = float(np.percentile(boot_demands, 2.5))
            ci_upper = float(np.percentile(boot_demands, 97.5))

            # ── Safety stock  (Z=1.96 for 97.5% service level) ─────
            z_score = 1.96
            safety_stock = z_score * math.sqrt(
                mean_lead * std_demand ** 2 + mean_demand ** 2 * std_lead ** 2
            )

            # ── Economic Order Quantity (EOQ) ───────────────────────
            annual_demand = mean_demand * 24  # ~2 shipments/month × 12
            ordering_cost = 150.0  # fixed cost per order
            holding_rate = 0.25  # 25% of unit cost per year
            holding_cost = avg_cost * holding_rate
            eoq = math.sqrt(2 * annual_demand * ordering_cost / max(holding_cost, 0.01))

            # ── Reorder point ───────────────────────────────────────
            reorder_point = mean_demand * mean_lead + safety_stock

            # ── Carrying cost (monthly) ─────────────────────────────
            carrying = safety_stock * avg_cost * holding_rate / 12

            # ── Service level estimation ────────────────────────────
            on_time = float(np.mean(delays == 0))
            service_levels.append(on_time)

            total_safety += safety_stock
            total_carrying += carrying

            result_rows.append([
                product.name,
                f"{mean_demand:,.0f}",
                f"{std_demand:,.0f}",
                f"[{ci_lower:,.0f} – {ci_upper:,.0f}]",
                f"{safety_stock:,.0f}",
                f"{eoq:,.0f}",
                f"{reorder_point:,.0f}",
                f"€{carrying:,.2f}",
                f"{on_time:.0%}",
            ])

            # Small sleep to make timing visible in the UI
            time.sleep(0.12)

        elapsed = time.perf_counter() - t0

        # ── Persist outputs ─────────────────────────────────────────
        self.total_products_analysed = len(result_rows)
        self.total_safety_stock_units = round(total_safety, 1)
        self.total_carrying_cost_eur = round(total_carrying, 2)
        self.avg_service_level = round(
            sum(service_levels) / max(len(service_levels), 1), 4
        )
        self.computation_seconds = round(elapsed, 2)
        self.save(skip_hooks=True)

        # ── Rich log output ─────────────────────────────────────────
        logger.add_heading("Product-Level Analysis", level=3)
        logger.add_table(
            headers=[
                "Product", "μ Demand", "σ Demand", "95% CI",
                "Safety Stock", "EOQ", "Reorder Pt",
                "Carrying $/mo", "On-Time %",
            ],
            rows=result_rows,
        )
        logger.add_horizontal_rule()
        logger.add_heading("Summary", level=3)
        logger.add_table(
            headers=["Metric", "Value"],
            rows=[
                ["Warehouse", self.warehouse.name],
                ["Products analysed", str(self.total_products_analysed)],
                ["Total safety stock", f"{self.total_safety_stock_units:,.0f} units"],
                ["Monthly carrying cost", f"€{self.total_carrying_cost_eur:,.2f}"],
                ["Average on-time rate", f"{self.avg_service_level:.1%}"],
                ["⏱️ Computation time", f"**{elapsed:.2f} s**"],
            ],
        )
        logger.add_text(
            "> 💡 This analysed **one warehouse**.  Imagine running this for all 8 "
            "hubs sequentially — you would wait **{:.0f} seconds**.  "
            "Step 2 and 3 will show a better way.".format(elapsed * 8)
        )
        logger.log()
