from collections.abc import Hashable
from dataclasses import dataclass
from dataclasses import field
from typing import Annotated
from typing import Any
from typing import Callable
from typing import Literal
from typing import Union

from pydantic import BaseModel
from pydantic import Discriminator
from pydantic import Field
from pydantic import GetCoreSchemaHandler
from pydantic import PydanticUserError
from pydantic import TypeAdapter
from pydantic_core import core_schema

_DEFAULT_TAG = object()


@dataclass(slots=True, frozen=True)
class TypeFirstDiscriminator(Discriminator):
    discriminator: str | Callable[[Any], Hashable] | None = field(default=None)
    type_field: str = "type"
    mode_on_missing_type: Literal["smart", "left_to_right"] = "smart"

    def __post_init__(self) -> None:
        if self.discriminator is not None:
            return

        def _default_discriminator(data: Any) -> Hashable:
            if isinstance(data, dict):
                return data.get(self.type_field, _DEFAULT_TAG)
            return getattr(data, self.type_field, _DEFAULT_TAG)

        object.__setattr__(self, "discriminator", _default_discriminator)

    def _convert_schema(
        self,
        original_schema: core_schema.CoreSchema,
        handler: GetCoreSchemaHandler | None = None,
    ) -> core_schema.TaggedUnionSchema:
        if original_schema["type"] != "union":
            # This likely indicates that the schema was a single-item union that was simplified.
            # In this case, we do the same thing we do in
            # `pydantic._internal._discriminated_union._ApplyInferredDiscriminator._apply_to_root`, namely,
            # package the generated schema back into a single-item union.
            original_schema = core_schema.union_schema([original_schema])

        tagged_union_choices = {}
        for choice in original_schema["choices"]:
            tag = None
            if isinstance(choice, tuple):
                choice, tag = choice
            metadata = choice.get("metadata")
            if metadata is not None:
                tag = metadata.get("pydantic_internal_union_tag_key") or tag
            if tag is None:
                # `handler` is None when this method is called from `apply_discriminator()` (deferred discriminators)
                if handler is not None and choice["type"] == "definition-ref":
                    # If choice was built from a PEP 695 type alias, try to resolve the def:
                    try:
                        choice = handler.resolve_ref_schema(choice)
                    except LookupError:
                        pass
                    else:
                        metadata = choice.get("metadata")
                        if metadata is not None:
                            tag = metadata.get(
                                "pydantic_internal_union_tag_key"
                            )

                if tag is None:
                    choice_class = choice.get("cls")
                    if not isinstance(choice_class, type) or not issubclass(
                        choice_class, BaseModel
                    ):
                        PydanticUserError(
                            f"`Tag` not provided for choice {choice} used with `Discriminator`",
                            code="callable-discriminator-no-tag",
                        )
                    tag = choice_class.model_fields[self.type_field].default
            tagged_union_choices[tag] = choice
        tagged_union_choices[_DEFAULT_TAG] = TypeAdapter(
            Annotated[
                Union.__getitem__(tuple(tagged_union_choices.values())),
                Field(union_mode=self.mode_on_missing_type),
            ]
        ).core_schema
        # Have to do these verbose checks to ensure falsy values ('' and {}) don't get ignored
        custom_error_type = self.custom_error_type
        if custom_error_type is None:
            custom_error_type = original_schema.get("custom_error_type")

        custom_error_message = self.custom_error_message
        if custom_error_message is None:
            custom_error_message = original_schema.get("custom_error_message")

        custom_error_context = self.custom_error_context
        if custom_error_context is None:
            custom_error_context = original_schema.get("custom_error_context")

        custom_error_type = (
            original_schema.get("custom_error_type")
            if custom_error_type is None
            else custom_error_type
        )
        return core_schema.tagged_union_schema(
            tagged_union_choices,
            self.discriminator,
            custom_error_type=custom_error_type,
            custom_error_message=custom_error_message,
            custom_error_context=custom_error_context,
            strict=original_schema.get("strict"),
            ref=original_schema.get("ref"),
            metadata=original_schema.get("metadata"),
            serialization=original_schema.get("serialization"),
        )
