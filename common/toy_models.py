"""Pydantic models exchanged with the toy solver.

Shared by the api, the worker and the solver.
"""

import pydantic


class ToyInstance(pydantic.BaseModel):
    """Input to the solver.

    Attributes:
        a: Objective coefficient of x.
        b: Objective coefficient of y.
    """

    a: float
    b: float


class ToySolution(pydantic.BaseModel):
    """Output of the solver.

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
