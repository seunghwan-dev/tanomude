import datetime as dt

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
