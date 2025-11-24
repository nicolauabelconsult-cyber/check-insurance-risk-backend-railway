from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel


class RoleEnum(str, Enum):
    admin = "ADMIN"
    analyst = "ANALYST"


class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    role: RoleEnum
    last_login: Optional[datetime] = None
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: str
    user: UserInfo


class RiskAnalysisInfo(BaseModel):
    id: int
    full_name: Optional[str] = None
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    analyzed_at: Optional[datetime] = None
    decision: Optional[str] = None
    analyst_name: Optional[str] = None


class DashboardStats(BaseModel):
    totalAnalyses: int
    pendingReview: int
    highRiskCases: int
    activeSources: int
    recentAnalyses: List[RiskAnalysisInfo]
    riskDistribution: Dict[str, int]


class SourceTypeEnum(str, Enum):
    pep_list = "PEP_LIST"
    sanctions = "SANCTIONS"
    internal = "INTERNAL"
    other = "OTHER"


class InfoSourceInfo(BaseModel):
    id: int
    name: str
    source_type: str
    file_type: str
    num_records: int
    uploaded_at: datetime
    uploaded_by: Optional[int] = None
    uploaded_by_name: Optional[str] = None
    is_active: bool


class RiskCheckRequest(BaseModel):
    full_name: Optional[str] = None
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    nationality: Optional[str] = None
    notes: Optional[str] = None


class RiskCheckResponse(BaseModel):
    success: bool
    id: int
    risk_score: float
    risk_level: str
    matches: list
    risk_factors: List[str]
    analyzed_at: datetime


class DecisionEnum(str, Enum):
    approved = "APPROVED"
    rejected = "REJECTED"
    under_review = "UNDER_REVIEW"


class DecisionRequest(BaseModel):
    decision: DecisionEnum
    notes: Optional[str] = None
