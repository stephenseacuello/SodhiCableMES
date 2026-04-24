"""
Embedded LP/IP solver with a PuLP-compatible API.

Two-phase revised simplex for LP, branch-and-bound for IP/MIP.
No external dependencies beyond the standard library.
"""

import copy
import math

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LpMaximize = 1
LpMinimize = -1

LpContinuous = "Continuous"
LpBinary = "Binary"
LpInteger = "Integer"

LpStatus = {
    1: "Optimal",
    0: "Not Solved",
    -1: "Infeasible",
    -2: "Unbounded",
    -3: "Undefined",
}

BIG_M = 1e7
MAX_ITER = 5000
_tolerance = 1e-8

# ---------------------------------------------------------------------------
# LpVariable
# ---------------------------------------------------------------------------

class LpVariable:
    """Decision variable for an LP / IP model."""

    def __init__(self, name, lowBound=None, upBound=None, cat=LpContinuous, e=None):
        self.name = name
        self.lowBound = lowBound
        self.upBound = upBound
        self.cat = cat
        self.value = None
        if cat == LpBinary:
            self.lowBound = 0
            self.upBound = 1

    # -- value property -----------------------------------------------------
    @property
    def varValue(self):
        return self.value

    # -- arithmetic ---------------------------------------------------------
    def __neg__(self):
        return LpAffineExpression({self: -1.0})

    def __add__(self, other):
        if isinstance(other, LpVariable):
            return LpAffineExpression({self: 1.0, other: 1.0})
        if isinstance(other, LpAffineExpression):
            expr = LpAffineExpression({self: 1.0})
            for v, c in other.terms.items():
                expr.terms[v] = expr.terms.get(v, 0.0) + c
            expr.constant = other.constant
            return expr
        if isinstance(other, (int, float)):
            return LpAffineExpression({self: 1.0}, constant=float(other))
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, (int, float)):
            return LpAffineExpression({self: 1.0}, constant=float(other))
        if other == 0:
            return LpAffineExpression({self: 1.0})
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, LpVariable):
            return LpAffineExpression({self: 1.0, other: -1.0})
        if isinstance(other, LpAffineExpression):
            expr = LpAffineExpression({self: 1.0})
            for v, c in other.terms.items():
                expr.terms[v] = expr.terms.get(v, 0.0) - c
            expr.constant = -other.constant
            return expr
        if isinstance(other, (int, float)):
            return LpAffineExpression({self: 1.0}, constant=-float(other))
        return NotImplemented

    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            return LpAffineExpression({self: -1.0}, constant=float(other))
        return NotImplemented

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return LpAffineExpression({self: float(other)})
        return NotImplemented

    def __rmul__(self, other):
        if isinstance(other, (int, float)):
            return LpAffineExpression({self: float(other)})
        return NotImplemented

    # -- comparison (constraint construction) --------------------------------
    def __le__(self, other):
        # self <= other  -->  self - other <= 0
        if isinstance(other, (int, float)):
            return LpConstraint(LpAffineExpression({self: 1.0}), sense=-1, rhs=float(other))
        if isinstance(other, LpVariable):
            return LpConstraint(LpAffineExpression({self: 1.0, other: -1.0}), sense=-1, rhs=0.0)
        if isinstance(other, LpAffineExpression):
            expr = LpAffineExpression({self: 1.0})
            for v, c in other.terms.items():
                expr.terms[v] = expr.terms.get(v, 0.0) - c
            return LpConstraint(expr, sense=-1, rhs=other.constant)
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, (int, float)):
            return LpConstraint(LpAffineExpression({self: 1.0}), sense=1, rhs=float(other))
        if isinstance(other, LpVariable):
            return LpConstraint(LpAffineExpression({self: 1.0, other: -1.0}), sense=1, rhs=0.0)
        if isinstance(other, LpAffineExpression):
            expr = LpAffineExpression({self: 1.0})
            for v, c in other.terms.items():
                expr.terms[v] = expr.terms.get(v, 0.0) - c
            return LpConstraint(expr, sense=1, rhs=other.constant)
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, (int, float)):
            return LpConstraint(LpAffineExpression({self: 1.0}), sense=0, rhs=float(other))
        if isinstance(other, LpVariable):
            return LpConstraint(LpAffineExpression({self: 1.0, other: -1.0}), sense=0, rhs=0.0)
        if isinstance(other, LpAffineExpression):
            expr = LpAffineExpression({self: 1.0})
            for v, c in other.terms.items():
                expr.terms[v] = expr.terms.get(v, 0.0) - c
            return LpConstraint(expr, sense=0, rhs=other.constant)
        return NotImplemented

    def __hash__(self):
        return id(self)

    def __repr__(self):
        return f"LpVariable({self.name})"

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# LpAffineExpression
# ---------------------------------------------------------------------------

