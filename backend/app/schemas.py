from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str
    password: str


class UserOut(BaseModel):
    id: int
    login: str

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: int
    code: str
    parent_id: int | None
    parent_code: str | None = None
    title: str
    description: str
    assignee: str
    duration_days: int
    start_date: date
    end_date: date
    sort_order: int
    last_changed_by: str
    updated_at: datetime | None = None
    predecessor_codes: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DependencyOut(BaseModel):
    id: int
    predecessor_task_id: int
    successor_task_id: int
    predecessor_code: str
    successor_code: str


class PlanOut(BaseModel):
    id: int
    title: str
    start_date: date
    updated_at: datetime | None = None
    tasks: list[TaskOut]
    dependencies: list[DependencyOut]
    undo_count: int = 0


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee: str | None = None
    duration_days: int | None = None
    start_date: date | None = None


class ChatRequest(BaseModel):
    message: str


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    job_id: int | None = None
    meta: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: int
    plan_id: int
    status: str
    request_text: str
    result_summary: str | None = None
    error: str | None = None
    changes: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    validate_ok: bool | None = None
    validate_errors: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tokens_input: int | None = None
    tokens_output: int | None = None
    undone_within_5m: bool = False
    rating: str | None = None
    rating_comment: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class RatingRequest(BaseModel):
    rating: Literal["up", "down"]
    comment: str | None = None


class AgentStatsOut(BaseModel):
    total: int
    success_rate: float
    validate_fail_rate: float
    undo_after_agent_rate: float
    avg_latency_ms: float | None
    ratings_up: int = 0
    ratings_down: int = 0


class HealthOut(BaseModel):
    status: str
    db: str
    llm: str
