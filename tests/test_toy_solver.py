"""Tests for domain.toy_solver.

The LP is: maximize a*x + b*y subject to x + y >= 1 and x - y >= 1.
The feasible region has a single vertex at (1, 0) and recession cone
spanned by the rays (1, 1) and (1, -1). Hence the problem is bounded
iff a + b <= 0 and a - b <= 0 (i.e. a <= -|b|), in which case the
optimal objective is a. When a < -|b| the optimum (1, 0) is unique.
"""

from unittest import mock

from ortools.linear_solver import pywraplp
import pytest

from common import models
from domain import toy_solver

_TOL = 1e-6
_UNBOUNDED_STATUSES = {"UNBOUNDED", "INFEASIBLE_OR_UNBOUNDED"}


def _assert_feasible(x: float, y: float) -> None:
    assert x + y >= 1 - _TOL
    assert x - y >= 1 - _TOL


@pytest.mark.parametrize(
    "a, b",
    [(-1, 0), (-2, 1), (-2, -1), (-3, -1), (-10, 9.5)],
)
def test_unique_optimum_is_vertex(a: float, b: float) -> None:
    """When a < -|b| the unique optimum is the vertex (1, 0)."""
    result = toy_solver.solve(models.ToyInstance(a=a, b=b))

    assert result.status == "OPTIMAL"
    assert result.x == pytest.approx(1.0, abs=_TOL)
    assert result.y == pytest.approx(0.0, abs=_TOL)
    assert result.objective == pytest.approx(a, abs=_TOL)


@pytest.mark.parametrize("a, b", [(-1, 1), (-1, -1), (0, 0)])
def test_degenerate_optimum_has_correct_objective(a: float, b: float) -> None:
    """Optimal face is a ray (or the whole region), so only check value."""
    result = toy_solver.solve(models.ToyInstance(a=a, b=b))

    assert result.status == "OPTIMAL"
    assert result.x is not None and result.y is not None
    _assert_feasible(result.x, result.y)
    assert result.objective == pytest.approx(a, abs=_TOL)
    assert a * result.x + b * result.y == pytest.approx(
        result.objective, abs=_TOL
    )


@pytest.mark.parametrize(
    "a, b",
    [(1, 1), (1, -1), (0, 1), (0, -1), (-1, -2), (-1, 2), (1, 0)],
)
def test_unbounded_objective(a: float, b: float) -> None:
    """When a > -|b| the objective is unbounded and no values are set."""
    result = toy_solver.solve(models.ToyInstance(a=a, b=b))

    assert result.status in _UNBOUNDED_STATUSES
    assert result.x is None
    assert result.y is None
    assert result.objective is None


def test_raises_when_glop_unavailable() -> None:
    """A missing GLOP backend raises RuntimeError."""
    with mock.patch.object(pywraplp.Solver, "CreateSolver", return_value=None):
        with pytest.raises(RuntimeError, match="GLOP"):
            toy_solver.solve(models.ToyInstance(a=1, b=1))


@pytest.mark.parametrize(
    "solver_status, expected",
    [
        (pywraplp.Solver.UNBOUNDED, "UNBOUNDED"),
        (pywraplp.Solver.INFEASIBLE, "INFEASIBLE_OR_UNBOUNDED"),
        (pywraplp.Solver.FEASIBLE, "UNKNOWN"),
        (pywraplp.Solver.ABNORMAL, "UNKNOWN"),
        (pywraplp.Solver.NOT_SOLVED, "UNKNOWN"),
    ],
)
def test_status_mapping(solver_status: int, expected: str) -> None:
    """Each non-optimal solver status maps to the expected string."""
    with mock.patch.object(
        pywraplp.Solver, "Solve", return_value=solver_status
    ):
        result = toy_solver.solve(models.ToyInstance(a=-1, b=0))

    assert result == models.ToySolution(status=expected)


def test_solution_defaults_to_none() -> None:
    """ToySolution values default to None when only status is given."""
    solution = models.ToySolution(status="UNKNOWN")

    assert solution.x is None
    assert solution.y is None
    assert solution.objective is None
