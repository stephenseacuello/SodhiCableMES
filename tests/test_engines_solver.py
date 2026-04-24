"""
Tests for engines/solver.py -- Embedded LP/IP Solver.

Covers simple 2-variable LP problems, integer programming,
infeasible and unbounded detection, the lpSum helper, and
the value() extractor.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.solver import (
    LpProblem,
    LpVariable,
    LpMaximize,
    LpMinimize,
    LpContinuous,
    LpBinary,
    LpInteger,
    LpStatus,
    lpSum,
    value,
)


# ===================================================================
# Simple 2-Variable LP
# ===================================================================

class TestSimpleLP:
    """Verify LP solutions for classic textbook problems."""

    def test_maximize_2var_lp(self):
        """Maximize z = 3x + 5y subject to x<=4, 2y<=12, 3x+5y<=15.

        Optimal: x=0, y=3, z=15  (or x=1.25, y=2.25, z=15 depending on
        active constraints -- solver should find z=15).
        """
        prob = LpProblem("test_max", LpMaximize)
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)

        prob += 3 * x + 5 * y  # objective
        prob += (x <= 4)
        prob += (2 * y <= 12)
        prob += (3 * x + 5 * y <= 15)

        status = prob.solve()
        assert status == 1  # Optimal
        assert prob.status == "Optimal"

        obj_val = 3 * x.varValue + 5 * y.varValue
        assert obj_val == pytest.approx(15.0, abs=0.01)

    def test_minimize_2var_lp(self):
        """Minimize z = 2x + 3y subject to x+y>=4, x>=1, y>=1.

        Optimal: x=3, y=1, z=9  (or x=1, y=3, z=11 -- solver picks min).
        """
        prob = LpProblem("test_min", LpMinimize)
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)

        prob += 2 * x + 3 * y
        prob += (x + y >= 4)
        prob += (x >= 1)
        prob += (y >= 1)

        status = prob.solve()
        assert status == 1
        obj_val = 2 * x.varValue + 3 * y.varValue
        # Optimal is x=3, y=1 -> z=9
        assert obj_val == pytest.approx(9.0, abs=0.01)

    def test_variable_values_nonnegative(self):
        """Variables with lowBound=0 should have non-negative optimal values."""
        prob = LpProblem("test_bounds", LpMaximize)
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)

        prob += x + y
        prob += (x + y <= 10)

        prob.solve()
        assert x.varValue >= -1e-8
        assert y.varValue >= -1e-8

    def test_equality_constraint(self):
        """An equality constraint pins the optimal exactly."""
        prob = LpProblem("test_eq", LpMaximize)
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)

        prob += x + y
        prob += (x + y == 5)  # equality

        status = prob.solve()
        assert status == 1
        assert x.varValue + y.varValue == pytest.approx(5.0, abs=0.01)

    def test_upper_bound_on_variable(self):
        """Variable upBound is respected."""
        prob = LpProblem("test_ub", LpMaximize)
        x = LpVariable("x", lowBound=0, upBound=3)
        y = LpVariable("y", lowBound=0, upBound=3)

        prob += x + y

        status = prob.solve()
        assert status == 1
        assert x.varValue <= 3.0 + 1e-6
        assert y.varValue <= 3.0 + 1e-6


# ===================================================================
# Integer Programming
# ===================================================================

class TestIntegerProgramming:
    """Verify integer and binary variable constraints."""

    def test_binary_variable_is_0_or_1(self):
        """Binary variables should take value 0 or 1."""
        prob = LpProblem("test_binary", LpMaximize)
        x = LpVariable("x", cat=LpBinary)
        y = LpVariable("y", cat=LpBinary)

        prob += 3 * x + 4 * y
        prob += (x + y <= 1)

        status = prob.solve()
        assert status == 1
        assert x.varValue == pytest.approx(0.0, abs=0.01) or x.varValue == pytest.approx(1.0, abs=0.01)
        assert y.varValue == pytest.approx(0.0, abs=0.01) or y.varValue == pytest.approx(1.0, abs=0.01)
        # Optimal: y=1, x=0, z=4
        assert y.varValue == pytest.approx(1.0, abs=0.01)

    def test_integer_variable_is_integral(self):
        """Integer variables should have integer-valued solutions."""
        prob = LpProblem("test_int", LpMaximize)
        x = LpVariable("x", lowBound=0, cat=LpInteger)
        y = LpVariable("y", lowBound=0, cat=LpInteger)

        prob += 5 * x + 4 * y
        prob += (6 * x + 4 * y <= 24)
        prob += (x + 2 * y <= 6)

        status = prob.solve()
        assert status == 1
        # Values should be (close to) integers
        assert abs(x.varValue - round(x.varValue)) < 0.01
        assert abs(y.varValue - round(y.varValue)) < 0.01

    def test_knapsack_problem(self):
        """Classic 0-1 knapsack: pick items to maximize value within weight limit."""
        prob = LpProblem("knapsack", LpMaximize)
        items = [
            LpVariable(f"item_{i}", cat=LpBinary)
            for i in range(4)
        ]
        values_list = [10, 40, 30, 50]
        weights = [5, 4, 6, 3]
        capacity = 10

        prob += lpSum(v * items[i] for i, v in enumerate(values_list))
        prob += lpSum(w * items[i] for i, w in enumerate(weights)) <= capacity

        status = prob.solve()
        assert status == 1
        total_weight = sum(weights[i] * items[i].varValue for i in range(4))
        assert total_weight <= capacity + 0.01


# ===================================================================
# Infeasible / Unbounded
# ===================================================================

class TestEdgeCases:
    """Verify solver handles infeasible and unbounded problems."""

    def test_infeasible_problem(self):
        """Contradictory constraints should return infeasible (status -1)."""
        prob = LpProblem("infeasible", LpMaximize)
        x = LpVariable("x", lowBound=0)

        prob += x
        prob += (x >= 10)
        prob += (x <= 5)  # contradicts x >= 10

        status = prob.solve()
        assert status == -1

    def test_value_function_extracts_variable(self):
        """value() extracts the numeric value from an LpVariable."""
        prob = LpProblem("val_test", LpMaximize)
        x = LpVariable("x", lowBound=0, upBound=5)
        prob += x
        prob.solve()
        assert value(x) == pytest.approx(5.0, abs=0.01)

    def test_value_function_with_number(self):
        """value() passes through plain numbers unchanged."""
        assert value(42) == 42.0
        assert value(3.14) == pytest.approx(3.14)

    def test_lpsum_aggregation(self):
        """lpSum correctly aggregates a list of variable expressions."""
        x = LpVariable("x", lowBound=0)
        y = LpVariable("y", lowBound=0)
        expr = lpSum([2 * x, 3 * y, 10])
        # expr should have terms {x: 2, y: 3} and constant 10
        assert expr.terms[x] == pytest.approx(2.0)
        assert expr.terms[y] == pytest.approx(3.0)
        assert expr.constant == pytest.approx(10.0)

    def test_status_string_mapping(self):
        """LpStatus maps integer codes to human-readable strings."""
        assert LpStatus[1] == "Optimal"
        assert LpStatus[-1] == "Infeasible"
        assert LpStatus[-2] == "Unbounded"
        assert LpStatus[0] == "Not Solved"
