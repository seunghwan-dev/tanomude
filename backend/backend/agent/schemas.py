import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    workflow: str
    instruction: str
    fields: dict
    dedup_key: str | None = None


class Envelope(BaseModel):
    type: Literal["task_created", "execution_started", "execution_finished", "status_changed"]
    task_id: int
    seq: int
    ts: dt.datetime
    payload: dict


class ExecutionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attempt_no: int
    status: str
    final_screen: str | None
    trip_id: int | None
    trip_created: bool | None
    executed_steps: int
    errors: list | None
    correction_candidate: dict | None
    started_at: dt.datetime
    finished_at: dt.datetime | None


class TaskView(BaseModel):
    id: int
    dedup_key: str | None
    workflow: str
    instruction: str
    fields: dict
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    executions: list[ExecutionView]
