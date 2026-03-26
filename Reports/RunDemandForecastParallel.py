"""
Step 3 — Run Parallel Demand Forecast  (Trigger)
=================================================

A **CalculationModel** that triggers the parallel batch
``DemandForecastParallel`` (CalculatedModelMixin).  When the user
clicks **Calculate**, this model calls
``DemandForecastParallel.create()`` which generates the same 96
warehouse × product combinations but dispatches them to Celery
workers **in parallel** (grouped by warehouse).

Compare the timing with Step 2's ``RunDemandForecast`` — same data,
same algorithm, dramatically different wall-clock time.
"""

import time

from django.db import models
from lex.core.models.CalculationModel import CalculationModel
from lex.audit_logging.handlers.LexLogger import LexLogger

from Workshop.Reports.DemandForecastParallel import DemandForecastParallel


logger = LexLogger()


class RunDemandForecastParallel(CalculationModel):

    id = models.AutoField(primary_key=True)
    run_name = models.CharField(max_length=200, default="Parallel Forecast Run")

    # ── Computed summary ─────────────────────────────────────────────
    total_forecasts = models.IntegerField(default=0)
    total_seconds = models.FloatField(default=0)

    def __str__(self):
        return f"⚡ {self.run_name}"

    def calculate(self):
        time.sleep(2)
        t0 = time.perf_counter()

        logger.add_heading("⚡ Demand Forecast — Parallel Batch", level=2)
        logger.add_text(
            "Running `DemandForecastParallel.create()` — same 96 forecasts, "
            "but grouped by **warehouse** (8 groups of 12) and dispatched "
            "to Celery workers in parallel."
        )
        logger.add_horizontal_rule()
        logger.log()

        # Trigger the batch generation + parallel calculation
        from lex.audit_logging.utils.ModelContext import model_logging_context
        DemandForecastParallel.create()

        elapsed = time.perf_counter() - t0
        n = DemandForecastParallel.objects.count()

        self.total_forecasts = n
        self.total_seconds = round(elapsed, 2)
        self.save(skip_hooks=True)

        logger.add_horizontal_rule()
        logger.add_heading("✅ Parallel Batch Complete", level=2)
        logger.add_table(
            headers=["Metric", "Value"],
            rows=[
                ["Total forecasts", str(n)],
                ["Strategy", "Parallel (8 Celery groups)"],
                ["⏱️ Total time", f"**{elapsed:.2f} s**"],
                ["Avg per forecast", f"{elapsed / max(n, 1) * 1000:.0f} ms"],
            ],
        )
        logger.add_text(
            "> 🎉 Compare this with Step 2's sequential time.  "
            "The only code difference is **two lines**: "
            "`parallelizable_fields` and `@lex_shared_task`."
        )
        logger.log()
