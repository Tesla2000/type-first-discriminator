import typing
from typing import Annotated
from typing import Literal
from typing import TypeVar
from typing import Union

from pydantic import AfterValidator
from pydantic import BaseModel
from pydantic import Field

T = TypeVar("T", bound=typing._UnionGenericAlias)


def _validate_unique(
    alternative_union_modes: tuple[Literal["smart", "left_to_right"], ...],
) -> tuple[Literal["smart", "left_to_right"], ...]:
    if len(set(alternative_union_modes)) != len(alternative_union_modes):
        raise ValueError(f"There are duplicates in {alternative_union_modes=}")
    return alternative_union_modes


class CompositeDiscriminator(BaseModel, frozen=True):
    discriminator_type: str = "type"
    alternative_union_modes: Annotated[
        tuple[Literal["smart", "left_to_right"], ...],
        Field(min_length=1),
        AfterValidator(_validate_unique),
    ] = ("smart",)

    def __call__(self, type_union: T) -> T:
        if not isinstance(type_union, typing._UnionGenericAlias):
            raise ValueError(f"{type_union=} is not a union type")
        return Annotated[
            Union.__getitem__(
                (
                    Annotated[
                        type_union,
                        Field(discriminator=self.discriminator_type),
                    ],
                    *tuple(
                        Annotated[type_union, Field(union_mode=union_mode)]
                        for union_mode in self.alternative_union_modes
                    ),
                )
            ),
            Field(union_mode="left_to_right"),
        ]


TYPE_FIRST_DISCRIMINATOR = CompositeDiscriminator()
