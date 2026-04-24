"""
MRP Engine for SodhiCable MES
==============================
Material Requirements Planning with 7 lot-sizing methods.
Uses only sqlite3 and Python standard library.
"""

import sqlite3
import math
import random
from collections import defaultdict


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

def create_mrp_tables(conn):
    """Create the five MRP tables if they do not already exist."""
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mrp_items (
            item_id   TEXT PRIMARY KEY,
            name      TEXT NOT NULL,
            description TEXT DEFAULT '',
            level     INTEGER NOT NULL DEFAULT 0,
            item_type TEXT NOT NULL DEFAULT 'RM',
            lead_time INTEGER NOT NULL DEFAULT 1,
            lot_rule  TEXT NOT NULL DEFAULT 'L4L',
            lot_size  INTEGER NOT NULL DEFAULT 1,
            safety_stock INTEGER NOT NULL DEFAULT 0,
            on_hand   INTEGER NOT NULL DEFAULT 0,
            unit_cost REAL NOT NULL DEFAULT 0.0,
            setup_cost REAL NOT NULL DEFAULT 500.0,
            holding_cost REAL NOT NULL DEFAULT 2.0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mrp_bom (
            parent_id TEXT NOT NULL,
            child_id  TEXT NOT NULL,
            qty_per   REAL NOT NULL DEFAULT 1.0,
            scrap_rate REAL NOT NULL DEFAULT 0.0,
            PRIMARY KEY (parent_id, child_id),
            FOREIGN KEY (parent_id) REFERENCES mrp_items(item_id),
            FOREIGN KEY (child_id)  REFERENCES mrp_items(item_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mrp_demand (
            item_id  TEXT NOT NULL,
            week     INTEGER NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            source   TEXT NOT NULL DEFAULT 'MPS',
            PRIMARY KEY (item_id, week, source),
            FOREIGN KEY (item_id) REFERENCES mrp_items(item_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mrp_planned_orders (
            order_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id      TEXT NOT NULL,
            release_week INTEGER NOT NULL,
            receipt_week INTEGER NOT NULL,
            quantity     REAL NOT NULL DEFAULT 0,
            status       TEXT NOT NULL DEFAULT 'planned',
            FOREIGN KEY (item_id) REFERENCES mrp_items(item_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mrp_inventory_log (
            item_id            TEXT NOT NULL,
            week               INTEGER NOT NULL,
            gross_req          REAL NOT NULL DEFAULT 0,
            scheduled_receipts REAL NOT NULL DEFAULT 0,
            projected_oh       REAL NOT NULL DEFAULT 0,
            net_req            REAL NOT NULL DEFAULT 0,
            planned_receipt    REAL NOT NULL DEFAULT 0,
            planned_release    REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (item_id, week),
            FOREIGN KEY (item_id) REFERENCES mrp_items(item_id)
        )
    """)

    conn.commit()


# ---------------------------------------------------------------------------
# Seed data for SodhiCable
# ---------------------------------------------------------------------------

def populate_sodhicable_bom(conn):
    """Seed 31 items, BOM relationships, and MPS demand for 8 weeks."""
    cur = conn.cursor()

    # Clear existing data
    for tbl in ("mrp_inventory_log", "mrp_planned_orders",
                "mrp_demand", "mrp_bom", "mrp_items"):
        cur.execute(f"DELETE FROM {tbl}")

    # ---- Finished Goods (level 0) ----
    finished_goods = [
        ("FG-A1", "Power Cable A1",  "3-conductor 12AWG power cable",    0, "FG", 1, "L4L",  1,  5, 20, 12.50, 800.0, 3.0),
        ("FG-A2", "Power Cable A2",  "3-conductor 10AWG power cable",    0, "FG", 1, "FOQ", 50,  5, 15, 14.00, 800.0, 3.0),
        ("FG-B1", "Control Cable B1","7-conductor shielded control",     0, "FG", 1, "EOQ",  1, 10, 10, 18.00, 900.0, 2.5),
        ("FG-B2", "Control Cable B2","12-conductor shielded control",    0, "FG", 2, "POQ",  1, 10,  8, 22.00, 900.0, 2.5),
        ("FG-C1", "Data Cable C1",   "Cat6 data cable",                  0, "FG", 1, "SM",   1,  0, 25, 8.00,  600.0, 2.0),
        ("FG-C2", "Data Cable C2",   "Cat6A shielded data cable",        0, "FG", 1, "WW",   1,  0, 12, 11.00, 700.0, 2.0),
    ]

    # ---- Sub-assemblies (level 1) ----
    sub_assemblies = [
        ("SA-WIRE-CU",     "Copper Wire Assembly",   "Drawn and annealed Cu wire",    1, "SA", 2, "FOQ", 100, 20, 80, 5.00, 600.0, 1.5),
        ("SA-WIRE-CU-10",  "Cu Wire 10AWG Assembly", "10AWG drawn Cu wire",           1, "SA", 2, "FOQ", 100, 15, 60, 5.50, 600.0, 1.5),
        ("SA-INSUL-PVC",   "PVC Insulation Layer",   "Extruded PVC insulation",       1, "SA", 1, "L4L",   1, 10, 50, 2.00, 400.0, 1.0),
        ("SA-INSUL-XLPE",  "XLPE Insulation Layer",  "Cross-linked PE insulation",    1, "SA", 1, "L4L",   1, 10, 40, 3.00, 450.0, 1.2),
        ("SA-JACKET-PVC",  "PVC Jacket",             "Outer PVC jacket extrusion",    1, "SA", 1, "EOQ",   1,  5, 60, 1.50, 350.0, 0.8),
        ("SA-JACKET-LSZH", "LSZH Jacket",            "Low-smoke zero-halogen jacket", 1, "SA", 1, "EOQ",   1,  5, 30, 2.50, 400.0, 1.0),
        ("SA-SHIELD-FOIL", "Foil Shield Assembly",   "Aluminum foil shield layer",    1, "SA", 1, "L4L",   1,  5, 45, 1.80, 300.0, 0.9),
        ("SA-SHIELD-BRAID","Braid Shield Assembly",  "Copper braid shield layer",     1, "SA", 2, "FOQ",  50,  5, 35, 3.50, 500.0, 1.5),
        ("SA-TWIST-PAIR",  "Twisted Pair Assembly",  "Twisted pair formation",        1, "SA", 1, "L4L",   1,  0, 70, 1.20, 250.0, 0.6),
        ("SA-DRAIN-WIRE",  "Drain Wire Assembly",    "Tin-plated drain wire",         1, "SA", 1, "L4L",   1,  0, 55, 0.80, 200.0, 0.5),
    ]

    # ---- Raw Materials (level 2) ----
    raw_materials = [
        ("RM-CU-ROD",    "Copper Rod 8mm",        "Oxygen-free Cu rod",        2, "RM", 3, "FOQ", 200, 50, 500, 3.00, 1000.0, 1.0),
        ("RM-CU-ROD-10", "Copper Rod 10mm",       "Cu rod for 10AWG",          2, "RM", 3, "FOQ", 200, 40, 400, 3.20, 1000.0, 1.0),
        ("RM-PVC-COMP",  "PVC Compound",          "Insulation grade PVC",      2, "RM", 2, "EOQ",   1, 30, 300, 1.00, 500.0,  0.5),
        ("RM-XLPE-COMP", "XLPE Compound",         "Cross-linkable PE pellets", 2, "RM", 2, "EOQ",   1, 30, 200, 1.80, 550.0,  0.6),
        ("RM-PVC-JACK",  "PVC Jacket Compound",   "Jacket grade PVC",          2, "RM", 2, "L4L",   1, 20, 250, 0.90, 400.0,  0.4),
        ("RM-LSZH-COMP", "LSZH Compound",         "Low-smoke compound",        2, "RM", 3, "FOQ", 150, 20, 180, 2.00, 600.0,  0.7),
        ("RM-AL-FOIL",   "Aluminum Foil",         "Shielding foil tape",       2, "RM", 2, "L4L",   1, 15, 350, 0.60, 250.0,  0.3),
        ("RM-CU-BRAID",  "Copper Braid Wire",     "Tinned Cu braid wire",      2, "RM", 3, "FOQ", 100, 20, 250, 2.20, 700.0,  0.8),
        ("RM-TIN-WIRE",  "Tin-plated Wire",       "Drain wire stock",          2, "RM", 2, "L4L",   1, 10, 200, 0.50, 200.0,  0.3),
        ("RM-COLOR-MB",  "Color Masterbatch",     "Color concentrate pellets", 2, "RM", 1, "L4L",   1,  5, 150, 0.30, 100.0,  0.2),
        ("RM-MARKER-INK","Marking Ink",           "Surface print ink",         2, "RM", 1, "FOQ",  50,  5, 100, 0.20, 80.0,   0.1),
        ("RM-FILLER",    "Cable Filler",          "Polypropylene filler",      2, "RM", 1, "L4L",   1,  5, 120, 0.15, 60.0,   0.1),
        ("RM-TAPE",      "Binding Tape",          "Polyester binding tape",    2, "RM", 1, "L4L",   1,  5,  90, 0.10, 50.0,   0.1),
        ("RM-RIPCORD",   "Ripcord",               "Nylon ripcord",             2, "RM", 1, "L4L",   1,  0, 200, 0.05, 30.0,   0.05),
        ("RM-NYLON",     "Nylon Compound",        "PA-6 nylon pellets",        2, "RM", 2, "EOQ",   1, 10, 160, 1.50, 500.0,  0.5),
    ]

    all_items = finished_goods + sub_assemblies + raw_materials
    cur.executemany(
        "INSERT INTO mrp_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        all_items,
    )

    # ---- BOM relationships ----
    bom_links = [
        # FG-A1 -> sub-assemblies
        ("FG-A1", "SA-WIRE-CU",     3.0, 0.02),
        ("FG-A1", "SA-INSUL-PVC",   3.0, 0.01),
        ("FG-A1", "SA-JACKET-PVC",  1.0, 0.01),

        # FG-A2 -> sub-assemblies
        ("FG-A2", "SA-WIRE-CU-10",  3.0, 0.02),
        ("FG-A2", "SA-INSUL-PVC",   3.0, 0.01),
        ("FG-A2", "SA-JACKET-PVC",  1.0, 0.01),

        # FG-B1 -> sub-assemblies
        ("FG-B1", "SA-WIRE-CU",     7.0, 0.02),
        ("FG-B1", "SA-INSUL-XLPE",  7.0, 0.01),
        ("FG-B1", "SA-SHIELD-FOIL", 1.0, 0.005),
        ("FG-B1", "SA-DRAIN-WIRE",  1.0, 0.0),
        ("FG-B1", "SA-JACKET-LSZH", 1.0, 0.01),

        # FG-B2 -> sub-assemblies
        ("FG-B2", "SA-WIRE-CU",     12.0, 0.03),
        ("FG-B2", "SA-INSUL-XLPE",  12.0, 0.01),
        ("FG-B2", "SA-SHIELD-BRAID",1.0,  0.005),
        ("FG-B2", "SA-DRAIN-WIRE",  1.0,  0.0),
        ("FG-B2", "SA-JACKET-LSZH", 1.0,  0.01),

        # FG-C1 -> sub-assemblies
        ("FG-C1", "SA-TWIST-PAIR",  4.0, 0.01),
        ("FG-C1", "SA-INSUL-PVC",   8.0, 0.01),
        ("FG-C1", "SA-JACKET-PVC",  1.0, 0.01),

        # FG-C2 -> sub-assemblies
        ("FG-C2", "SA-TWIST-PAIR",  4.0, 0.01),
        ("FG-C2", "SA-INSUL-PVC",   8.0, 0.01),
        ("FG-C2", "SA-SHIELD-FOIL", 1.0, 0.005),
        ("FG-C2", "SA-DRAIN-WIRE",  1.0, 0.0),
        ("FG-C2", "SA-JACKET-LSZH", 1.0, 0.01),

        # SA -> Raw Materials
        ("SA-WIRE-CU",     "RM-CU-ROD",    1.1, 0.03),
        ("SA-WIRE-CU",     "RM-COLOR-MB",  0.05, 0.0),
        ("SA-WIRE-CU-10",  "RM-CU-ROD-10", 1.2, 0.03),
        ("SA-WIRE-CU-10",  "RM-COLOR-MB",  0.05, 0.0),
        ("SA-INSUL-PVC",   "RM-PVC-COMP",  1.5, 0.02),
        ("SA-INSUL-PVC",   "RM-COLOR-MB",  0.08, 0.0),
        ("SA-INSUL-XLPE",  "RM-XLPE-COMP", 1.6, 0.02),
        ("SA-INSUL-XLPE",  "RM-COLOR-MB",  0.08, 0.0),
        ("SA-JACKET-PVC",  "RM-PVC-JACK",  2.0, 0.02),
        ("SA-JACKET-PVC",  "RM-FILLER",    0.3, 0.0),
        ("SA-JACKET-PVC",  "RM-RIPCORD",   0.1, 0.0),
        ("SA-JACKET-PVC",  "RM-MARKER-INK",0.02,0.0),
        ("SA-JACKET-LSZH", "RM-LSZH-COMP", 2.2, 0.02),
        ("SA-JACKET-LSZH", "RM-FILLER",    0.3, 0.0),
        ("SA-JACKET-LSZH", "RM-RIPCORD",   0.1, 0.0),
        ("SA-JACKET-LSZH", "RM-MARKER-INK",0.02,0.0),
        ("SA-SHIELD-FOIL", "RM-AL-FOIL",   1.2, 0.01),
        ("SA-SHIELD-FOIL", "RM-TAPE",      0.2, 0.0),
        ("SA-SHIELD-BRAID","RM-CU-BRAID",  1.5, 0.02),
        ("SA-SHIELD-BRAID","RM-TAPE",      0.15,0.0),
        ("SA-TWIST-PAIR",  "RM-CU-ROD",    0.5, 0.02),
        ("SA-TWIST-PAIR",  "RM-NYLON",     0.1, 0.0),
        ("SA-DRAIN-WIRE",  "RM-TIN-WIRE",  1.0, 0.01),
    ]

    cur.executemany(
        "INSERT INTO mrp_bom VALUES (?,?,?,?)",
        bom_links,
    )

    # ---- MPS Demand (8 weeks) ----
    mps_demand = [
        # FG-A1
        ("FG-A1", 1, 10, "MPS"), ("FG-A1", 2, 15, "MPS"),
        ("FG-A1", 3, 12, "MPS"), ("FG-A1", 4, 18, "MPS"),
        ("FG-A1", 5, 10, "MPS"), ("FG-A1", 6, 20, "MPS"),
        ("FG-A1", 7, 14, "MPS"), ("FG-A1", 8, 16, "MPS"),
        # FG-A2
        ("FG-A2", 1,  8, "MPS"), ("FG-A2", 2, 12, "MPS"),
        ("FG-A2", 3, 10, "MPS"), ("FG-A2", 4, 14, "MPS"),
        ("FG-A2", 5,  8, "MPS"), ("FG-A2", 6, 16, "MPS"),
        ("FG-A2", 7, 10, "MPS"), ("FG-A2", 8, 12, "MPS"),
        # FG-B1
        ("FG-B1", 1,  5, "MPS"), ("FG-B1", 2,  8, "MPS"),
        ("FG-B1", 3,  6, "MPS"), ("FG-B1", 4, 10, "MPS"),
        ("FG-B1", 5,  7, "MPS"), ("FG-B1", 6,  9, "MPS"),
        ("FG-B1", 7,  5, "MPS"), ("FG-B1", 8,  8, "MPS"),
        # FG-B2
        ("FG-B2", 1,  3, "MPS"), ("FG-B2", 2,  5, "MPS"),
        ("FG-B2", 3,  4, "MPS"), ("FG-B2", 4,  6, "MPS"),
        ("FG-B2", 5,  3, "MPS"), ("FG-B2", 6,  7, "MPS"),
        ("FG-B2", 7,  4, "MPS"), ("FG-B2", 8,  5, "MPS"),
        # FG-C1
        ("FG-C1", 1, 15, "MPS"), ("FG-C1", 2, 20, "MPS"),
        ("FG-C1", 3, 18, "MPS"), ("FG-C1", 4, 22, "MPS"),
        ("FG-C1", 5, 15, "MPS"), ("FG-C1", 6, 25, "MPS"),
        ("FG-C1", 7, 18, "MPS"), ("FG-C1", 8, 20, "MPS"),
        # FG-C2
        ("FG-C2", 1,  6, "MPS"), ("FG-C2", 2, 10, "MPS"),
        ("FG-C2", 3,  8, "MPS"), ("FG-C2", 4, 12, "MPS"),
        ("FG-C2", 5,  7, "MPS"), ("FG-C2", 6, 14, "MPS"),
        ("FG-C2", 7,  9, "MPS"), ("FG-C2", 8, 11, "MPS"),
    ]

    cur.executemany(
        "INSERT INTO mrp_demand VALUES (?,?,?,?)",
        mps_demand,
    )

    conn.commit()
    return len(all_items), len(bom_links), len(mps_demand)


# ---------------------------------------------------------------------------
# BOM explosion
# ---------------------------------------------------------------------------

def explode_bom(conn, item_id, qty_needed, level=0, include_scrap=True):
    """
    Recursively explode BOM for *item_id*.

    Returns dict  {item_id: total_qty}  with scrap-adjusted quantities.
    """
    cur = conn.cursor()
    result = defaultdict(float)
    result[item_id] += qty_needed

    cur.execute(
        "SELECT child_id, qty_per, scrap_rate FROM mrp_bom WHERE parent_id = ?",
        (item_id,),
    )
    children = cur.fetchall()

    for child_id, qty_per, scrap_rate in children:
        child_qty = qty_needed * qty_per
        if include_scrap:
            child_qty *= (1.0 + scrap_rate)
        child_result = explode_bom(conn, child_id, child_qty,
                                   level + 1, include_scrap)
        for k, v in child_result.items():
            result[k] += v

    return dict(result)


def get_bom_tree(conn, item_id, level=0):
    """
    Return a flat list of dicts representing the indented BOM tree.

    Each dict: {item_id, name, level, qty_per, indent}
    """
    cur = conn.cursor()
    cur.execute("SELECT name FROM mrp_items WHERE item_id = ?", (item_id,))
    row = cur.fetchone()
    name = row[0] if row else item_id

    indent = "  " * level + ("|-- " if level > 0 else "")
    tree = [{
        "item_id": item_id,
        "name": name,
        "level": level,
        "qty_per": 1.0 if level == 0 else None,
        "indent": indent,
    }]

    cur.execute(
        "SELECT child_id, qty_per FROM mrp_bom WHERE parent_id = ? ORDER BY child_id",
        (item_id,),
    )
    children = cur.fetchall()

    for child_id, qty_per in children:
        child_tree = get_bom_tree(conn, child_id, level + 1)
        # patch qty_per onto root of child subtree
        if child_tree:
            child_tree[0]["qty_per"] = qty_per
        tree.extend(child_tree)

    return tree


# ---------------------------------------------------------------------------
# Inventory helpers
# ---------------------------------------------------------------------------

_ORIGINAL_ON_HAND = {}  # cache for reset


def reset_inventory(conn):
    """Reset on_hand quantities to the values inserted by populate_sodhicable_bom."""
    global _ORIGINAL_ON_HAND
    cur = conn.cursor()
    if not _ORIGINAL_ON_HAND:
        cur.execute("SELECT item_id, on_hand FROM mrp_items")
        _ORIGINAL_ON_HAND = {r[0]: r[1] for r in cur.fetchall()}

    for item_id, oh in _ORIGINAL_ON_HAND.items():
        cur.execute("UPDATE mrp_items SET on_hand = ? WHERE item_id = ?",
                     (oh, item_id))
    # Clear planned orders and inventory log
    cur.execute("DELETE FROM mrp_planned_orders")
    cur.execute("DELETE FROM mrp_inventory_log")
    conn.commit()


# ---------------------------------------------------------------------------
# Gross requirements
# ---------------------------------------------------------------------------

def get_gross_requirements(conn, item_id, level):
    """
    Return {week: qty} of gross requirements for *item_id*.

    Level 0 items read directly from mrp_demand.
    Level 1+ items derive requirements from parent planned release orders.
    """
    cur = conn.cursor()
    gross = defaultdict(float)

    if level == 0:
        cur.execute(
            "SELECT week, SUM(quantity) FROM mrp_demand "
            "WHERE item_id = ? GROUP BY week ORDER BY week",
            (item_id,),
        )
        for week, qty in cur.fetchall():
            gross[week] += qty
    else:
        # Find all parents that use this item
        cur.execute(
            "SELECT parent_id, qty_per, scrap_rate FROM mrp_bom WHERE child_id = ?",
            (item_id,),
        )
        parents = cur.fetchall()
        for parent_id, qty_per, scrap_rate in parents:
            # Parent planned orders released in week W generate gross
            # requirements for child in week W
            cur.execute(
                "SELECT release_week, quantity FROM mrp_planned_orders "
                "WHERE item_id = ? AND status = 'planned'",
                (parent_id,),
            )
            for week, parent_qty in cur.fetchall():
                child_qty = parent_qty * qty_per * (1.0 + scrap_rate)
                gross[week] += child_qty

    return dict(gross)


# ---------------------------------------------------------------------------
# Lot-sizing methods
# ---------------------------------------------------------------------------

def apply_lot_rule(net_need, lot_rule, lot_size, future_demands=None,
                   setup_cost=500.0, holding_cost=2.0, production_rate=0.0):
    """
    Apply one of 7 lot-sizing rules and return an integer order quantity.

    Parameters
    ----------
    net_need : float
        Net requirement for the current period.
    lot_rule : str
        One of L4L, FOQ, EOQ, EPQ, POQ, SM, WW, LUC, PPB.
    lot_size : int
        Fixed lot size (used by FOQ).
    future_demands : list of float or None
        Demands for current + future periods (used by SM, WW, POQ).
    setup_cost : float
        Fixed ordering / setup cost  (S).
    holding_cost : float
        Holding cost per unit per period  (H).
    production_rate : float
        Production rate per period (used by EPQ).

    Returns
    -------
    int
        Order quantity (>= net_need).
    """
    if net_need <= 0:
        return 0

    rule = lot_rule.upper().strip()

    # --- Lot-for-Lot ---
    if rule == "L4L":
        return int(math.ceil(net_need))

    # --- Fixed Order Quantity ---
    if rule == "FOQ":
        if lot_size <= 0:
            lot_size = 1
        qty = lot_size
        while qty < net_need:
            qty += lot_size
        return int(qty)

    # --- Economic Order Quantity ---
    if rule == "EOQ":
        # D = annualized demand estimate (assume 52 weeks)
        if future_demands and len(future_demands) > 0:
            avg_week = sum(future_demands) / len(future_demands)
        else:
            avg_week = net_need
        D = avg_week * 52.0
        if D <= 0 or holding_cost <= 0:
            return int(math.ceil(net_need))
        eoq = math.sqrt(2.0 * D * setup_cost / holding_cost)
        qty = max(int(math.ceil(eoq)), int(math.ceil(net_need)))
        return qty

    # --- Economic Production Quantity ---
    if rule == "EPQ":
        if future_demands and len(future_demands) > 0:
            avg_week = sum(future_demands) / len(future_demands)
        else:
            avg_week = net_need
        D = avg_week * 52.0
        d = avg_week  # demand rate per period
        p = production_rate if production_rate > 0 else d * 2.0
        if D <= 0 or holding_cost <= 0 or p <= d:
            return int(math.ceil(net_need))
        epq = math.sqrt(2.0 * D * setup_cost / (holding_cost * (1.0 - d / p)))
        qty = max(int(math.ceil(epq)), int(math.ceil(net_need)))
        return qty

    # --- Period Order Quantity ---
    if rule == "POQ":
        # Convert EOQ into number of periods, then aggregate that many periods
        if future_demands and len(future_demands) > 0:
            avg_week = sum(future_demands) / len(future_demands)
        else:
            avg_week = net_need
        D = avg_week * 52.0
        if D <= 0 or holding_cost <= 0:
            return int(math.ceil(net_need))
        eoq = math.sqrt(2.0 * D * setup_cost / holding_cost)
        periods = max(1, int(round(eoq / avg_week))) if avg_week > 0 else 1
        if future_demands and len(future_demands) > 0:
            qty = sum(future_demands[:periods])
        else:
            qty = net_need
        return max(int(math.ceil(qty)), int(math.ceil(net_need)))

    # --- Silver-Meal heuristic ---
    if rule == "SM":
        if not future_demands or len(future_demands) == 0:
            return int(math.ceil(net_need))

        best_T = 1
        best_avg = float("inf")
        cumulative_qty = 0.0

        for T in range(1, len(future_demands) + 1):
            cumulative_qty += future_demands[T - 1]
            # Holding cost for demands in periods 1..T carried from order period
            hold = 0.0
            for i in range(T):
                hold += holding_cost * i * future_demands[i]
            avg_cost = (setup_cost + hold) / T

            if T > 1 and avg_cost > best_avg:
                # Average cost increasing -> stop at previous T
                break
            best_avg = avg_cost
            best_T = T

        qty = sum(future_demands[:best_T])
        return max(int(math.ceil(qty)), int(math.ceil(net_need)))

    # --- Least Unit Cost (LUC) ---
    if rule == "LUC":
        if not future_demands or len(future_demands) == 0:
            return int(math.ceil(net_need))

        best_T = 1
        best_unit_cost = float("inf")

        for T in range(1, len(future_demands) + 1):
            cumulative_qty = sum(future_demands[:T])
            if cumulative_qty <= 0:
                continue
            hold = 0.0
            for i in range(T):
                hold += holding_cost * i * future_demands[i]
            unit_cost = (setup_cost + hold) / cumulative_qty

            if T > 1 and unit_cost > best_unit_cost:
                break
            best_unit_cost = unit_cost
            best_T = T

        qty = sum(future_demands[:best_T])
        return max(int(math.ceil(qty)), int(math.ceil(net_need)))

    # --- Part Period Balancing (PPB) ---
    if rule == "PPB":
        if not future_demands or len(future_demands) == 0:
            return int(math.ceil(net_need))

        # EPP = setup_cost / holding_cost (Economic Part Period)
        epp = setup_cost / holding_cost if holding_cost > 0 else 1.0
        best_T = 1
        best_diff = float("inf")

        cumulative_pp = 0.0
        for T in range(1, len(future_demands) + 1):
            # Part periods = demand[T-1] * (T-1) periods of carry
            if T > 1:
                cumulative_pp += future_demands[T - 1] * (T - 1)
            diff = abs(cumulative_pp - epp)
            if diff < best_diff:
                best_diff = diff
                best_T = T
            elif cumulative_pp > epp:
                break

        qty = sum(future_demands[:best_T])
        return max(int(math.ceil(qty)), int(math.ceil(net_need)))

    # --- Wagner-Whitin DP ---
    if rule == "WW":
        if not future_demands or len(future_demands) == 0:
            return int(math.ceil(net_need))

        n = len(future_demands)
        d = future_demands
        INF = float("inf")

        # f[j] = minimum cost to satisfy demands 0..j
        f = [INF] * n
        order_from = [0] * n  # which period starts the order covering period j

        for j in range(n):
            for i in range(j + 1):
                # Order placed in period i to cover periods i..j
                if i == 0:
                    prev_cost = 0.0
                else:
                    prev_cost = f[i - 1]
                if prev_cost == INF:
                    continue

                order_cost = setup_cost
                hold = 0.0
                for k in range(i, j + 1):
                    hold += holding_cost * (k - i) * d[k]
                total = prev_cost + order_cost + hold

                if total < f[j]:
                    f[j] = total
                    order_from[j] = i

        # Trace back to find the first order quantity
        # The first order covers periods order_from[...] to some end
        # We need the order that starts at period 0
        # Trace: find which periods are covered
        orders = []
        j = n - 1
        while j >= 0:
            i = order_from[j]
            orders.append((i, j))
            j = i - 1
        orders.reverse()

        if orders:
            first_start, first_end = orders[0]
            qty = sum(d[first_start:first_end + 1])
        else:
            qty = net_need
        return max(int(math.ceil(qty)), int(math.ceil(net_need)))

    # Fallback: lot-for-lot
    return int(math.ceil(net_need))


# ---------------------------------------------------------------------------
# MRP netting for a single item
# ---------------------------------------------------------------------------

def mrp_item(conn, item_id, verbose=False):
    """
    Run MRP netting logic for a single item.

    Returns a list of planned order dicts:
        [{item_id, release_week, receipt_week, quantity}, ...]
    """
    cur = conn.cursor()

    # Fetch item master data
    cur.execute(
        "SELECT level, lead_time, lot_rule, lot_size, safety_stock, "
        "on_hand, setup_cost, holding_cost FROM mrp_items WHERE item_id = ?",
        (item_id,),
    )
    row = cur.fetchone()
    if row is None:
        return []

    level, lead_time, lot_rule, lot_size, safety_stock, on_hand, \
        setup_cost, holding_cost = row

    # Gross requirements
    gross_map = get_gross_requirements(conn, item_id, level)
    if not gross_map:
        return []

    weeks = sorted(gross_map.keys())
    min_week = min(weeks)
    max_week = max(weeks)
    all_weeks = list(range(min_week, max_week + 1))

    # Build demand list for future-looking lot sizing methods
    demand_list = [gross_map.get(w, 0.0) for w in all_weeks]

    projected_oh = float(on_hand)
    planned_orders = []

    # Clear existing planned orders and inventory log for this item
    cur.execute("DELETE FROM mrp_planned_orders WHERE item_id = ?", (item_id,))
    cur.execute("DELETE FROM mrp_inventory_log WHERE item_id = ?", (item_id,))

    for idx, week in enumerate(all_weeks):
        gross_req = gross_map.get(week, 0.0)

        # Scheduled receipts (already firm orders)
        # For this engine, we don't pre-populate scheduled receipts,
        # so we default to 0. In production you'd query a table.
        scheduled_receipts = 0.0

        # Projected on-hand before any new orders
        projected_oh = projected_oh - gross_req + scheduled_receipts

        # Net requirement
        net_req = 0.0
        planned_receipt = 0.0
        planned_release = 0.0

        if projected_oh < safety_stock:
            net_req = safety_stock - projected_oh

            # Future demands from current period onward
            future_demands = demand_list[idx:]

            order_qty = apply_lot_rule(
                net_req, lot_rule, lot_size,
                future_demands=future_demands,
                setup_cost=setup_cost,
                holding_cost=holding_cost,
            )

            planned_receipt = float(order_qty)
            projected_oh += planned_receipt

            release_week = week - lead_time

            planned_orders.append({
                "item_id": item_id,
                "release_week": release_week,
                "receipt_week": week,
                "quantity": order_qty,
            })

            # Insert planned order
            cur.execute(
                "INSERT INTO mrp_planned_orders "
                "(item_id, release_week, receipt_week, quantity, status) "
                "VALUES (?, ?, ?, ?, 'planned')",
                (item_id, release_week, week, order_qty),
            )

            planned_release_week = release_week
        else:
            planned_release_week = None

        # Log inventory record for this week
        # planned_release is the order qty that is *released* in this week
        # We need to check if any order is released in this week
        release_qty = 0.0
        for po in planned_orders:
            if po["release_week"] == week:
                release_qty += po["quantity"]

        cur.execute(
            "INSERT OR REPLACE INTO mrp_inventory_log "
            "(item_id, week, gross_req, scheduled_receipts, projected_oh, "
            "net_req, planned_receipt, planned_release) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, week, gross_req, scheduled_receipts,
             projected_oh, net_req, planned_receipt, release_qty),
        )

    if verbose:
        print(f"\n--- MRP for {item_id} (level={level}, LT={lead_time}, "
              f"rule={lot_rule}, SS={safety_stock}) ---")
        print(f"{'Week':>6} {'GrossReq':>10} {'SchedRcpt':>10} "
              f"{'ProjOH':>10} {'NetReq':>10} {'PlnRcpt':>10} {'PlnRel':>10}")
        for week in all_weeks:
            cur.execute(
                "SELECT gross_req, scheduled_receipts, projected_oh, "
                "net_req, planned_receipt, planned_release "
                "FROM mrp_inventory_log WHERE item_id = ? AND week = ?",
                (item_id, week),
            )
            r = cur.fetchone()
            if r:
                print(f"{week:>6} {r[0]:>10.1f} {r[1]:>10.1f} "
                      f"{r[2]:>10.1f} {r[3]:>10.1f} {r[4]:>10.1f} {r[5]:>10.1f}")

    conn.commit()
    return planned_orders


# ---------------------------------------------------------------------------
# Full MRP run
# ---------------------------------------------------------------------------

def run_mrp(conn, verbose=False):
    """
    Run MRP for all items, processing by BOM level (level 0 first).

    Returns (total_orders, past_due_count).
    """
    cur = conn.cursor()

    # Clear all previous results
    cur.execute("DELETE FROM mrp_planned_orders")
    cur.execute("DELETE FROM mrp_inventory_log")
    conn.commit()

    # Cache original on_hand for reset capability
    global _ORIGINAL_ON_HAND
    if not _ORIGINAL_ON_HAND:
        cur.execute("SELECT item_id, on_hand FROM mrp_items")
        _ORIGINAL_ON_HAND = {r[0]: r[1] for r in cur.fetchall()}

    # Get items sorted by BOM level
    cur.execute("SELECT item_id, level FROM mrp_items ORDER BY level ASC, item_id ASC")
    items = cur.fetchall()

    total_orders = 0
    past_due = 0

    for item_id, level in items:
        orders = mrp_item(conn, item_id, verbose=verbose)
        total_orders += len(orders)
        for o in orders:
            if o["release_week"] < 1:
                past_due += 1

    if verbose:
        print(f"\n=== MRP Complete: {total_orders} planned orders, "
              f"{past_due} past-due ===")

    return total_orders, past_due


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def get_mrp_report(conn):
    """
    Return list of dicts with all planned orders joined with item details.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT po.order_id, po.item_id, i.name, i.level, i.item_type,
               po.release_week, po.receipt_week, po.quantity, po.status,
               i.lot_rule, i.lead_time, i.safety_stock,
               i.unit_cost, po.quantity * i.unit_cost AS order_cost
        FROM mrp_planned_orders po
        JOIN mrp_items i ON po.item_id = i.item_id
        ORDER BY i.level, po.item_id, po.receipt_week
    """)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return [dict(zip(cols, r)) for r in rows]


def get_mrp_summary(conn):
    """
    Return list of dicts summarized by item: total orders, total qty,
    total cost, earliest release, latest receipt.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT po.item_id, i.name, i.level, i.item_type, i.lot_rule,
               COUNT(*) AS num_orders,
               SUM(po.quantity) AS total_qty,
               SUM(po.quantity * i.unit_cost) AS total_cost,
               MIN(po.release_week) AS earliest_release,
               MAX(po.receipt_week) AS latest_receipt,
               SUM(CASE WHEN po.release_week < 1 THEN 1 ELSE 0 END) AS past_due
        FROM mrp_planned_orders po
        JOIN mrp_items i ON po.item_id = i.item_id
        GROUP BY po.item_id
        ORDER BY i.level, po.item_id
    """)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return [dict(zip(cols, r)) for r in rows]


# ---------------------------------------------------------------------------
# Demand simulation
# ---------------------------------------------------------------------------

def simulate_demand(conn, item_id, weeks=8, base=15, noise=0.3, seed=42):
    """
    Generate simulated weekly demand with seasonality and noise.

    d_t = base * seasonal(t) * N(1, noise)
    where seasonal(t) = 1 + 0.2 * sin(2 * pi * t / 12)

    Returns list of weekly demand values (length = weeks).
    """
    rng = random.Random(seed)
    demands = []

    for t in range(1, weeks + 1):
        seasonal = 1.0 + 0.2 * math.sin(2.0 * math.pi * t / 12.0)
        noise_factor = rng.gauss(1.0, noise)
        noise_factor = max(0.1, noise_factor)  # prevent negative
        d_t = base * seasonal * noise_factor
        d_t = max(0, round(d_t))
        demands.append(d_t)

    # Optionally insert into mrp_demand
    cur = conn.cursor()
    for t, qty in enumerate(demands, start=1):
        cur.execute(
            "INSERT OR REPLACE INTO mrp_demand (item_id, week, quantity, source) "
            "VALUES (?, ?, ?, 'simulated')",
            (item_id, t, qty),
        )
    conn.commit()

    return demands


# ---------------------------------------------------------------------------
# Plan nervousness
# ---------------------------------------------------------------------------

def compute_nervousness(plan_a, plan_b):
    """
    Compare two MRP plans and quantify schedule nervousness.

    Parameters
    ----------
    plan_a, plan_b : list of dict
        Each dict has keys: item_id, release_week, receipt_week, quantity.

    Returns
    -------
    dict with keys:
        pct_changed  : float  - percentage of orders that differ
        n_added      : int    - orders in B not in A
        n_deleted    : int    - orders in A not in B
        qty_delta    : float  - absolute change in total planned quantity
    """
    def _key(order):
        return (order["item_id"], order["release_week"], order["receipt_week"])

    set_a = {}
    for o in plan_a:
        k = _key(o)
        set_a[k] = o.get("quantity", 0)

    set_b = {}
    for o in plan_b:
        k = _key(o)
        set_b[k] = o.get("quantity", 0)

    keys_a = set(set_a.keys())
    keys_b = set(set_b.keys())

    added = keys_b - keys_a
    deleted = keys_a - keys_b
    common = keys_a & keys_b

    changed = 0
    for k in common:
        if abs(set_a[k] - set_b[k]) > 0.01:
            changed += 1

    total_orders = len(keys_a | keys_b)
    n_changed = len(added) + len(deleted) + changed

    qty_a = sum(set_a.values())
    qty_b = sum(set_b.values())

    return {
        "pct_changed": (n_changed / total_orders * 100.0) if total_orders > 0 else 0.0,
        "n_added": len(added),
        "n_deleted": len(deleted),
        "qty_delta": abs(qty_b - qty_a),
    }


# ---------------------------------------------------------------------------
# Demand pegging
# ---------------------------------------------------------------------------

def get_pegging_report(conn, item_id):
    """
    Walk planned orders for *item_id* backward to their originating MPS demand.

    For each planned order, identify which parent demands drove it by
    traversing the BOM upward (via mrp_bom) until a level-0 item with
    MPS demand is reached.

    Returns a list of dicts:
        [{item_id, planned_qty, receipt_week, pegged_to_item,
          pegged_demand_qty, demand_week}, ...]
    """
    cur = conn.cursor()

    # Fetch planned orders for the requested item
    cur.execute(
        "SELECT receipt_week, quantity FROM mrp_planned_orders "
        "WHERE item_id = ? AND status = 'planned' "
        "ORDER BY receipt_week",
        (item_id,),
    )
    planned_orders = cur.fetchall()

    if not planned_orders:
        return []

    # Determine BOM level
    cur.execute("SELECT level FROM mrp_items WHERE item_id = ?", (item_id,))
    row = cur.fetchone()
    if row is None:
        return []
    item_level = row[0]

    report = []

    for receipt_week, planned_qty in planned_orders:
        if item_level == 0:
            # Level 0: peg directly to its own MPS demand
            cur.execute(
                "SELECT week, quantity FROM mrp_demand "
                "WHERE item_id = ? AND source = 'MPS' AND week = ?",
                (item_id, receipt_week),
            )
            mps_row = cur.fetchone()
            demand_qty = mps_row[1] if mps_row else 0.0
            report.append({
                "item_id": item_id,
                "planned_qty": planned_qty,
                "receipt_week": receipt_week,
                "pegged_to_item": item_id,
                "pegged_demand_qty": demand_qty,
                "demand_week": receipt_week,
            })
        else:
            # Walk upward through BOM parents until we reach level-0 MPS
            _peg_to_parents(conn, cur, item_id, planned_qty,
                            receipt_week, report)

    return report


def _peg_to_parents(conn, cur, child_id, child_qty, child_week, report):
    """Recursively trace a child's planned order up to MPS-level parents."""
    cur.execute(
        "SELECT parent_id, qty_per, scrap_rate FROM mrp_bom WHERE child_id = ?",
        (child_id,),
    )
    parents = cur.fetchall()

    for parent_id, qty_per, scrap_rate in parents:
        cur.execute("SELECT level FROM mrp_items WHERE item_id = ?",
                     (parent_id,))
        parent_row = cur.fetchone()
        if parent_row is None:
            continue
        parent_level = parent_row[0]

        # How much of the parent demand drove this child qty?
        effective_per = qty_per * (1.0 + scrap_rate)
        if effective_per <= 0:
            continue
        parent_qty_driven = child_qty / effective_per

        if parent_level == 0:
            # Reached MPS level — find the demand entry closest to week
            cur.execute(
                "SELECT week, quantity FROM mrp_demand "
                "WHERE item_id = ? AND source = 'MPS' "
                "ORDER BY ABS(week - ?) LIMIT 1",
                (parent_id, child_week),
            )
            mps_row = cur.fetchone()
            demand_week = mps_row[0] if mps_row else child_week
            demand_qty = mps_row[1] if mps_row else 0.0

            report.append({
                "item_id": child_id,
                "planned_qty": child_qty,
                "receipt_week": child_week,
                "pegged_to_item": parent_id,
                "pegged_demand_qty": demand_qty,
                "demand_week": demand_week,
            })
        else:
            # Intermediate level — keep walking upward
            _peg_to_parents(conn, cur, parent_id, parent_qty_driven,
                            child_week, report)


# ---------------------------------------------------------------------------
# Kanban sizing
# ---------------------------------------------------------------------------

def compute_kanban_size(demand_rate, lead_time, safety_factor=0.2):
    """
    Compute kanban container size using the standard formula.

    K = demand_rate x lead_time x (1 + safety_factor)

    Parameters
    ----------
    demand_rate : float
        Average demand per period (e.g. units/week).
    lead_time : float
        Replenishment lead time in the same time unit as demand_rate.
    safety_factor : float
        Safety margin as a fraction (default 0.2 = 20%).

    Returns
    -------
    dict with keys: demand_rate, lead_time, safety_factor, kanban_size
    """
    kanban_size = demand_rate * lead_time * (1.0 + safety_factor)
    return {
        "demand_rate": demand_rate,
        "lead_time": lead_time,
        "safety_factor": safety_factor,
        "kanban_size": round(kanban_size, 2),
    }


# ---------------------------------------------------------------------------
# Convenience: run from command line
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    conn = sqlite3.connect(":memory:")
    create_mrp_tables(conn)
    n_items, n_bom, n_demand = populate_sodhicable_bom(conn)
    print(f"Seeded {n_items} items, {n_bom} BOM links, {n_demand} demand records.")

    # Show BOM tree for FG-A1
    print("\n=== BOM Tree: FG-A1 ===")
    for node in get_bom_tree(conn, "FG-A1"):
        print(f"{node['indent']}{node['item_id']}  ({node['name']})  "
              f"x{node['qty_per']}")

    # Explode BOM
    print("\n=== BOM Explosion: FG-B1 x 10 ===")
    explosion = explode_bom(conn, "FG-B1", 10)
    for item_id, qty in sorted(explosion.items()):
        print(f"  {item_id}: {qty:.2f}")

    # Run full MRP
    print("\n=== Running MRP ===")
    total, past_due = run_mrp(conn, verbose=True)

    # Summary
    print("\n=== MRP Summary ===")
    for row in get_mrp_summary(conn):
        print(f"  {row['item_id']:20s}  orders={row['num_orders']:3d}  "
              f"qty={row['total_qty']:8.0f}  cost=${row['total_cost']:10.2f}  "
              f"past_due={row['past_due']}")

    # Simulate demand
    print("\n=== Simulated Demand for FG-A1 ===")
    sim = simulate_demand(conn, "FG-A1", weeks=8, base=15, noise=0.3, seed=42)
    print(f"  Weekly demands: {sim}")

    # Nervousness
    plan_a = get_mrp_report(conn)
    # Re-run with modified demand to compute nervousness
    reset_inventory(conn)
    simulate_demand(conn, "FG-A1", weeks=8, base=18, noise=0.3, seed=99)
    run_mrp(conn, verbose=False)
    plan_b = get_mrp_report(conn)
    nerv = compute_nervousness(plan_a, plan_b)
    print(f"\n=== Schedule Nervousness ===")
    print(f"  Changed: {nerv['pct_changed']:.1f}%  "
          f"Added: {nerv['n_added']}  Deleted: {nerv['n_deleted']}  "
          f"Qty delta: {nerv['qty_delta']:.0f}")

    conn.close()
