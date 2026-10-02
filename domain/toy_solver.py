"""Toy OR-Tools example.

maximize   a*x + b*y
subject to x + y >= 1
           x - y >= 1
"""

from ortools.linear_solver import pywraplp

from common import models


def solve(request: models.ToyInstance) -> models.ToySolution:
    """Solves the toy LP for the given objective coefficients.

    Args:
        request: The problem parameters.

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

    solver.Maximize(request.a * x + request.b * y)

    status = solver.Solve()

    if status == pywraplp.Solver.OPTIMAL:
        return models.ToySolution(
            status="OPTIMAL",
            x=x.solution_value(),
            y=y.solution_value(),
            objective=solver.Objective().Value(),
        )
    if status == pywraplp.Solver.UNBOUNDED:
        return models.ToySolution(status="UNBOUNDED")
    if status == pywraplp.Solver.INFEASIBLE:
        # NOTE: with x and y left unbounded (-inf, inf), GLOP reports
        # INFEASIBLE for problems that are actually UNBOUNDED (the feasible
        # region x+y>=1, x-y>=1 is never empty). Treat INFEASIBLE here as
        # "infeasible or unbounded" and, if that distinction matters,
        # re-check with finite variable bounds.
        return models.ToySolution(status="INFEASIBLE_OR_UNBOUNDED")
    return models.ToySolution(status="UNKNOWN")
