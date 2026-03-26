#!/usr/bin/env python3
"""
NovaTrans Supply Chain Workshop — Test Data Generator
=====================================================

Generates four CSV files that workshop participants upload into LEX:

  TestData/warehouses.csv          —   8 global distribution hubs
  TestData/product_categories.csv  —  12 product lines
  TestData/suppliers.csv           —  20 international suppliers
  TestData/shipment_history.csv    — ~2 300 monthly shipment records (Jan–Dec 2024)

Run once from the Workshop directory:

    python generate_test_data.py
"""

import csv
import os
import random
from datetime import date, timedelta

random.seed(42)  # reproducible data

OUT_DIR = os.path.join(os.path.dirname(__file__), "TestData")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── Warehouses ───────────────────────────────────────────────────────────────

WAREHOUSES = [
    ("Frankfurt Hub",   "EMEA",     "Germany",              50000, 125000.00, 50.1109,   8.6821),
    ("Shanghai Hub",    "APAC",     "China",                75000,  95000.00, 31.2304, 121.4737),
    ("Los Angeles Hub", "AMERICAS", "United States",        60000, 155000.00, 33.9425,-118.4081),
    ("São Paulo Hub",   "AMERICAS", "Brazil",               45000,  85000.00,-23.5505, -46.6333),
    ("Dubai Hub",       "MEA",      "United Arab Emirates",  55000, 110000.00, 25.2048,  55.2708),
    ("Mumbai Hub",      "APAC",     "India",                40000,  72000.00, 19.0760,  72.8777),
    ("Singapore Hub",   "APAC",     "Singapore",            65000, 135000.00,  1.3521, 103.8198),
    ("Rotterdam Hub",   "EMEA",     "Netherlands",          70000, 140000.00, 51.9244,   4.4777),
]

WH_HEADERS = ["name", "region", "country", "capacity_units",
              "operating_cost_monthly", "latitude", "longitude"]

# ─── Product Categories ──────────────────────────────────────────────────────

PRODUCTS = [
    ("Electronics",       "ELEC", 2.5,  0.015,  450.00,    0, ""),
    ("Pharmaceuticals",   "PHAR", 0.8,  0.005, 1200.00,  365, "6.1"),
    ("Automotive Parts",  "AUTO", 8.5,  0.045,  180.00,    0, ""),
    ("Textiles",          "TEXT", 1.2,  0.025,   35.00,    0, ""),
    ("Food & Beverage",   "FOOD", 3.0,  0.008,   12.00,   90, ""),
    ("Chemicals",         "CHEM",15.0,  0.020,   95.00,  730, "3"),
    ("Machinery",         "MACH",120.0, 0.350, 5500.00,    0, ""),
    ("Consumer Goods",    "CONS", 1.5,  0.012,   28.00,    0, ""),
    ("Raw Materials",     "RAWM",50.0,  0.100,  200.00,    0, ""),
    ("Luxury Goods",      "LUXE", 0.5,  0.003, 2800.00,    0, ""),
    ("Building Materials","BLDG",25.0,  0.080,   45.00,    0, ""),
    ("Agricultural",      "AGRI",20.0,  0.060,   18.00,  180, ""),
]

PROD_HEADERS = ["name", "sku_prefix", "weight_kg", "volume_m3",
                "unit_value", "shelf_life_days", "hazmat_class"]

# ─── Suppliers ────────────────────────────────────────────────────────────────

