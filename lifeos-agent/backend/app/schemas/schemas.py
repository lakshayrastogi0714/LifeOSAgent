from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ScheduleBlockStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"


class UserProfileBase(BaseModel):
    display_name: str = "User"
    timezone: str = "UTC"
    working_hours_start: str = "09:00"
    working_hours_end: str = "17:00"
    preferred_break_minutes: int = 15
    default_task_duration_minutes: int = 60
    study_days: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    timezone: Optional[str] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    preferred_break_minutes: Optional[int] = None
    default_task_duration_minutes: Optional[int] = None
    study_days: Optional[List[int]] = None


class UserProfileResponse(UserProfileBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    category: str = "general"
    priority: TaskPriority = TaskPriority.MEDIUM
    deadline: Optional[datetime] = None
    estimated_duration_minutes: int = Field(default=60, ge=1, le=1440)


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    deadline: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = Field(None, ge=1, le=1440)
    actual_duration_minutes: Optional[int] = Field(None, ge=0)
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None


class TaskResponse(TaskBase):
    id: int
    user_id: int
    status: TaskStatus
    actual_duration_minutes: Optional[int] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleBlockBase(BaseModel):
    task_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    status: ScheduleBlockStatus = ScheduleBlockStatus.PLANNED


class ScheduleBlockCreate(ScheduleBlockBase):
    pass


class ScheduleBlockResponse(ScheduleBlockBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionBase(BaseModel):
    title: str = "New Conversation"


class ChatSessionCreate(ChatSessionBase):
    pass


class ChatSessionResponse(ChatSessionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageBase(BaseModel):
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ChatMessageCreate(ChatMessageBase):
    pass


class ChatMessageResponse(ChatMessageBase):
    id: int
    session_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentExecutionResponse(BaseModel):
    id: int
    session_id: int
    user_request: str
    tool_name: str
    arguments_json: Dict[str, Any]
    result_json: Optional[Dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyPlanRequest(BaseModel):
    date: Optional[datetime] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    preferred_break_minutes: Optional[int] = None


class WeeklyPlanRequest(BaseModel):
    start_date: Optional[datetime] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    preferred_break_minutes: Optional[int] = None


class ScheduleTaskRequest(BaseModel):
    task_id: int
    preferred_start: Optional[datetime] = None
    preferred_end: Optional[datetime] = None


class RescheduleTaskRequest(BaseModel):
    task_id: int
    new_start: Optional[datetime] = None
    new_end: Optional[datetime] = None
    protect_completed: bool = True


class ConflictDetectionResponse(BaseModel):
    conflicts: List[Dict[str, Any]]
    has_conflicts: bool


class DailyPlanResponse(BaseModel):
    date: datetime
    schedule_blocks: List[ScheduleBlockResponse]
    unscheduled_tasks: List[TaskResponse]
    total_planned_minutes: int
    available_minutes: int
    feasibility_note: Optional[str] = None


class WeeklyPlanResponse(BaseModel):
    week_start: datetime
    daily_plans: List[DailyPlanResponse]
    total_planned_hours: float
    total_available_hours: float


class BriefingResponse(BaseModel):
    date: datetime
    todays_tasks: List[TaskResponse]
    upcoming_deadlines: List[TaskResponse]
    overdue_tasks: List[TaskResponse]
    schedule_summary: str
    focus_recommendation: str


class InsightsResponse(BaseModel):
    completion_rate: float
    tasks_completed_this_week: int
    overdue_tasks_count: int
    planned_vs_available_hours: Dict[str, float]
    estimated_vs_actual_effort: Dict[str, float]
    productivity_trend: List[Dict[str, Any]]


class AIStatusResponse(BaseModel):
    provider: str
    model: Optional[str] = None
    available: bool
    demo_mode: bool
    error: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None


class ChatResponse(BaseModel):
    session_id: int
    message: ChatMessageResponse
    tool_calls: List[Dict[str, Any]] = []
    requires_confirmation: bool = False
    confirmation_details: Optional[Dict[str, Any]] = None


class ConfirmActionRequest(BaseModel):
    action: str
    parameters: Dict[str, Any]
    confirmed: bool


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None