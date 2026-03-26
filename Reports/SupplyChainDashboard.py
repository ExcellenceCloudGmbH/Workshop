"""
Step 4 — Supply Chain Risk Dashboard  (Orchestrator)
=====================================================

The grand finale.  This **CalculationModel** orchestrates the full
risk-analysis pipeline in three phases:

  Phase A — **WaitForTasks**
      Dispatch ``SupplierRiskScore.create()`` (160 Monte Carlo simulations)
      to Celery workers in parallel.  **Block** until every single score
      has finished.  The log will show the total wait time.

  Phase B — **Aggregate**
      Read the completed risk scores, compute per-warehouse and global
      summaries, build a risk heat-map.

  Phase C — **FireAndForget**
      For every HIGH / CRITICAL risk combination, create an
      ``AlertDispatcher`` record and dispatch it to Celery — but do
      **NOT** wait.  The alerts will be sent in the background after
      the dashboard has already returned.

What it demonstrates
--------------------
* **WaitForTasks** — blocking parallel dispatch  (Phase A)
* **FireAndForget** — non-blocking dispatch      (Phase C)
* Orchestrating *other* models from within a CalculationModel
* Rich multi-section LexLogger output with timing breakdown
* The contrast:  WaitForTasks takes ~3 s (parallel Monte Carlo),
  while FireAndForget returns in < 0.1 s (alerts still running)
"""

import time

from django.db import models
from lex.core.models.CalculationModel import CalculationModel
from lex.audit_logging.handlers.LexLogger import LexLogger
from lex.lex_app.celery_tasks import WaitForTasks, FireAndForget

from Workshop.Input.Warehouse import Warehouse
from Workshop.Input.Supplier import Supplier
from Workshop.Reports.SupplierRiskScore import SupplierRiskScore
from Workshop.Reports.AlertDispatcher import AlertDispatcher


logger = LexLogger()


