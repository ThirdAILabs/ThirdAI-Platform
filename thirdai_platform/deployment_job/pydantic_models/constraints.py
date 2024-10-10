"""
Defines constraint models for Pydantic validation.
"""

from typing import Any, Dict, Iterable, Union

from pydantic import BaseModel, Field, RootModel
from typing_extensions import Annotated, Literal


class AnyOf(BaseModel):
    """
    Represents a constraint where the value must be one of the specified values.
    """

    constraint_type: Literal["AnyOf"]
    values: Iterable[Any]


class EqualTo(BaseModel):
    """
    Represents a constraint where the value must be equal to the specified value.
    """

    constraint_type: Literal["EqualTo"]
    value: Any


class InRange(BaseModel):
    """
    Represents a constraint where the value must be within the specified range.
    """

    constraint_type: Literal["InRange"]
    minimum: Any
    maximum: Any
    inclusive_min: bool = True
    inclusive_max: bool = True


class GreaterThan(BaseModel):
    """
    Represents a constraint where the value must be greater than the specified minimum.
    """

    constraint_type: Literal["GreaterThan"]
    minimum: Any
    include_equal: bool = False


class LessThan(BaseModel):
    """
    Represents a constraint where the value must be less than the specified maximum.
    """

    constraint_type: Literal["LessThan"]
    maximum: Any
    include_equal: bool = False


class Constraints(RootModel):
    """
    Root model for a collection of constraints.
    """

    root: Dict[
        str,
        Annotated[
            Union[AnyOf, EqualTo, InRange, GreaterThan, LessThan],
            Field(discriminator="constraint_type"),
        ],
    ] = {}
