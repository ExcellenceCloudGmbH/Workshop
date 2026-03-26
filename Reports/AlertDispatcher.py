"""
Step 4c — Alert Dispatcher  (FireAndForget)
===========================================

A lightweight **CalculationModel** that simulates sending email / Slack
alerts for every high-risk supplier–warehouse combination.

It is invoked by the ``SupplyChainDashboard`` inside a
**FireAndForget** context.  The dashboard does NOT wait for the alerts
to finish — it logs immediately and moves on.

What it demonstrates
--------------------
* ``FireAndForget`` — non-blocking asynchronous dispatch
* The calculation runs in a Celery worker **after** the parent has
  already returned
* Compare the dashboard log:  the ``⏱️ FireAndForget returned in
  < 0.1 s`` message appears long before the alerts actually finish
"""

import time

from django.db import models
from lex.core.models.CalculationModel import CalculationModel
from lex.audit_logging.handlers.LexLogger import LexLogger
from lex.lex_app.celery_tasks import lex_shared_task

from Workshop.Input.Warehouse import Warehouse
from Workshop.Input.Supplier import Supplier


logger = LexLogger()


class AlertDispatcher(CalculationModel):

    id = models.AutoField(primary_key=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    risk_rating = models.CharField(max_length=10)
    alert_channel = models.CharField(
        max_length=20, default="email",
        choices=[("email", "E-Mail"), ("slack", "Slack"), ("both", "Both")],
    )

    # ── Outputs ──────────────────────────────────────────────────────
    alert_sent = models.BooleanField(default=False)
    alert_message = models.TextField(blank=True, default="")
    dispatch_seconds = models.FloatField(default=0)

    def __str__(self):
        status = "✅" if self.alert_sent else "⏳"
        return f"{status} Alert: {self.supplier} → {self.warehouse} [{self.risk_rating}]"

    @lex_shared_task
    def calculate(self):
        """
        Simulate sending an alert notification.

        In production this would call an SMTP server or Slack webhook.
        We simulate network latency with a 2-second sleep to make the
        FireAndForget behaviour clearly visible.
        """
        t0 = time.perf_counter()

        # Simulate composing the alert
        message = (
            f"⚠️ SUPPLY CHAIN ALERT\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Supplier:  {self.supplier.name}\n"
            f"Warehouse: {self.warehouse.name}\n"
            f"Risk:      {self.risk_rating}\n"
            f"Channel:   {self.alert_channel}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Action required: Review supplier contract and contingency plan."
        )

        # Simulate network I/O (email send / API call)
        time.sleep(2.0)

        elapsed = time.perf_counter() - t0

        self.alert_sent = True
        self.alert_message = message
        self.dispatch_seconds = round(elapsed, 2)
        self.save(skip_hooks=True)

        logger.add_heading(f"📧 Alert Sent — {self.supplier.name}", level=3)
        logger.add_text(f"**To:** {self.warehouse.name} ops team")
        logger.add_text(f"**Risk:** {self.risk_rating}")
        logger.add_text(f"**Channel:** {self.alert_channel}")
        logger.add_text(f"**Delivery time:** {self.dispatch_seconds:.1f} s")
        logger.add_text(
            "> This ran inside **FireAndForget** — the dashboard already "
            "returned while this alert was being sent."
        )
        logger.log()
