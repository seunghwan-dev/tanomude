from typing import Literal

from pydantic import BaseModel, Field


class KeyStep(BaseModel):
    type: Literal["field", "fkey", "nav"]
    target: str | None = None
    value: str | None = None
    key: str | None = None


class Screen(BaseModel):
    session_id: str | None = None
    screen: str
    fields: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    trip_id: int | None = None


class AssertSpec(BaseModel):
    screen: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    trip_saved: bool | None = None


class Diff(BaseModel):
    kind: Literal["screen", "field", "error_missing", "trip_saved"]
    key: str | None = None
    expected: str | None = None
    actual: str | None = None


class AssertResult(BaseModel):
    ok: bool
    diffs: list[Diff] = Field(default_factory=list)


def evaluate_assert(screen: Screen, spec: AssertSpec) -> AssertResult:
    diffs: list[Diff] = []
    if spec.screen is not None and spec.screen != screen.screen:
        diffs.append(Diff(kind="screen", expected=spec.screen, actual=screen.screen))
    for key, expected in spec.fields.items():
        actual = screen.fields.get(key)
        if actual != expected:
            diffs.append(Diff(kind="field", key=key, expected=expected, actual=actual))
    for expected_error in spec.errors:
        if expected_error not in screen.errors:
            diffs.append(Diff(kind="error_missing", key=expected_error, expected=expected_error, actual=None))
    if spec.trip_saved is not None:
        actual_saved = screen.trip_id is not None
        if actual_saved != spec.trip_saved:
            diffs.append(Diff(kind="trip_saved", expected=str(spec.trip_saved), actual=str(actual_saved)))
    return AssertResult(ok=len(diffs) == 0, diffs=diffs)