SUPPLIERS = [
    ("TechSource GmbH",         "Germany",              7, 0.95, 500000,  100),
    ("SinoLogistics Co.",        "China",               21, 0.88,1200000,  500),
    ("Pacific Trade Corp",       "United States",        5, 0.97, 350000,   50),
    ("Andean Exports SA",        "Brazil",              18, 0.82, 280000,  200),
    ("Gulf Dynamics LLC",        "United Arab Emirates", 10, 0.91, 420000,  150),
    ("Tata Supply Chain",        "India",               14, 0.86, 900000,  300),
    ("MarinaPort Pte",           "Singapore",            8, 0.94, 600000,  100),
    ("EuroFreight BV",           "Netherlands",          6, 0.96, 550000,   75),
    ("Sakura Industries",        "Japan",               12, 0.93, 450000,  120),
    ("Nordic Materials AB",      "Sweden",               9, 0.92, 320000,   80),
    ("Mediterranean Trading",    "Italy",               11, 0.89, 380000,  110),
    ("Atlas Logistics",          "Turkey",              15, 0.84, 520000,  250),
    ("CapeTown Distributors",    "South Africa",        20, 0.80, 240000,  300),
    ("Mapleleaf Supply",         "Canada",               6, 0.95, 400000,   60),
    ("Oceania Freight",          "Australia",           16, 0.87, 310000,  150),
    ("Andean Mining Corp",       "Chile",               22, 0.79, 200000,  400),
    ("Baltic Shipping OÜ",       "Estonia",             13, 0.85, 270000,  130),
    ("Rhine Chemical AG",        "Germany",              8, 0.93, 480000,   90),
    ("Dragon Electronics",       "China",               19, 0.90, 850000,  400),
    ("Panama Canal Trade",       "Panama",              17, 0.83, 350000,  200),
]

SUP_HEADERS = ["name", "country", "lead_time_days", "reliability_score",
               "annual_capacity", "min_order_qty"]

# ─── Product → typical supplier affinity (weighted random) ───────────────────

PRODUCT_SUPPLIER_AFFINITY = {
    "Electronics":       ["TechSource GmbH", "Dragon Electronics", "Sakura Industries", "SinoLogistics Co."],
    "Pharmaceuticals":   ["Rhine Chemical AG", "TechSource GmbH", "EuroFreight BV", "Tata Supply Chain"],
    "Automotive Parts":  ["Sakura Industries", "TechSource GmbH", "Pacific Trade Corp", "SinoLogistics Co."],
    "Textiles":          ["Tata Supply Chain", "SinoLogistics Co.", "Andean Exports SA", "Mediterranean Trading"],
    "Food & Beverage":   ["Mapleleaf Supply", "Andean Exports SA", "Mediterranean Trading", "Oceania Freight"],
    "Chemicals":         ["Rhine Chemical AG", "Gulf Dynamics LLC", "Baltic Shipping OÜ", "Atlas Logistics"],
    "Machinery":         ["TechSource GmbH", "Sakura Industries", "Pacific Trade Corp", "Nordic Materials AB"],
    "Consumer Goods":    ["SinoLogistics Co.", "MarinaPort Pte", "EuroFreight BV", "Pacific Trade Corp"],
    "Raw Materials":     ["Andean Mining Corp", "CapeTown Distributors", "Atlas Logistics", "Oceania Freight"],
    "Luxury Goods":      ["Mediterranean Trading", "EuroFreight BV", "MarinaPort Pte", "Sakura Industries"],
    "Building Materials": ["Atlas Logistics", "Andean Mining Corp", "CapeTown Distributors", "Baltic Shipping OÜ"],
    "Agricultural":      ["Andean Exports SA", "Mapleleaf Supply", "Oceania Freight", "Panama Canal Trade"],
}

# ─── Quantity ranges by product (reflects real volume differences) ────────────

PRODUCT_QTY_RANGE = {
    "Electronics":       (80,  600),
    "Pharmaceuticals":   (200, 1500),
    "Automotive Parts":  (50,  400),
    "Textiles":          (500, 3000),
    "Food & Beverage":   (1000,8000),
    "Chemicals":         (100, 800),
    "Machinery":         (5,   40),
    "Consumer Goods":    (300, 2500),
    "Raw Materials":     (200, 1200),
    "Luxury Goods":      (10,  80),
    "Building Materials": (150, 900),
    "Agricultural":      (500, 4000),
}

# ─── Seasonality multipliers (some products spike in certain months) ─────────

