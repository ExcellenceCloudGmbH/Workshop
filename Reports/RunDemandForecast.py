"""
Step 2 — Run Demand Forecast  (Trigger)
========================================

A **CalculationModel** that triggers the batch ``DemandForecast``
(CalculatedModelMixin).  When the user clicks **Calculate**, this
model calls ``DemandForecast.create()`` which generates all 96
warehouse × product combinations and computes each **sequentially**.

Why a separate trigger?
-----------------------
``CalculatedModelMixin`` models don't expose a Calculate button in the
UI — they need a ``CalculationModel`` to invoke ``.create()``.  This
model is that glue: one click → 96 forecasts.
"""

import time

from django.db import models
from lex.core.models.CalculationModel import CalculationModel
from lex.audit_logging.handlers.LexLogger import LexLogger

from Workshop.Reports.DemandForecast import DemandForecast


logger = LexLogger()


class RunDemandForecast(CalculationModel):

    id = models.AutoField(primary_key=True)
    run_name = models.CharField(max_length=200, default="Demand Forecast Run")

    # ── Computed summary ─────────────────────────────────────────────
    total_forecasts = models.IntegerField(default=0)
    total_seconds = models.FloatField(default=0)

    def __str__(self):
        return f"📊 {self.run_name}"

    def calculate(self):
        t0 = time.perf_counter()

        logger.add_heading("📊 Demand Forecast — Sequential Batch", level=2)
        logger.add_text(
            "Running `DemandForecast.create()` — this generates **all** "
            "warehouse × product combinations and computes each one "
            "**sequentially** on the main thread."
        )
        logger.add_horizontal_rule()
        logger.log()

        # Trigger the batch generation + sequential calculation
        DemandForecast.create()

        elapsed = time.perf_counter() - t0
        n = DemandForecast.objects.count()

        self.total_forecasts = n
        self.total_seconds = round(elapsed, 2)
        self.save(skip_hooks=True)

        logger.add_horizontal_rule()
        logger.add_heading("✅ Sequential Batch Complete", level=2)
        logger.add_table(
            headers=["Metric", "Value"],
            rows=[
                ["Total forecasts", str(n)],
                ["Strategy", "Sequential (single thread)"],
                ["⏱️ Total time", f"**{elapsed:.2f} s**"],
                ["Avg per forecast", f"{elapsed / max(n, 1) * 1000:.0f} ms"],
            ],
        )
        logger.add_text(
            "> 💡 All {} forecasts ran one-by-one on the main thread.  "
            "Next, try **Step 3** to see the same work done in parallel "
            "— expect a **5–8× speedup**.".format(n)
        )
        logger.log()
