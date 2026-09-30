"""Toy OR-Tools example.

maximize   a*x + b*y
subject to x + y >= 1
           x - y >= 1
"""

from dataclasses import dataclass

from ortools.linear_solver import pywraplp


@dataclass
class Solution:
    status: str
    x: float | None = None
    y: float | None = None
    objective: float | None = None


def solve(a: float, b: float) -> Solution:
    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        raise RuntimeError("GLOP solver unavailable")

    infinity = solver.infinity()
    x = solver.NumVar(-infinity, infinity, "x")
    y = solver.NumVar(-infinity, infinity, "y")

    solver.Add(x + y >= 1)
    solver.Add(x - y >= 1)

    solver.Maximize(a * x + b * y)

    status = solver.Solve()

    if status == pywraplp.Solver.OPTIMAL:
        return Solution("OPTIMAL", x.solution_value(), y.solution_value(), solver.Objective().Value())
    if status == pywraplp.Solver.UNBOUNDED:
        return Solution("UNBOUNDED")
    if status == pywraplp.Solver.INFEASIBLE:
        # NOTE: with x and y left unbounded (-inf, inf), GLOP reports
        # INFEASIBLE for problems that are actually UNBOUNDED (the feasible
        # region x+y>=1, x-y>=1 is never empty). Treat INFEASIBLE here as
        # "infeasible or unbounded" and, if that distinction matters,
        # re-check with finite variable bounds.
        return Solution("INFEASIBLE_OR_UNBOUNDED")
    return Solution("UNKNOWN")


if __name__ == "__main__":
    for a, b in [(1, 1), (1, -1), (-1, 1), (-1, -2)]:
        result = solve(a, b)
        print(f"a={a}, b={b} -> {result}")