class SupplyChainDashboard(CalculationModel):

    id = models.AutoField(primary_key=True)
    analysis_name = models.CharField(max_length=200, default="Risk Analysis Run")

    # ── Computed summary fields ──────────────────────────────────────
    total_combinations = models.IntegerField(default=0)
    critical_count = models.IntegerField(default=0)
    high_count = models.IntegerField(default=0)
    medium_count = models.IntegerField(default=0)
    low_count = models.IntegerField(default=0)
    total_expected_loss_eur = models.FloatField(default=0)
    total_var95_eur = models.FloatField(default=0)
    alerts_dispatched = models.IntegerField(default=0)
    phase_a_seconds = models.FloatField(default=0)
    phase_b_seconds = models.FloatField(default=0)
    phase_c_seconds = models.FloatField(default=0)
    total_seconds = models.FloatField(default=0)

    def __str__(self):
        return f"🌐 {self.analysis_name}"

    def calculate(self):
        t_total = time.perf_counter()

        logger.add_heading("🌐 Supply Chain Risk Dashboard", level=1)
        logger.add_text(f"**Run:** {self.analysis_name}")
        logger.add_horizontal_rule()

        # ═════════════════════════════════════════════════════════════
        #  PHASE A — WaitForTasks  (blocking parallel Monte Carlo)
        # ═════════════════════════════════════════════════════════════
        logger.add_heading("Phase A — Supplier Risk Simulation  (WaitForTasks)", level=2)
        logger.add_text(
            "Dispatching **SupplierRiskScore** for all supplier × warehouse "
            "combinations.  Using `WaitForTasks` to run them in parallel "
            "and **block** until every simulation has completed …"
        )

        t_a = time.perf_counter()

        with WaitForTasks():
            SupplierRiskScore.create()

        phase_a = time.perf_counter() - t_a

        risk_scores = SupplierRiskScore.objects.all()
        n_scores = risk_scores.count()

        logger.add_text(f"✅ **{n_scores} risk scores** completed in **{phase_a:.2f} s**")
        logger.add_text(
            "> 💡 Without parallelism this would take ~{:.0f} s.  "
            "`WaitForTasks` dispatched {} Celery tasks and blocked until "
            "all finished.".format(phase_a * 4, n_scores)
        )
        logger.add_horizontal_rule()

        # ═════════════════════════════════════════════════════════════
        #  PHASE B — Aggregate results
        # ═════════════════════════════════════════════════════════════
        logger.add_heading("Phase B — Risk Aggregation", level=2)
        t_b = time.perf_counter()

        critical = risk_scores.filter(risk_rating="CRITICAL")
        high = risk_scores.filter(risk_rating="HIGH")
        medium = risk_scores.filter(risk_rating="MEDIUM")
        low = risk_scores.filter(risk_rating="LOW")

        self.total_combinations = n_scores
        self.critical_count = critical.count()
        self.high_count = high.count()
        self.medium_count = medium.count()
        self.low_count = low.count()

        # Financial totals
        total_loss = sum(r.expected_loss_eur for r in risk_scores)
        total_var = sum(r.var_95_eur for r in risk_scores)
        self.total_expected_loss_eur = round(total_loss, 2)
        self.total_var95_eur = round(total_var, 2)

        # Risk heat-map: warehouse × top-5 riskiest suppliers
        warehouses = Warehouse.objects.all().order_by("name")
        top_risky_suppliers = (
            risk_scores.order_by("-disruption_probability")
            .values_list("supplier__name", flat=True)
            .distinct()[:6]
        )

        heatmap_rows = []
        for wh in warehouses:
            row = [wh.name]
            for sup_name in top_risky_suppliers:
                score = risk_scores.filter(
                    warehouse=wh, supplier__name=sup_name
                ).first()
                if score:
                    emoji = {
                        "LOW": "🟢", "MEDIUM": "🟡",
                        "HIGH": "🟠", "CRITICAL": "🔴",
                    }.get(score.risk_rating, "⚪")
                    row.append(f"{emoji} {score.disruption_probability:.0%}")
                else:
                    row.append("—")
            heatmap_rows.append(row)

        phase_b = time.perf_counter() - t_b

        # Log aggregation results
        logger.add_heading("Risk Distribution", level=3)
        logger.add_table(
            headers=["Rating", "Count", "% of Total"],
            rows=[
                ["🔴 CRITICAL", str(self.critical_count),
                 f"{self.critical_count / max(n_scores, 1) * 100:.1f}%"],
                ["🟠 HIGH", str(self.high_count),
                 f"{self.high_count / max(n_scores, 1) * 100:.1f}%"],
                ["🟡 MEDIUM", str(self.medium_count),
                 f"{self.medium_count / max(n_scores, 1) * 100:.1f}%"],
                ["🟢 LOW", str(self.low_count),
                 f"{self.low_count / max(n_scores, 1) * 100:.1f}%"],
            ],
        )

        logger.add_heading("Financial Exposure", level=3)
        logger.add_table(
            headers=["Metric", "Value"],
            rows=[
                ["Total expected loss (monthly)", f"€{self.total_expected_loss_eur:,.2f}"],
                ["Total VaR 95% (monthly)", f"€{self.total_var95_eur:,.2f}"],
            ],
        )

        logger.add_heading("Risk Heat-Map (Warehouse × Top Risky Suppliers)", level=3)
        logger.add_table(
            headers=["Warehouse"] + list(top_risky_suppliers),
            rows=heatmap_rows,
        )
        logger.add_horizontal_rule()

        # ═════════════════════════════════════════════════════════════
        #  PHASE C — FireAndForget  (non-blocking alert dispatch)
        # ═════════════════════════════════════════════════════════════
        logger.add_heading("Phase C — Alert Dispatch  (FireAndForget)", level=2)
        logger.add_text(
            "Dispatching **AlertDispatcher** for every HIGH and CRITICAL "
            "combination.  Using `FireAndForget` so we do **NOT** wait — "
            "alerts will be sent in the background."
        )

        t_c = time.perf_counter()

        # Collect HIGH + CRITICAL combinations
        alert_targets = risk_scores.filter(risk_rating__in=["HIGH", "CRITICAL"])
        n_alerts = alert_targets.count()

        # Clean up previous alerts
        AlertDispatcher.objects.all().delete()

        with FireAndForget():
            for score in alert_targets:
                alert = AlertDispatcher(
                    warehouse=score.warehouse,
                    supplier=score.supplier,
                    risk_rating=score.risk_rating,
                    alert_channel="both" if score.risk_rating == "CRITICAL" else "email",
                )
                alert.save()
                alert.try_calculate()

        phase_c = time.perf_counter() - t_c
        total_elapsed = time.perf_counter() - t_total

        self.alerts_dispatched = n_alerts
        self.phase_a_seconds = round(phase_a, 2)
        self.phase_b_seconds = round(phase_b, 2)
        self.phase_c_seconds = round(phase_c, 2)
        self.total_seconds = round(total_elapsed, 2)
        self.save(skip_hooks=True)

        logger.add_text(
            f"🚀 **{n_alerts} alerts** dispatched in **{phase_c:.2f} s** — "
            f"and we did NOT wait for them to finish!"
        )
        logger.add_text(
            "> 💡 Each alert takes ~2 s to \"send\".  With {} alerts that "
            "would be **{:.0f} s** if we waited.  But `FireAndForget` "
            "returned in **{:.2f} s** — the alerts are being sent by "
            "Celery workers right now, in the background.".format(
                n_alerts, n_alerts * 2, phase_c
            )
        )
        logger.add_horizontal_rule()

        # ═════════════════════════════════════════════════════════════
        #  TIMING SUMMARY
        # ═════════════════════════════════════════════════════════════
        logger.add_heading("⏱️ Timing Breakdown", level=2)
        logger.add_table(
            headers=["Phase", "Strategy", "Time"],
            rows=[
                ["A — Risk Simulation", "**WaitForTasks** (parallel, blocking)",
                 f"**{self.phase_a_seconds:.2f} s**"],
                ["B — Aggregation", "Synchronous",
                 f"{self.phase_b_seconds:.2f} s"],
                ["C — Alert Dispatch", "**FireAndForget** (parallel, non-blocking)",
                 f"**{self.phase_c_seconds:.2f} s**"],
                ["**TOTAL**", "", f"**{self.total_seconds:.2f} s**"],
            ],
        )

        logger.add_heading("Key Takeaways", level=3)
        logger.add_text(
            "1. **WaitForTasks** ran 160 Monte Carlo simulations in parallel "
            "and *blocked* until all results were ready — we needed them for Phase B.\n"
            "2. **FireAndForget** dispatched alert notifications and returned "
            "*instantly* — we didn't need to wait for emails to be sent.\n"
            "3. The total dashboard time is dominated by Phase A (the real work), "
            "not Phase C (the side-effects)."
        )
        logger.log()
