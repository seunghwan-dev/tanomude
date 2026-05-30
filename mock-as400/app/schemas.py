import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TripApplicationCreate(BaseModel):
    dest: str = Field(min_length=1, max_length=12)
    dept_date: dt.date
    ret_date: dt.date
    days: int = Field(ge=1)
    purpose: str = Field(min_length=1, max_length=20)
    proj: str = Field(pattern=r"^P-\d{3}$")
    overseas: bool = False

    @model_validator(mode="after")
    def check_dates(self) -> "TripApplicationCreate":
        if self.ret_date < self.dept_date:
            raise ValueError("ret_date must not precede dept_date")
        return self


class TripApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dest: str
    dept_date: dt.date
    ret_date: dt.date
    days: int
    purpose: str
    proj: str
    overseas: bool
    created_at: dt.datetime


class StepIn(BaseModel):
    type: Literal["field", "fkey", "nav"]
    target: str | None = None
    value: str | None = None
    key: str | None = None


class SessionCreate(BaseModel):
    idempotency_key: str | None = None


class SessionStateOut(BaseModel):
    session_id: str
    screen: str
    fields: dict[str, str]
    errors: list[str]
    trip_id: int | None
    ready: bool = True
    trip_created: bool | None = None