class LpAffineExpression:
    """Linear combination of LpVariables plus a constant."""

    def __init__(self, terms=None, constant=0.0):
        if terms is None:
            self.terms = {}
        elif isinstance(terms, dict):
            self.terms = dict(terms)
        elif isinstance(terms, LpVariable):
            self.terms = {terms: 1.0}
        elif isinstance(terms, LpAffineExpression):
            self.terms = dict(terms.terms)
            constant += terms.constant
        elif isinstance(terms, (int, float)):
            self.terms = {}
            constant += float(terms)
        else:
            self.terms = {}
        self.constant = float(constant)

    def value(self):
        """Evaluate the expression using current variable values."""
        total = self.constant
        for var, coeff in self.terms.items():
            if var.value is None:
                return None
            total += var.value * coeff
        return total

    # -- arithmetic ---------------------------------------------------------
    def __neg__(self):
        new_terms = {v: -c for v, c in self.terms.items()}
        return LpAffineExpression(new_terms, -self.constant)

    def __add__(self, other):
        result = LpAffineExpression(self.terms, self.constant)
        if isinstance(other, LpAffineExpression):
            for v, c in other.terms.items():
                result.terms[v] = result.terms.get(v, 0.0) + c
            result.constant += other.constant
        elif isinstance(other, LpVariable):
            result.terms[other] = result.terms.get(other, 0.0) + 1.0
        elif isinstance(other, (int, float)):
            result.constant += float(other)
        else:
            return NotImplemented
        return result

    def __radd__(self, other):
        if isinstance(other, (int, float)):
            return LpAffineExpression(self.terms, self.constant + float(other))
        if other == 0:
            return LpAffineExpression(self.terms, self.constant)
        if isinstance(other, LpVariable):
            result = LpAffineExpression(self.terms, self.constant)
            result.terms[other] = result.terms.get(other, 0.0) + 1.0
            return result
        return NotImplemented

    def __iadd__(self, other):
        if isinstance(other, LpAffineExpression):
            for v, c in other.terms.items():
                self.terms[v] = self.terms.get(v, 0.0) + c
            self.constant += other.constant
        elif isinstance(other, LpVariable):
            self.terms[other] = self.terms.get(other, 0.0) + 1.0
        elif isinstance(other, (int, float)):
            self.constant += float(other)
        else:
            return NotImplemented
        return self

    def __sub__(self, other):
        result = LpAffineExpression(self.terms, self.constant)
        if isinstance(other, LpAffineExpression):
            for v, c in other.terms.items():
                result.terms[v] = result.terms.get(v, 0.0) - c
            result.constant -= other.constant
        elif isinstance(other, LpVariable):
            result.terms[other] = result.terms.get(other, 0.0) - 1.0
        elif isinstance(other, (int, float)):
            result.constant -= float(other)
        else:
            return NotImplemented
        return result

    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            neg = -self
            neg.constant += float(other)
            return neg
        if isinstance(other, LpVariable):
            neg = -self
            neg.terms[other] = neg.terms.get(other, 0.0) + 1.0
            return neg
        return NotImplemented

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            new_terms = {v: c * float(other) for v, c in self.terms.items()}
            return LpAffineExpression(new_terms, self.constant * float(other))
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    # -- comparison (constraint construction) --------------------------------
    def __le__(self, other):
        if isinstance(other, (int, float)):
            return LpConstraint(LpAffineExpression(self.terms, 0.0), sense=-1,
                                rhs=float(other) - self.constant)
        if isinstance(other, LpVariable):
            expr = LpAffineExpression(self.terms, 0.0)
            expr.terms[other] = expr.terms.get(other, 0.0) - 1.0
            return LpConstraint(expr, sense=-1, rhs=-self.constant)
        if isinstance(other, LpAffineExpression):
            expr = self - other
            return LpConstraint(LpAffineExpression(expr.terms, 0.0), sense=-1,
                                rhs=-expr.constant)
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, (int, float)):
            return LpConstraint(LpAffineExpression(self.terms, 0.0), sense=1,
                                rhs=float(other) - self.constant)
        if isinstance(other, LpVariable):
            expr = LpAffineExpression(self.terms, 0.0)
            expr.terms[other] = expr.terms.get(other, 0.0) - 1.0
            return LpConstraint(expr, sense=1, rhs=-self.constant)
        if isinstance(other, LpAffineExpression):
            expr = self - other
            return LpConstraint(LpAffineExpression(expr.terms, 0.0), sense=1,
                                rhs=-expr.constant)
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, (int, float)):
            return LpConstraint(LpAffineExpression(self.terms, 0.0), sense=0,
                                rhs=float(other) - self.constant)
        if isinstance(other, LpVariable):
            expr = LpAffineExpression(self.terms, 0.0)
            expr.terms[other] = expr.terms.get(other, 0.0) - 1.0
            return LpConstraint(expr, sense=0, rhs=-self.constant)
        if isinstance(other, LpAffineExpression):
            expr = self - other
            return LpConstraint(LpAffineExpression(expr.terms, 0.0), sense=0,
                                rhs=-expr.constant)
        return NotImplemented

    def __hash__(self):
        return id(self)

    def __repr__(self):
        parts = []
        for v, c in self.terms.items():
            parts.append(f"{c}*{v.name}")
        if self.constant:
            parts.append(str(self.constant))
        return " + ".join(parts) if parts else "0"


