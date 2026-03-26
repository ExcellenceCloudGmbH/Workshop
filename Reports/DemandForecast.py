"""
Step 2 — Batch Sequential Demand Forecast
==========================================

A **CalculatedModelMixin** that generates one record for every
warehouse × product combination (8 × 12 = **96 records**) and runs
each forecast **sequentially**.

What it demonstrates
--------------------
* ``defining_fields`` — the cross-product dimensions
* ``get_selected_key_list()`` — returns the cartesian product
* ``create()`` class method — the 4-step pipeline
* No ``parallelizable_fields`` → everything runs in one thread

Why it's slow
-------------
Each forecast involves exponential smoothing, trend detection, and a
500-iteration confidence bootstrap on the warehouse's shipment history.
At ~0.15 s per record × 96 records the total wall-clock time is
**~15 seconds** — all on the main thread.

Step 3 will add parallelism to cut that to ~2 s.
"""

import time
import math

import numpy as np
from django.db import models
from lex.core.mixins.CalculatedModelMixin import CalculatedModelMixin
from lex.audit_logging.handlers.LexLogger import LexLogger

from Workshop.Input.Warehouse import Warehouse
from Workshop.Input.ProductCategory import ProductCategory
from Workshop.Input.ShipmentRecord import ShipmentRecord


logger = LexLogger()


class DemandForecast(CalculatedModelMixin):

    id = models.AutoField(primary_key=True)

    # ── Defining fields (batch dimensions) ───────────────────────────
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    product_category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)

    defining_fields = ["warehouse", "product_category"]

    def get_selected_key_list(self, key):
        if key == "warehouse":
            return list(Warehouse.objects.all())
        if key == "product_category":
            return list(ProductCategory.objects.all())
        return []

    # ── Computed outputs ─────────────────────────────────────────────
    forecast_units_next_quarter = models.FloatField(default=0)
    trend_slope = models.FloatField(default=0)
    seasonality_index = models.FloatField(default=1.0)
    confidence_lower = models.FloatField(default=0)
    confidence_upper = models.FloatField(default=0)
    smoothed_demand = models.FloatField(default=0)
    data_points_used = models.IntegerField(default=0)
    computation_ms = models.FloatField(default=0)

    class Meta:
        unique_together = ("warehouse", "product_category")

    def __str__(self):
        return f"Forecast: {self.warehouse} × {self.product_category}"

    # ─────────────────────────────────────────────────────────────────
    #  Per-record calculation
    # ─────────────────────────────────────────────────────────────────
    def calculate(self):
        t0 = time.perf_counter()

        shipments = ShipmentRecord.objects.filter(
            warehouse=self.warehouse,
            product_category=self.product_category,
        ).order_by("ship_date")

        quantities = np.array(
            list(shipments.values_list("quantity", flat=True)), dtype=float
        )

        if len(quantities) < 3:
            self.forecast_units_next_quarter = 0
            self.data_points_used = len(quantities)
            self.computation_ms = round((time.perf_counter() - t0) * 1000, 1)
            self.save(skip_hooks=True)
            return

        # ── Exponential smoothing (α = 0.3) ─────────────────────────
        alpha = 0.3
        smoothed = np.zeros_like(quantities)
        smoothed[0] = quantities[0]
        for i in range(1, len(quantities)):
            smoothed[i] = alpha * quantities[i] + (1 - alpha) * smoothed[i - 1]

        # ── Trend via linear regression ──────────────────────────────
        x = np.arange(len(quantities), dtype=float)
        x_mean = np.mean(x)
        y_mean = np.mean(quantities)
        slope = float(np.sum((x - x_mean) * (quantities - y_mean)) /
                       max(np.sum((x - x_mean) ** 2), 1e-9))

        # ── Seasonality index (ratio of recent quarter to mean) ──────
        recent_q = quantities[-min(6, len(quantities)):]
        seasonality = float(np.mean(recent_q) / max(y_mean, 1))

        # ── Forecast: smoothed tail + trend extrapolation × season ───
        periods_ahead = 6  # next quarter ≈ 6 shipment periods
        forecast = (smoothed[-1] + slope * periods_ahead) * seasonality

        # ── Bootstrap confidence interval (500 iterations) ───────────
        n_boot = 500
        boot_forecasts = np.zeros(n_boot)
        for b in range(n_boot):
            idx = np.random.choice(len(quantities), size=len(quantities), replace=True)
            sample = quantities[idx]
            s = np.zeros_like(sample)
            s[0] = sample[0]
            for i in range(1, len(sample)):
                s[i] = alpha * sample[i] + (1 - alpha) * s[i - 1]
            boot_forecasts[b] = s[-1] * seasonality

        ci_lo = float(np.percentile(boot_forecasts, 5))
        ci_hi = float(np.percentile(boot_forecasts, 95))

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # ── Persist ──────────────────────────────────────────────────
        self.forecast_units_next_quarter = round(forecast, 1)
        self.trend_slope = round(slope, 4)
        self.seasonality_index = round(seasonality, 4)
        self.confidence_lower = round(ci_lo, 1)
        self.confidence_upper = round(ci_hi, 1)
        self.smoothed_demand = round(float(smoothed[-1]), 1)
        self.data_points_used = len(quantities)
        self.computation_ms = round(elapsed_ms, 1)
        self.save(skip_hooks=True)

        # Small sleep to guarantee visible timing in the UI
        time.sleep(0.12)

        # ── Log ──────────────────────────────────────────────────────
        logger.add_heading(
            f"📈 {self.warehouse.name} × {self.product_category.name}", level=3
        )
        logger.add_table(
            headers=["Metric", "Value"],
            rows=[
                ["Data points", str(self.data_points_used)],
                ["Smoothed demand (last)", f"{self.smoothed_demand:,.1f}"],
                ["Trend slope", f"{self.trend_slope:+.4f}"],
                ["Seasonality index", f"{self.seasonality_index:.2f}"],
                ["**Forecast (next Q)**", f"**{self.forecast_units_next_quarter:,.1f} units**"],
                ["90% CI", f"[{self.confidence_lower:,.1f} – {self.confidence_upper:,.1f}]"],
                ["Computation", f"{self.computation_ms:.0f} ms"],
            ],
        )
        logger.log()
