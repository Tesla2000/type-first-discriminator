from typing import Annotated
from typing import Any
from typing import Literal
from typing import Union

import pytest
from pydantic import BaseModel
from pydantic import TypeAdapter
from pydantic import ValidationError

from type_first_discriminator import TypeFirstDiscriminator


class A(BaseModel):
    type: Literal["a"] = "a"


class B(BaseModel):
    type: Literal["b"] = "b"
    other_field: str


class C(BaseModel):
    kind: Literal["c"] = "c"


class D(BaseModel):
    kind: Literal["d"] = "d"
    value: int


class Overlap(BaseModel):
    type: Literal["overlap"] = "overlap"
    name: str


class Specific(BaseModel):
    type: Literal["specific"] = "specific"
    name: str
    score: int


class RequiresX(BaseModel):
    type: Literal["x"] = "x"
    x: str


class RequiresY(BaseModel):
    type: Literal["y"] = "y"
    y: str


@pytest.fixture(scope="module")
def any_base() -> TypeAdapter:
    return TypeAdapter(Annotated[Union[A, B], TypeFirstDiscriminator()])


@pytest.fixture(scope="module")
def any_custom_field() -> TypeAdapter:
    return TypeAdapter(
        Annotated[Union[C, D], TypeFirstDiscriminator(type_field="kind")]
    )


@pytest.fixture(scope="module")
def any_smart_fallback() -> TypeAdapter:
    return TypeAdapter(
        Annotated[
            Union[Overlap, Specific],
            TypeFirstDiscriminator(mode_on_missing_type="smart"),
        ]
    )


@pytest.fixture(scope="module")
def any_all_required() -> TypeAdapter:
    return TypeAdapter(
        Annotated[Union[RequiresX, RequiresY], TypeFirstDiscriminator()]
    )


@pytest.fixture(scope="module")
def any_left_to_right_fallback() -> TypeAdapter:
    return TypeAdapter(
        Annotated[
            Union[Overlap, Specific],
            TypeFirstDiscriminator(mode_on_missing_type="left_to_right"),
        ]
    )


@pytest.mark.parametrize(
    "data,expected_type",
    [
        ({"type": "a"}, A),
        ({"type": "b", "other_field": "hello"}, B),
        (A(), A),
    ],
)
def test_dispatches_by_type_field(
    any_base: TypeAdapter, data: Any, expected_type: type
) -> None:
    assert isinstance(any_base.validate_python(data), expected_type)


def test_dispatches_json_by_type_field(any_base: TypeAdapter) -> None:
    assert isinstance(
        any_base.validate_json('{"type": "b", "other_field": "hello"}'), B
    )


def test_unknown_type_value_raises(any_base: TypeAdapter) -> None:
    with pytest.raises(ValidationError):
        any_base.validate_python({"type": "z"})


def test_missing_required_field_raises(any_base: TypeAdapter) -> None:
    with pytest.raises(ValidationError):
        any_base.validate_python({"type": "b"})


def test_falls_back_to_only_matching_type(any_base: TypeAdapter) -> None:
    assert isinstance(any_base.validate_python({"other_field": "hello"}), B)


def test_fallback_matches_first_type_with_all_optional_fields(
    any_base: TypeAdapter,
) -> None:
    assert isinstance(any_base.validate_python({"unknown_field": "x"}), A)


def test_fallback_raises_when_all_types_require_missing_field(
    any_all_required: TypeAdapter,
) -> None:
    with pytest.raises(ValidationError):
        any_all_required.validate_python({"unknown_field": "z"})


def test_smart_fallback_prefers_more_specific_match(
    any_smart_fallback: TypeAdapter,
) -> None:
    assert isinstance(
        any_smart_fallback.validate_python({"name": "x", "score": 1}), Specific
    )


def test_left_to_right_fallback_picks_first_match(
    any_left_to_right_fallback: TypeAdapter,
) -> None:
    assert isinstance(
        any_left_to_right_fallback.validate_python({"name": "x", "score": 1}),
        Overlap,
    )


@pytest.mark.parametrize(
    "data,expected_type",
    [
        ({"kind": "c"}, C),
        ({"kind": "d", "value": 42}, D),
        ({"value": 42}, D),
    ],
)
def test_custom_type_field(
    any_custom_field: TypeAdapter, data: Any, expected_type: type
) -> None:
    assert isinstance(any_custom_field.validate_python(data), expected_type)


def test_custom_callable_discriminator() -> None:
    adapter = TypeAdapter(
        Annotated[
            Union[A, B],
            TypeFirstDiscriminator(
                discriminator=lambda data: (
                    data.get("type") if isinstance(data, dict) else None
                )
            ),
        ]
    )
    assert isinstance(adapter.validate_python({"type": "a"}), A)
