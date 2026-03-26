# 🌐 NovaTrans Supply Chain Workshop

> **Learn LEX's parallelisation features by building a real supply chain
> risk analysis system — from CSV upload to Monte Carlo simulation.**

---

## The Story

**NovaTrans** is a global logistics company operating 8 distribution hubs
across 4 continents.  They move 12 product categories from 20 international
suppliers.  Every month the operations team needs to:

1. **Upload** fresh shipment data (2 300+ records)
2. **Analyse** inventory levels per warehouse
3. **Forecast** demand for every warehouse × product combination
4. **Score** supplier risk with Monte Carlo simulations
5. **Alert** stakeholders when risk thresholds are breached

The workshop builds this system step by step, each step introducing a
new LEX computation feature:

| Step | Feature | Model | Records | Time (est.) |
|------|---------|-------|---------|-------------|
| 0 | CSV Upload | `UploadWarehouses` … `UploadShipments` | 4 files | ~5 s |
| 1 | Sequential `CalculationModel` | `InventoryOptimizer` | 1 per warehouse | ~2 s each |
| 2 | Batch `CalculatedModelMixin` (sync) | `DemandForecast` | 96 | ~15 s |
| 3 | Batch + `parallelizable_fields` | `DemandForecastParallel` | 96 | ~2 s ⚡ |
| 4 | `WaitForTasks` + `FireAndForget` | `SupplyChainDashboard` | 160 + alerts | ~5 s |

---

## Project Structure

```
Workshop/
├── generate_test_data.py          # Creates the 4 CSV files
├── TestData/
│   ├── warehouses.csv             #   8 distribution hubs
│   ├── product_categories.csv     #  12 product lines
│   ├── suppliers.csv              #  20 international suppliers
│   └── shipment_history.csv       # ~2 300 shipment records (2024)
├── Input/                         # Dimension tables (LexModel)
│   ├── Warehouse.py
│   ├── ProductCategory.py
│   ├── Supplier.py
│   └── ShipmentRecord.py
├── Upload/                        # CSV ingest models (LexModel + @hook)
│   ├── UploadWarehouses.py
│   ├── UploadProducts.py
│   ├── UploadSuppliers.py
│   └── UploadShipments.py
└── Reports/                       # Calculation models
    ├── InventoryOptimizer.py      # Step 1 — CalculationModel (sequential)
    ├── DemandForecast.py          # Step 2 — CalculatedModelMixin (batch, sync)
    ├── DemandForecastParallel.py  # Step 3 — CalculatedModelMixin (batch, parallel)
    ├── SupplierRiskScore.py       # Step 4a — Monte Carlo (parallel sub-model)
    ├── SupplyChainDashboard.py    # Step 4b — Orchestrator (WaitForTasks + FireAndForget)
    └── AlertDispatcher.py         # Step 4c — Notifications (FireAndForget target)
```

---

## Quick Start

### 1. Generate test data

```bash
cd project_example
python Workshop/generate_test_data.py
```

### 2. Run migrations

```bash
lex makemigrations
lex migrate
```

### 3. Start the app

```bash
lex start
```

### 4. Upload data (in the UI)

Navigate to the **Workshop → Upload Data** section in the sidebar.
Create one record per upload model and attach the corresponding CSV
from `Workshop/TestData/`.  Upload in this order:

1. **UploadWarehouses** → `warehouses.csv`
2. **UploadProducts** → `product_categories.csv`
3. **UploadSuppliers** → `suppliers.csv`
4. **UploadShipments** → `shipment_history.csv`

### 5. Run calculations (Steps 1–4)

Follow the guided walkthrough in the [Workshop Documentation](../../docs/workshop/).

---

## What You'll Learn

### CalculationModel (Step 1)
A single model that computes results when you click **Calculate**.
See the state machine: `NOT_CALCULATED → IN_PROGRESS → SUCCESS`.

### CalculatedModelMixin (Step 2)
Generates records for every combination of `defining_fields` and
runs `calculate()` on each.  Synchronous — everything on one thread.

### parallelizable_fields (Step 3)
Add **two lines** to the Step 2 model — `parallelizable_fields` and
`@lex_shared_task` — and watch 96 calculations run in ~2 s instead
of ~15 s.

### WaitForTasks (Step 4)
Dispatch 160 Monte Carlo simulations to Celery workers and **block**
until every one finishes.  Use the results for aggregation.

### FireAndForget (Step 4)
Dispatch alert notifications and **return immediately** — the alerts
are sent in the background by Celery while the dashboard has already
finished.

---

## Prerequisites

- LEX development environment set up (`lex start` works)
- Redis running locally (for Celery parallelisation)
- `numpy` and `pandas` installed (both are LEX dependencies)

To enable Celery workers:

```bash
export CELERY_ACTIVE=true
lex celery worker --concurrency=4
```

Without Celery, all calculations fall back to synchronous execution.
Steps 2 and 3 will produce identical timing — the speedup only
appears with Celery workers running.
