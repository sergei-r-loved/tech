from typing import Self

from pydantic import BaseModel


class CustomBaseModel(BaseModel):
    @classmethod
    def from_tuple(cls, values: tuple) -> Self:
        fields = cls.model_fields

        if len(fields) != len(values):
            raise ValueError(f"Expected {len(fields)} values, got {len(values)}")

        return cls(**dict(zip(fields, values)))