SEASONALITY = {
    "Electronics":       [0.8, 0.7, 0.9, 1.0, 1.0, 1.1, 1.0, 1.0, 1.2, 1.3, 1.5, 1.8],
    "Food & Beverage":   [1.0, 1.0, 1.1, 1.2, 1.3, 1.4, 1.4, 1.3, 1.2, 1.1, 1.2, 1.5],
    "Agricultural":      [0.6, 0.7, 1.0, 1.3, 1.5, 1.4, 1.2, 1.0, 1.3, 1.5, 0.9, 0.6],
    "Textiles":          [1.2, 1.0, 1.1, 1.3, 1.0, 0.8, 0.7, 0.9, 1.3, 1.4, 1.5, 1.6],
    "Building Materials": [0.5, 0.6, 1.0, 1.3, 1.5, 1.5, 1.4, 1.3, 1.2, 1.0, 0.7, 0.5],
}

# ─── Supplier reliability → delay distribution ──────────────────────────────

def _supplier_reliability(name):
    for s in SUPPLIERS:
        if s[0] == name:
            return s[3]
    return 0.85


def _generate_delay(supplier_name, product_name):
    """More unreliable suppliers → higher chance of delays."""
    reliability = _supplier_reliability(supplier_name)
    if random.random() < reliability:
        return 0  # on-time
    severity = 1 - reliability  # 0.05–0.21
    max_delay = int(severity * 30) + 2
    return random.randint(1, max_delay)


def _generate_damage_rate(product_name, delay_days):
    """Fragile / perishable goods have higher base damage. Delays worsen it."""
    base = {
        "Electronics": 0.008, "Pharmaceuticals": 0.003, "Luxury Goods": 0.005,
        "Food & Beverage": 0.012, "Chemicals": 0.006, "Agricultural": 0.010,
    }.get(product_name, 0.002)
    # delays increase damage
    return round(min(base + delay_days * 0.002, 0.15), 4)


# ─── Generate shipment history ───────────────────────────────────────────────

def generate_shipments():
    rows = []
    order_id = 10000
    start = date(2024, 1, 1)

    for month_idx in range(12):
        month_start = date(2024, month_idx + 1, 1)
        if month_idx < 11:
            month_end = date(2024, month_idx + 2, 1) - timedelta(days=1)
        else:
            month_end = date(2024, 12, 31)
        days_in_month = (month_end - month_start).days + 1

        for wh_name, wh_region, *_ in WAREHOUSES:
            for prod_name, _, _, _, unit_val, *_ in PRODUCTS:
                # 2 shipments per warehouse-product-month (with some randomness)
                n_shipments = random.choices([1, 2, 3], weights=[0.2, 0.6, 0.2])[0]

                qmin, qmax = PRODUCT_QTY_RANGE[prod_name]
                season_mult = SEASONALITY.get(prod_name, [1.0]*12)[month_idx]
                suppliers = PRODUCT_SUPPLIER_AFFINITY[prod_name]

                for _ in range(n_shipments):
                    ship_day = random.randint(0, days_in_month - 1)
                    ship_date = month_start + timedelta(days=ship_day)
                    supplier = random.choice(suppliers)
                    qty = int(random.randint(qmin, qmax) * season_mult)
                    # unit cost varies ±15% around base
                    cost = round(unit_val * random.uniform(0.85, 1.15), 2)
                    delay = _generate_delay(supplier, prod_name)
                    damage = _generate_damage_rate(prod_name, delay)

                    order_id += 1
                    rows.append([
                        wh_name, prod_name, supplier, ship_date.isoformat(),
                        qty, cost, delay, damage, f"ORD-{order_id}"
                    ])

    random.shuffle(rows)  # realistic: not perfectly ordered
    return rows


SHIP_HEADERS = ["warehouse", "product_category", "supplier", "ship_date",
                "quantity", "unit_cost", "delay_days", "damage_rate", "order_id"]


# ─── Write helpers ────────────────────────────────────────────────────────────

def write_csv(filename, headers, rows):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  ✓ {filename:35s}  {len(rows):>5,} rows")


def main():
    print("NovaTrans Workshop — Generating test data …\n")

    write_csv("warehouses.csv", WH_HEADERS, WAREHOUSES)
    write_csv("product_categories.csv", PROD_HEADERS, PRODUCTS)
    write_csv("suppliers.csv", SUP_HEADERS, SUPPLIERS)
    shipments = generate_shipments()
    write_csv("shipment_history.csv", SHIP_HEADERS, shipments)

    print(f"\n✅  All files written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
