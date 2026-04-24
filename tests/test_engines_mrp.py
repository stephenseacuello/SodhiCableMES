"""
Tests for engines/mrp_engine.py -- Material Requirements Planning Engine.

Covers BOM explosion, lot-sizing rules (L4L, FOQ, EOQ), net requirements
calculation, full MRP runs, kanban sizing, and plan nervousness.
"""

import math
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.mrp_engine import (
    create_mrp_tables,
    populate_sodhicable_bom,
    explode_bom,
    get_bom_tree,
    apply_lot_rule,
    mrp_item,
    run_mrp,
    compute_nervousness,
    compute_kanban_size,
    get_mrp_report,
    get_mrp_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mrp_db():
    """Return a fresh in-memory connection with MRP tables and seed data."""
    conn = sqlite3.connect(":memory:")
    create_mrp_tables(conn)
    populate_sodhicable_bom(conn)
    return conn


# ===================================================================
# BOM Explosion
# ===================================================================

class TestBomExplosion:
    """Verify recursive BOM explosion with scrap adjustment."""

    def test_parent_appears_in_explosion(self):
        """The requested parent item itself is included in the explosion."""
        conn = _mrp_db()
        result = explode_bom(conn, "FG-A1", 10)
        assert "FG-A1" in result
        assert result["FG-A1"] == pytest.approx(10.0)
        conn.close()

    def test_children_appear_in_explosion(self):
        """Direct children of FG-A1 appear in the explosion."""
        conn = _mrp_db()
        result = explode_bom(conn, "FG-A1", 10)
        # FG-A1 has children SA-WIRE-CU, SA-INSUL-PVC, SA-JACKET-PVC
        assert "SA-WIRE-CU" in result
        assert "SA-INSUL-PVC" in result
        assert "SA-JACKET-PVC" in result
        conn.close()

    def test_grandchildren_appear_in_explosion(self):
        """Raw materials (level 2) appear via recursive explosion."""
        conn = _mrp_db()
        result = explode_bom(conn, "FG-A1", 10)
        # SA-WIRE-CU -> RM-CU-ROD
        assert "RM-CU-ROD" in result
        conn.close()

    def test_scrap_adjustment_increases_quantity(self):
        """With include_scrap=True, child quantities exceed qty_per * parent."""
        conn = _mrp_db()
        with_scrap = explode_bom(conn, "FG-A1", 10, include_scrap=True)
        without_scrap = explode_bom(conn, "FG-A1", 10, include_scrap=False)
        # SA-WIRE-CU has scrap_rate=0.02, so scrap-adjusted qty > unadjusted
        assert with_scrap["SA-WIRE-CU"] > without_scrap["SA-WIRE-CU"]
        conn.close()

    def test_qty_per_scaling(self):
        """Child qty scales with qty_per from BOM link."""
        conn = _mrp_db()
        # FG-A1 -> SA-WIRE-CU has qty_per=3.0, scrap=0.02
        result = explode_bom(conn, "FG-A1", 10, include_scrap=False)
        assert result["SA-WIRE-CU"] == pytest.approx(30.0)
        conn.close()


# ===================================================================
# BOM Tree
# ===================================================================

class TestBomTree:
    """Verify the indented BOM tree representation."""

    def test_tree_root_is_first(self):
        """The first entry is the root item at level 0."""
        conn = _mrp_db()
        tree = get_bom_tree(conn, "FG-A1")
        assert tree[0]["item_id"] == "FG-A1"
        assert tree[0]["level"] == 0
        conn.close()

    def test_tree_has_children(self):
        """Children appear at level 1 in the tree."""
        conn = _mrp_db()
        tree = get_bom_tree(conn, "FG-A1")
        child_ids = [n["item_id"] for n in tree if n["level"] == 1]
        assert "SA-WIRE-CU" in child_ids
        conn.close()


# ===================================================================
# Lot-Sizing Rules
# ===================================================================

class TestLotSizing:
    """Verify the seven lot-sizing methods."""

    def test_l4l_returns_exact_need(self):
        """Lot-for-Lot returns ceil(net_need)."""
        assert apply_lot_rule(10.0, "L4L", 1) == 10
        assert apply_lot_rule(10.3, "L4L", 1) == 11

    def test_foq_rounds_up_to_lot_size(self):
        """Fixed Order Quantity rounds up to the nearest lot_size multiple."""
        assert apply_lot_rule(10.0, "FOQ", 50) == 50
        assert apply_lot_rule(60.0, "FOQ", 50) == 100

    def test_eoq_at_least_net_need(self):
        """EOQ returns at least ceil(net_need)."""
        result = apply_lot_rule(5.0, "EOQ", 1,
                                future_demands=[5, 5, 5, 5],
                                setup_cost=500, holding_cost=2.0)
        assert result >= 5

    def test_eoq_formula_sanity(self):
        """EOQ follows sqrt(2DS/H) and is reasonable for given parameters."""
        # D ~ 5*52 = 260, S=500, H=2 => EOQ = sqrt(2*260*500/2) = sqrt(130000) ~ 360
        result = apply_lot_rule(5.0, "EOQ", 1,
                                future_demands=[5, 5, 5, 5],
                                setup_cost=500, holding_cost=2.0)
        assert result >= 5
        assert result <= 500  # reasonable upper bound

    def test_zero_need_returns_zero(self):
        """Zero net need returns order qty of 0 regardless of rule."""
        assert apply_lot_rule(0.0, "L4L", 1) == 0
        assert apply_lot_rule(0.0, "FOQ", 50) == 0
        assert apply_lot_rule(-5.0, "EOQ", 1) == 0

    def test_silver_meal_at_least_net_need(self):
        """Silver-Meal heuristic returns at least net_need."""
        result = apply_lot_rule(10.0, "SM", 1,
                                future_demands=[10, 15, 8, 12],
                                setup_cost=500, holding_cost=2.0)
        assert result >= 10

    def test_wagner_whitin_at_least_net_need(self):
        """Wagner-Whitin DP returns at least net_need."""
        result = apply_lot_rule(10.0, "WW", 1,
                                future_demands=[10, 15, 8, 12],
                                setup_cost=500, holding_cost=2.0)
        assert result >= 10

    def test_unknown_rule_falls_back_to_l4l(self):
        """An unrecognized rule falls back to lot-for-lot."""
        assert apply_lot_rule(7.0, "UNKNOWN", 1) == 7


# ===================================================================
# Net Requirements (MRP Item)
# ===================================================================

class TestMrpItem:
    """Verify single-item MRP netting logic."""

    def test_planned_orders_generated(self):
        """Running MRP on a level-0 item with demand produces planned orders."""
        conn = _mrp_db()
        orders = mrp_item(conn, "FG-A1")
        assert len(orders) > 0
        conn.close()

    def test_planned_order_structure(self):
        """Each planned order has item_id, release_week, receipt_week, quantity."""
        conn = _mrp_db()
        orders = mrp_item(conn, "FG-A1")
        for o in orders:
            assert "item_id" in o
            assert "release_week" in o
            assert "receipt_week" in o
            assert "quantity" in o
            assert o["quantity"] > 0
        conn.close()

    def test_receipt_minus_release_equals_lead_time(self):
        """receipt_week - release_week equals the item's lead time."""
        conn = _mrp_db()
        cur = conn.cursor()
        cur.execute("SELECT lead_time FROM mrp_items WHERE item_id = 'FG-A1'")
        lt = cur.fetchone()[0]
        orders = mrp_item(conn, "FG-A1")
        for o in orders:
            assert o["receipt_week"] - o["release_week"] == lt
        conn.close()

    def test_nonexistent_item_returns_empty(self):
        """MRP on an item not in mrp_items returns an empty list."""
        conn = _mrp_db()
        orders = mrp_item(conn, "DOES-NOT-EXIST")
        assert orders == []
        conn.close()


# ===================================================================
# Full MRP Run
# ===================================================================

class TestRunMrp:
    """Verify the full multi-level MRP explosion."""

    def test_run_mrp_returns_totals(self):
        """run_mrp returns (total_orders, past_due_count)."""
        conn = _mrp_db()
        total, past_due = run_mrp(conn)
        assert total > 0
        assert past_due >= 0
        conn.close()

    def test_mrp_report_not_empty(self):
        """After a full run, the MRP report has planned order rows."""
        conn = _mrp_db()
        run_mrp(conn)
        report = get_mrp_report(conn)
        assert len(report) > 0
        conn.close()

    def test_mrp_summary_groups_by_item(self):
        """MRP summary groups orders by item_id."""
        conn = _mrp_db()
        run_mrp(conn)
        summary = get_mrp_summary(conn)
        item_ids = [row["item_id"] for row in summary]
        assert len(item_ids) == len(set(item_ids))  # unique
        conn.close()


# ===================================================================
# Kanban Sizing
# ===================================================================

class TestKanbanSize:
    """Verify kanban container size formula K = D * LT * (1 + SF)."""

    def test_basic_kanban_calculation(self):
        """K = 100 * 2 * 1.2 = 240."""
        result = compute_kanban_size(100.0, 2.0, safety_factor=0.2)
        assert result["kanban_size"] == pytest.approx(240.0)

    def test_zero_lead_time(self):
        """Zero lead time produces zero kanban size."""
        result = compute_kanban_size(100.0, 0.0)
        assert result["kanban_size"] == pytest.approx(0.0)

    def test_result_keys(self):
        """Return dict contains all expected keys."""
        result = compute_kanban_size(50.0, 3.0)
        assert "demand_rate" in result
        assert "lead_time" in result
        assert "safety_factor" in result
        assert "kanban_size" in result


# ===================================================================
# Plan Nervousness
# ===================================================================

class TestNervousness:
    """Verify schedule nervousness comparison of two MRP plans."""

    def test_identical_plans_zero_nervousness(self):
        """Two identical plans should have 0% change."""
        plan = [
            {"item_id": "A", "release_week": 1, "receipt_week": 2, "quantity": 10},
            {"item_id": "B", "release_week": 2, "receipt_week": 3, "quantity": 20},
        ]
        result = compute_nervousness(plan, plan)
        assert result["pct_changed"] == pytest.approx(0.0)
        assert result["n_added"] == 0
        assert result["n_deleted"] == 0
        assert result["qty_delta"] == pytest.approx(0.0)

    def test_completely_different_plans(self):
        """Plans with no overlapping orders should show 100% change."""
        plan_a = [
            {"item_id": "A", "release_week": 1, "receipt_week": 2, "quantity": 10},
        ]
        plan_b = [
            {"item_id": "B", "release_week": 3, "receipt_week": 4, "quantity": 20},
        ]
        result = compute_nervousness(plan_a, plan_b)
        assert result["pct_changed"] == pytest.approx(100.0)
        assert result["n_added"] == 1
        assert result["n_deleted"] == 1
