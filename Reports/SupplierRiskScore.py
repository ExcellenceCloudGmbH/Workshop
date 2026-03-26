"""
Step 4a — Supplier Risk Score  (Monte Carlo)
=============================================

A **CalculatedModelMixin + @lex_shared_task** that runs a Monte Carlo
disruption simulation for every **supplier × warehouse** combination
(20 × 8 = **160 records**).

Each record simulates 1 000 disruption scenarios to compute:
* Probability of disruption > 5 days
* Expected cost impact (damaged/delayed goods)
* Value-at-Risk (95th percentile loss)
* Risk rating  (LOW / MEDIUM / HIGH / CRITICAL)

This model is **not triggered directly by the user** — it is invoked
by the ``SupplyChainDashboard`` orchestrator via **WaitForTasks**.
"""

import time
import math

import numpy as np
from django.db import models
from lex.core.mixins.CalculatedModelMixin import CalculatedModelMixin
from lex.audit_logging.handlers.LexLogger import LexLogger
from lex.lex_app.celery_tasks import lex_shared_task

from Workshop.Input.Warehouse import Warehouse
from Workshop.Input.Supplier import Supplier
from Workshop.Input.ShipmentRecord import ShipmentRecord


logger = LexLogger()

# ── Risk thresholds ──────────────────────────────────────────────────
RISK_THRESHOLDS = {
    "LOW":      (0.00, 0.10),
    "MEDIUM":   (0.10, 0.30),
    "HIGH":     (0.30, 0.60),
    "CRITICAL": (0.60, 1.01),
}


def _classify_risk(probability):
    for label, (lo, hi) in RISK_THRESHOLDS.items():
        if lo <= probability < hi:
            return label
    return "CRITICAL"


class SupplierRiskScore(CalculatedModelMixin):

    id = models.AutoField(primary_key=True)

    # ── Defining fields ──────────────────────────────────────────────
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)

    defining_fields = ["supplier", "warehouse"]
    parallelizable_fields = ["supplier"]

    def get_selected_key_list(self, key):
        if key == "supplier":
            return list(Supplier.objects.all())
        if key == "warehouse":
            return list(Warehouse.objects.all())
        return []

    # ── Computed outputs ─────────────────────────────────────────────
    disruption_probability = models.FloatField(default=0)
    expected_loss_eur = models.FloatField(default=0)
    var_95_eur = models.FloatField(default=0, help_text="Value-at-Risk 95%")
    avg_delay_simulated = models.FloatField(default=0)
    risk_rating = models.CharField(max_length=10, default="N/A")
    simulations_run = models.IntegerField(default=0)
    computation_ms = models.FloatField(default=0)

    class Meta:
        unique_together = ("supplier", "warehouse")

    def __str__(self):
        return f"Risk: {self.supplier} → {self.warehouse} [{self.risk_rating}]"

    @lex_shared_task
    def calculate(self):
        t0 = time.perf_counter()

        # Historical shipments for this supplier→warehouse pair
        shipments = ShipmentRecord.objects.filter(
            supplier=self.supplier,
            warehouse=self.warehouse,
        )

        delays = np.array(
            list(shipments.values_list("delay_days", flat=True)), dtype=float
        )
        damages = np.array(
            list(shipments.values_list("damage_rate", flat=True)), dtype=float
        )
        costs = np.array(
            list(shipments.values_list("unit_cost", flat=True)), dtype=float
        )
        quantities = np.array(
            list(shipments.values_list("quantity", flat=True)), dtype=float
        )

        n_sim = 1000

        if len(delays) < 2:
            # Not enough data — assign worst-case
            self.disruption_probability = 0.5
            self.risk_rating = "HIGH"
            self.simulations_run = 0
            self.computation_ms = round((time.perf_counter() - t0) * 1000, 1)
            self.save(skip_hooks=True)
            return

        # ── Build empirical distributions ────────────────────────────
        delay_mean = float(np.mean(delays))
        delay_std = float(np.std(delays, ddof=1))
        damage_mean = float(np.mean(damages))
        damage_std = float(np.std(damages, ddof=1))
        avg_shipment_value = float(np.mean(costs * quantities))

        # ── Monte Carlo simulation ───────────────────────────────────
        sim_delays = np.maximum(
            np.random.normal(delay_mean, max(delay_std, 0.5), size=n_sim), 0
        )
        sim_damages = np.clip(
            np.random.normal(damage_mean, max(damage_std, 0.001), size=n_sim),
            0, 1,
        )

        # Disruption = delay > 5 days
        disruptions = sim_delays > 5
        disruption_prob = float(np.mean(disruptions))

        # Cost impact per scenario
        delay_penalty = sim_delays * avg_shipment_value * 0.002  # 0.2% per delay day
        damage_loss = sim_damages * avg_shipment_value
        total_loss = delay_penalty + damage_loss

        expected_loss = float(np.mean(total_loss))
        var_95 = float(np.percentile(total_loss, 95))

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # ── Persist ──────────────────────────────────────────────────
        self.disruption_probability = round(disruption_prob, 4)
        self.expected_loss_eur = round(expected_loss, 2)
        self.var_95_eur = round(var_95, 2)
        self.avg_delay_simulated = round(float(np.mean(sim_delays)), 2)
        self.risk_rating = _classify_risk(disruption_prob)
        self.simulations_run = n_sim
        self.computation_ms = round(elapsed_ms, 1)
        self.save(skip_hooks=True)

        # Small sleep to guarantee visible parallel vs. sequential difference
        time.sleep(0.08)

        # ── Log ──────────────────────────────────────────────────────
        emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(
            self.risk_rating, "⚪"
        )
        logger.add_heading(
            f"{emoji} {self.supplier.name} → {self.warehouse.name}", level=3
        )
        logger.add_table(
            headers=["Metric", "Value"],
            rows=[
                ["Disruption probability", f"{self.disruption_probability:.1%}"],
                ["Expected loss", f"€{self.expected_loss_eur:,.2f}"],
                ["VaR (95%)", f"€{self.var_95_eur:,.2f}"],
                ["Avg simulated delay", f"{self.avg_delay_simulated:.1f} d"],
                ["Risk rating", f"**{self.risk_rating}**"],
                ["Simulations", f"{self.simulations_run:,}"],
                ["Computation", f"{self.computation_ms:.0f} ms"],
            ],
        )
        logger.log()