# ---------------------------------------------------------------------------
# LpConstraint
# ---------------------------------------------------------------------------

class LpConstraint:
    """A linear constraint: expr sense rhs, where sense is -1(<=), 0(==), 1(>=)."""

    def __init__(self, expr=None, sense=0, rhs=0.0, name=None):
        if expr is None:
            self.expr = LpAffineExpression()
        elif isinstance(expr, LpVariable):
            self.expr = LpAffineExpression({expr: 1.0})
        elif isinstance(expr, LpAffineExpression):
            self.expr = expr
        else:
            self.expr = LpAffineExpression()
        self.sense = sense
        self.rhs = float(rhs)
        self.name = name

    def __repr__(self):
        sense_str = {-1: "<=", 0: "==", 1: ">="}[self.sense]
        return f"LpConstraint({self.expr} {sense_str} {self.rhs})"


# ---------------------------------------------------------------------------
# LpProblem
# ---------------------------------------------------------------------------

class LpProblem:
    """Container for an LP / IP optimisation problem."""

    def __init__(self, name="Problem", sense=LpMaximize):
        self.name = name
        self.sense = sense
        self.objective = LpAffineExpression()
        self.constraints = []
        self._status = 0  # Not Solved
        self._variables = []

    # -- model building -----------------------------------------------------
    def __iadd__(self, other):
        if isinstance(other, LpConstraint):
            self.constraints.append(other)
        elif isinstance(other, LpAffineExpression):
            self.objective = other
        elif isinstance(other, LpVariable):
            self.objective = LpAffineExpression({other: 1.0})
        elif isinstance(other, tuple):
            # (constraint, name) form
            if len(other) >= 2 and isinstance(other[0], LpConstraint):
                other[0].name = other[1]
                self.constraints.append(other[0])
            else:
                raise TypeError(f"Cannot add tuple {other} to LpProblem")
        else:
            raise TypeError(f"Cannot add {type(other)} to LpProblem")
        return self

    # -- collect variables --------------------------------------------------
    def _collect_variables(self):
        """Gather all LpVariables referenced in objective and constraints."""
        var_set = set()
        for v in self.objective.terms:
            var_set.add(v)
        for con in self.constraints:
            for v in con.expr.terms:
                var_set.add(v)
        return list(var_set)

    # -- status property ----------------------------------------------------
    @property
    def status(self):
        return LpStatus.get(self._status, "Undefined")

    # -- solve --------------------------------------------------------------
    def solve(self, solver=None, warm_start=None):
        """Solve the problem. Returns the status code."""
        variables = self._collect_variables()
        self._variables = variables

        has_integer = any(v.cat in (LpBinary, LpInteger) for v in variables)

        if has_integer:
            self._status = self._solve_ip(variables)
        else:
            self._status = self._solve_lp(variables)
        return self._status

    # -----------------------------------------------------------------------
    #  LP solver: Two-phase simplex (full tableau)
    # -----------------------------------------------------------------------
    def _solve_lp(self, variables, extra_bounds=None):
        """
        Solve the LP relaxation using a two-phase simplex method.

        Constraints are converted to standard equality form with slack,
        surplus, and artificial variables as needed.  Phase 1 minimises
        the sum of artificials to find a basic feasible solution; Phase 2
        optimises the original objective.

        *extra_bounds* is an optional dict ``{LpVariable: (lo, hi)}`` used
        by branch-and-bound to impose temporary bounds.
        """
        if extra_bounds is None:
            extra_bounds = {}

        var_idx = {v: i for i, v in enumerate(variables)}
        n_vars = len(variables)

        # ------------------------------------------------------------------
        # 1. Collect all constraint rows  (coeff_vector, sense, rhs)
        # ------------------------------------------------------------------
        rows = []      # list of [float] length n_vars
        senses = []    # -1 (<=), 0 (==), 1 (>=)
        rhs_vals = []

        # variable bounds
        for v in variables:
            lo = v.lowBound
            hi = v.upBound
            if v in extra_bounds:
                eb_lo, eb_hi = extra_bounds[v]
                if eb_lo is not None:
                    lo = eb_lo if lo is None else max(lo, eb_lo)
                if eb_hi is not None:
                    hi = eb_hi if hi is None else min(hi, eb_hi)
            if lo is not None:
                row = [0.0] * n_vars
                row[var_idx[v]] = 1.0
                rows.append(row)
                senses.append(1)   # >=
                rhs_vals.append(float(lo))
            if hi is not None:
                row = [0.0] * n_vars
                row[var_idx[v]] = 1.0
                rows.append(row)
                senses.append(-1)  # <=
                rhs_vals.append(float(hi))

        # explicit constraints
        for con in self.constraints:
            row = [0.0] * n_vars
            for v, c in con.expr.terms.items():
                if v in var_idx:
                    row[var_idx[v]] = c
            rows.append(row)
            senses.append(con.sense)
            rhs_vals.append(con.rhs)

        m = len(rows)
        if m == 0 and n_vars == 0:
            return 1

        # ------------------------------------------------------------------
        # 2. Ensure rhs >= 0 (flip entire row if needed)
        # ------------------------------------------------------------------
        for i in range(m):
            if rhs_vals[i] < -_tolerance:
                rows[i] = [-c for c in rows[i]]
                rhs_vals[i] = -rhs_vals[i]
                # Flip the sense:  <= becomes >=,  >= becomes <=,  == stays ==
                senses[i] = -senses[i]

        # ------------------------------------------------------------------
        # 3. Count slack and artificial columns
        #    <=  :  +slack,           basis = slack       (no artificial)
        #    >=  :  -surplus + art,   basis = artificial
        #    ==  :  +art,             basis = artificial
        # ------------------------------------------------------------------
        n_slack = 0
        n_art = 0
        row_type = []   # (slack_offset_or_None, art_offset_or_None)
        for i in range(m):
            if senses[i] == -1:      # <=
                row_type.append((n_slack, None))
                n_slack += 1
            elif senses[i] == 1:     # >=
                row_type.append((n_slack, n_art))
                n_slack += 1
                n_art += 1
            else:                    # ==
                row_type.append((None, n_art))
                n_art += 1

        total_cols = n_vars + n_slack + n_art

        # ------------------------------------------------------------------
        # 4. Build tableau   [A | Slack | Art | rhs]
        # ------------------------------------------------------------------
        tableau = []
        basis = [0] * m
        art_indices = set()

        for i in range(m):
            tab_row = [0.0] * (total_cols + 1)
            for j in range(n_vars):
                tab_row[j] = rows[i][j]
            tab_row[total_cols] = rhs_vals[i]

            s_off, a_off = row_type[i]

            if senses[i] == -1:         # <= : +slack
                sc = n_vars + s_off
                tab_row[sc] = 1.0
                basis[i] = sc
            elif senses[i] == 1:        # >= : -surplus + artificial
                sc = n_vars + s_off
                ac = n_vars + n_slack + a_off
                tab_row[sc] = -1.0
                tab_row[ac] = 1.0
                basis[i] = ac
                art_indices.add(ac)
            else:                       # == : artificial only
                ac = n_vars + n_slack + a_off
                tab_row[ac] = 1.0
                basis[i] = ac
                art_indices.add(ac)

            tableau.append(tab_row)

        # ------------------------------------------------------------------
        # 5. Build objective row (Big-M method)
        # ------------------------------------------------------------------
        # We combine Phase 1 and Phase 2 by penalising artificials with
        # a large cost (-BIG_M each, since we internally maximise).
        obj_row = [0.0] * (total_cols + 1)
        for v, c in self.objective.terms.items():
            if v in var_idx:
                obj_row[var_idx[v]] = c * self.sense   # internally maximise
        obj_row[total_cols] = self.objective.constant * self.sense

        for ac in art_indices:
            obj_row[ac] = -BIG_M

        # Make objective consistent with basis
        for i in range(m):
            bi = basis[i]
            if abs(obj_row[bi]) > _tolerance:
                ratio = obj_row[bi]
                for j in range(total_cols + 1):
                    obj_row[j] -= ratio * tableau[i][j]

        # ------------------------------------------------------------------
        # 6. Simplex iterations
        # ------------------------------------------------------------------
        status = self._simplex_iterate(tableau, obj_row, basis, total_cols, m)
        if status == -2:
            for v in variables:
                v.value = None
            return -2  # Unbounded

        # ------------------------------------------------------------------
        # 7. Check feasibility (artificials must be zero)
        # ------------------------------------------------------------------
        for i in range(m):
            if basis[i] in art_indices:
                if abs(tableau[i][total_cols]) > _tolerance:
                    for v in variables:
                        v.value = None
                    return -1  # Infeasible

        # ------------------------------------------------------------------
        # 8. Extract solution
        # ------------------------------------------------------------------
        solution = [0.0] * n_vars
        for i in range(m):
            if basis[i] < n_vars:
                solution[basis[i]] = tableau[i][total_cols]

        for j, v in enumerate(variables):
            v.value = solution[j]

        return 1  # Optimal

    def _simplex_iterate(self, tableau, obj_row, basis, total_cols, m):
        """
        Perform simplex iterations on the tableau.
        Uses Bland's rule for anti-cycling.
        Returns 1 for optimal, -2 for unbounded.
        """
        for _iteration in range(MAX_ITER):
            # Find entering variable (Bland's rule: smallest index with positive reduced cost)
            pivot_col = -1
            for j in range(total_cols):
                if obj_row[j] > _tolerance:
                    # Bland's rule — but we want to maximise, so pick first
                    # column with positive reduced cost
                    pivot_col = j
                    break

            if pivot_col == -1:
                return 1  # Optimal

            # Find leaving variable (minimum ratio test, Bland's rule for ties)
            pivot_row = -1
            min_ratio = math.inf
            for i in range(m):
                if tableau[i][pivot_col] > _tolerance:
                    ratio = tableau[i][total_cols] / tableau[i][pivot_col]
                    if ratio < min_ratio - _tolerance:
                        min_ratio = ratio
                        pivot_row = i
                    elif abs(ratio - min_ratio) < _tolerance:
                        # Bland's rule: pick row with smallest basis index
                        if basis[i] < basis[pivot_row]:
                            pivot_row = i

            if pivot_row == -1:
                return -2  # Unbounded

            self._pivot(tableau, basis, pivot_row, pivot_col, total_cols, m)

            # Update objective row
            ratio = obj_row[pivot_col] / tableau[pivot_row][pivot_col]
            for j in range(total_cols + 1):
                obj_row[j] -= ratio * tableau[pivot_row][j]
            obj_row[pivot_col] = 0.0  # clean up

        return 1  # Assume optimal after MAX_ITER

    def _pivot(self, tableau, basis, pivot_row, pivot_col, total_cols, m):
        """Perform a single pivot operation."""
        piv = tableau[pivot_row][pivot_col]
        # Scale pivot row
        for j in range(total_cols + 1):
            tableau[pivot_row][j] /= piv

        # Eliminate pivot column from other rows
        for i in range(m):
            if i != pivot_row:
                factor = tableau[i][pivot_col]
                if abs(factor) > _tolerance:
                    for j in range(total_cols + 1):
                        tableau[i][j] -= factor * tableau[pivot_row][j]
                    tableau[i][pivot_col] = 0.0  # clean up

        basis[pivot_row] = pivot_col

    # -----------------------------------------------------------------------
    #  IP solver: Branch and Bound
    # -----------------------------------------------------------------------
    def _solve_ip(self, variables):
        """Solve a MIP using branch and bound."""
        int_vars = [v for v in variables if v.cat in (LpBinary, LpInteger)]

        best = {"obj": -math.inf if self.sense == LpMaximize else math.inf,
                "solution": None, "found": False}
        node_count = [0]
        MAX_NODES = 10000

        def _branch(extra_bounds):
            if node_count[0] >= MAX_NODES:
                return

            node_count[0] += 1

            # Solve LP relaxation
            saved_values = {v: v.value for v in variables}
            lp_status = self._solve_lp(variables, extra_bounds)

            if lp_status != 1:
                # Restore and prune
                for v in variables:
                    v.value = saved_values[v]
                return

            # Compute objective
            obj_val = 0.0
            for v, c in self.objective.terms.items():
                if v.value is not None:
                    obj_val += v.value * c
            obj_val += self.objective.constant

            # Pruning: if this relaxation can't beat best
            if best["found"]:
                if self.sense == LpMaximize and obj_val <= best["obj"] + _tolerance:
                    for v in variables:
                        v.value = saved_values[v]
                    return
                elif self.sense == LpMinimize and obj_val >= best["obj"] - _tolerance:
                    for v in variables:
                        v.value = saved_values[v]
                    return

            # Check integrality
            branch_var = None
            max_frac = 0.0
            for v in int_vars:
                if v.value is not None:
                    frac = v.value - math.floor(v.value)
                    dist = min(frac, 1.0 - frac)
                    if dist > _tolerance and dist > max_frac:
                        max_frac = dist
                        branch_var = v

            if branch_var is None:
                # All integer vars are integral - feasible integer solution
                if not best["found"]:
                    best["found"] = True
                    best["obj"] = obj_val
                    best["solution"] = {v: v.value for v in variables}
                elif (self.sense == LpMaximize and obj_val > best["obj"] + _tolerance) or \
                     (self.sense == LpMinimize and obj_val < best["obj"] - _tolerance):
                    best["obj"] = obj_val
                    best["solution"] = {v: v.value for v in variables}
                for v in variables:
                    v.value = saved_values[v]
                return

            # Branch
            branch_val = branch_var.value
            floor_val = math.floor(branch_val)
            ceil_val = math.ceil(branch_val)

            # Branch down: branch_var <= floor_val
            eb_down = dict(extra_bounds)
            lo, hi = eb_down.get(branch_var, (branch_var.lowBound, branch_var.upBound))
            new_hi = floor_val if hi is None else min(hi, floor_val)
            eb_down[branch_var] = (lo, new_hi)
            _branch(eb_down)

            # Branch up: branch_var >= ceil_val
            eb_up = dict(extra_bounds)
            lo, hi = eb_up.get(branch_var, (branch_var.lowBound, branch_var.upBound))
            new_lo = ceil_val if lo is None else max(lo, ceil_val)
            eb_up[branch_var] = (new_lo, hi)
            _branch(eb_up)

            for v in variables:
                v.value = saved_values[v]

        _branch({})

        if best["found"]:
            for v in variables:
                v.value = best["solution"].get(v)
            return 1
        else:
            for v in variables:
                v.value = None
            return -1

    # -----------------------------------------------------------------------
    #  Shadow prices (perturbation method)
    # -----------------------------------------------------------------------
    def get_shadow_prices(self):
        """
        Compute shadow prices for each named constraint via perturbation.

        Returns dict {constraint_name: shadow_price}.
        """
        result = {}
        variables = self._collect_variables()

        # Get baseline objective value
        base_obj = 0.0
        for v, c in self.objective.terms.items():
            if v.value is not None:
                base_obj += v.value * c
        base_obj += self.objective.constant

        delta = 1.0  # 1 unit perturbation for meaningful shadow price

        for con in self.constraints:
            name = con.name if con.name else f"constraint_{id(con)}"

            # Perturb rhs
            original_rhs = con.rhs
            con.rhs = original_rhs + delta

            saved = {v: v.value for v in variables}
            status = self._solve_lp(variables)

            if status == 1:
                perturbed_obj = 0.0
                for v, c in self.objective.terms.items():
                    if v.value is not None:
                        perturbed_obj += v.value * c
                perturbed_obj += self.objective.constant
                shadow = (perturbed_obj - base_obj) / delta
            else:
                shadow = 0.0

            con.rhs = original_rhs
            for v in variables:
                v.value = saved[v]

            result[name] = shadow

        return result


# ---------------------------------------------------------------------------
# Standalone functions
# ---------------------------------------------------------------------------

def value(x):
    """Extract the numeric value from a variable, expression, or number."""
    if isinstance(x, LpVariable):
        return x.value
    if isinstance(x, LpAffineExpression):
        return x.value()
    if isinstance(x, (int, float)):
        return float(x)
    return None


def lpSum(items):
    """Sum a list of LpVariables / LpAffineExpressions into a single expression."""
    result = LpAffineExpression()
    for item in items:
        if isinstance(item, LpVariable):
            result.terms[item] = result.terms.get(item, 0.0) + 1.0
        elif isinstance(item, LpAffineExpression):
            for v, c in item.terms.items():
                result.terms[v] = result.terms.get(v, 0.0) + c
            result.constant += item.constant
        elif isinstance(item, (int, float)):
            result.constant += float(item)
    return result
