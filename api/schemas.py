from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AnalyzeRequest(BaseModel):
    cluster_id: str
    namespace: str
    pod_name: str
    reason: Optional[str] = "unknown"  # Kubernetes failure reason (e.g. CrashLoopBackOff)

class AnalyzeResponse(BaseModel):
    incident_id: str
    pod_name: Optional[str] = None
    namespace: Optional[str] = None
    incident_type: Optional[str] = None
    root_cause: Optional[str] = None
    confidence: Optional[str] = None
    recommended_action: Optional[str] = None
    explanation: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = None
    status: Optional[str] = None
    message: Optional[str] = None

class ApproveRequest(BaseModel):
    incident_id: str
    action: str
    approved_by: str
    approved: bool = True

class ApproveResponse(BaseModel):
    incident_id: str
    execution_status: str
    validation_result: Optional[str] = None
    message: str
    recommended_action: Optional[str] = None
    namespace: Optional[str] = None
    pod_name: Optional[str] = None

class IncidentSummary(BaseModel):
    id: str
    timestamp: datetime
    cluster_id: str
    namespace: str
    pod_name: str
    incident_type: str
    root_cause: Optional[str]
    confidence: Optional[str]
    recommended_action: Optional[str] = None
    explanation: Optional[str] = None
    status: str
    resolution_time: Optional[int]
    ai_used: bool

class ClusterStatusResponse(BaseModel):
    cluster_id: str
    healthy_pods: int
    failing_pods: int
    active_incidents: int
    total_nodes: int = 1
    total_namespaces: int = 1
    cpu_usage_pct: float = 0.0
    memory_usage_pct: float = 0.0

class PlaybookDetails(BaseModel):
    name: str
    description: str
    trigger: str
    steps: List[str]

class PlaybookResponse(BaseModel):
    name: str
    content: str
    details: Optional[PlaybookDetails] = None

class TokenRequest(BaseModel):
    username: str
    password: str  # Required — no free token issuance
    role: str = "viewer"  # Ignored by server; role is determined by credentials

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
