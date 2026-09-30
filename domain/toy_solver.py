"""Toy OR-Tools example.

maximize   a*x + b*y
subject to x + y >= 1
           x - y >= 1
"""

import dataclasses

from ortools.linear_solver import pywraplp


@dataclasses.dataclass
class Solution:
    """Outcome of a solve.

    Attributes:
        status: Solver status, e.g. "OPTIMAL" or "UNBOUNDED".
        x: Optimal value of x, if an optimum was found.
        y: Optimal value of y, if an optimum was found.
        objective: Optimal objective value, if an optimum was found.
    """

    status: str
    x: float | None = None
    y: float | None = None
    objective: float | None = None


def solve(a: float, b: float) -> Solution:
    """Solves the toy LP for the given objective coefficients.

    Args:
        a: Objective coefficient of x.
        b: Objective coefficient of y.

    Returns:
        The solution, with values set only when the status is OPTIMAL.

    Raises:
        RuntimeError: If the GLOP solver is unavailable.
    """
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
        return Solution(
            "OPTIMAL",
            x.solution_value(),
            y.solution_value(),
            solver.Objective().Value(),
        )
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


def main() -> None:
    """Solves a few sample objectives and prints the results."""
    for a, b in [(1, 1), (1, -1), (-1, 1), (-1, -2)]:
        result = solve(a, b)
        print(f"a={a}, b={b} -> {result}")


if __name__ == "__main__":
    main()
