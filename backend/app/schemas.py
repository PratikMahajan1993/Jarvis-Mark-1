from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


WidgetType = Literal["kpi", "table", "markdown", "chart", "timeline", "quote", "attachments"]
AttachmentStatus = Literal["gmail", "local", "drive", "both"]


class MailAttachment(BaseModel):
    attachment_id: str = ""
    filename: str = ""
    mime: str = ""
    size: int = 0
    readable: bool = False
    cad: bool = False
    status: AttachmentStatus = "gmail"
    local_path: str | None = None
    local_name: str | None = None
    drive_link: str | None = None
    artifact_id: str | None = None


class Widget(BaseModel):
    type: WidgetType
    label: str | None = None
    value: Any = None
    hint: str | None = None
    title: str | None = None
    columns: list[str] | None = None
    rows: list[list[Any]] | None = None
    text: str | None = None
    chart_type: Literal["bar", "line"] | None = "bar"
    points: list[dict[str, Any]] | None = None
    items: list[dict[str, Any]] | None = None
    cite: str | None = None
    email_id: str | None = None


class Scene(BaseModel):
    title: str = "Command Center"
    subtitle: str | None = None
    widgets: list[Widget] = Field(default_factory=list)


class Artifact(BaseModel):
    id: str
    kind: str
    name: str
    path: str
    created_at: str


class PendingAction(BaseModel):
    id: str
    kind: str
    title: str
    summary: str
    payload: dict[str, Any]
    agent_id: str = ""
    tool_name: str = ""
    irreversibility: int = 2
    consequence: str = ""


class ActivityEvent(BaseModel):
    id: str = ""
    time: str = ""
    agent: str = ""
    message: str = ""


class AgentStatus(BaseModel):
    id: str
    code: str
    label: str = ""
    domain: str = ""
    state: str = ""


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class TtsRequest(BaseModel):
    text: str
    profile: str | None = None
    language: str = "en"


class MailAttachmentAction(BaseModel):
    session_id: str = "default"
    email_id: str = ""
    attachment_ids: list[str] = Field(default_factory=list)
    filenames: list[str] = Field(default_factory=list)


class MailReplyAttachmentAction(BaseModel):
    session_id: str = "default"
    email_id: str = ""
    attachment_ids: list[str] = Field(default_factory=list)
    filenames: list[str] = Field(default_factory=list)
    body: str = ""


class MarkedDrawingSave(BaseModel):
    session_id: str = "default"
    source_name: str = ""
    image_base64: str = ""


class ChatResponse(BaseModel):
    speak: str
    scene: Scene
    artifacts: list[Artifact] = Field(default_factory=list)
    pending: list[PendingAction] = Field(default_factory=list)
    attachments: list[MailAttachment] = Field(default_factory=list)
    mail_id: str | None = None
    reply: str = ""
    offline: bool = False
    more: int = 0
    watching: bool = False
    critical: dict[str, Any] | None = None
    activity: list[ActivityEvent] = Field(default_factory=list)
    agents: list[AgentStatus] = Field(default_factory=list)
    wake_reason: str | None = None
    # Thin semantic router stamp (orchestra code + coarse intent)
    target_agent: str | None = None
    route_intent: str | None = None
    ui_action: dict[str, Any] | None = None


class ConversationCreate(BaseModel):
    category: str = "drawing"
    title: str = "Conversation"
    focus: dict[str, Any] = Field(default_factory=dict)


class DiscussionCreate(BaseModel):
    title: str = ""
    focus: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreate(BaseModel):
    title: str = "Job"
    focus: dict[str, Any] = Field(default_factory=dict)
    resume_key: str = ""


class ConversationPatch(BaseModel):
    minimized: bool | None = None
    title: str | None = None
    status: str | None = None


class DrawingSpawn(BaseModel):
    filename: str = ""
    local_name: str = ""
    local_path: str = ""
    mime: str = ""
    drive_link: str = ""


class ConfirmRequest(BaseModel):
    action_id: str
    approved: bool
    session_id: str = "default"


class ComposeUpdateRequest(BaseModel):
    session_id: str = "default"
    to: str | None = None
    subject: str | None = None
    body: str | None = None


class Preferences(BaseModel):
    display_name: str = "Sir"
    assistant_name: str = "Jarvis"
    persona: str = "Dry, sharp, wickedly witty British aide — one crisp aside, then the answer; short enough to say aloud; never corporate, never clownish, never fawning."
    verbosity: Literal["concise", "normal", "detailed"] = "concise"
    timezone: str = "Asia/Kolkata"
    job_context: str = "Work operations: email, calendar, documents, research."
    sign_off: str = "Best regards"
    voice_enabled: bool = True
    email_enabled: bool = True
    calendar_enabled: bool = True
    files_enabled: bool = True
    research_enabled: bool = True
    hud_density: Literal["comfortable", "dense"] = "comfortable"


class PreferencesUpdate(BaseModel):
    display_name: str | None = None
    assistant_name: str | None = None
    persona: str | None = None
    verbosity: Literal["concise", "normal", "detailed"] | None = None
    timezone: str | None = None
    job_context: str | None = None
    sign_off: str | None = None
    voice_enabled: bool | None = None
    email_enabled: bool | None = None
    calendar_enabled: bool | None = None
    files_enabled: bool | None = None
    research_enabled: bool | None = None
    hud_density: Literal["comfortable", "dense"] | None = None


class HealthResponse(BaseModel):
    ok: bool
    ollama: bool = False
    model: str
    models: list[str] = Field(default_factory=list)
    model_ready: bool | None = None
    provider: str | None = None


class AuditEntry(BaseModel):
    id: int
    created_at: str
    session_id: str
    tool: str
    detail: str
    status: str


class CanvasCamera(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 1.0


class CanvasItem(BaseModel):
    """Geometry is fixed; anything kind-specific rides along and is stored as JSON,
    so a new item kind needs no schema or table change."""

    model_config = ConfigDict(extra="allow")

    id: str
    kind: str
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    rotation: float = 0.0
    z: int = 0


CANVAS_ITEM_BASE_FIELDS = set(CanvasItem.model_fields)


class CanvasBoard(BaseModel):
    id: str
    name: str = "Canvas"
    camera: CanvasCamera = Field(default_factory=CanvasCamera)
    items: list[CanvasItem] = Field(default_factory=list)


class CanvasBoardCreate(BaseModel):
    id: str | None = None
    name: str = "Canvas"


class CanvasBoardUpdate(BaseModel):
    name: str = "Canvas"
    camera: CanvasCamera = Field(default_factory=CanvasCamera)
    items: list[CanvasItem] = Field(default_factory=list)


class CanvasFile(BaseModel):
    file_id: str
    name: str
    mime: str = ""
    width: float = 0.0
    height: float = 0.0
    page_count: int = 0
