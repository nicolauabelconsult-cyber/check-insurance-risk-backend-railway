from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RoleEnum(str, Enum):
    admin = "admin"
    analyst = "analyst"


class SourceTypeEnum(str, Enum):
    PEP = "PEP"
    SANCTIONS = "SANCTIONS"
    FRAUD = "FRAUD"
    CLAIMS = "CLAIMS"
    OTHER = "OTHER"


class RiskLevelEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DecisionEnum(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    UNDER_REVIEW = "UNDER_REVIEW"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)


class RiskCheckRequest(BaseModel):
    full_name: Optional[str] = None
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    nationality: Optional[str] = None
    notes: Optional[str] = None


class DecisionRequest(BaseModel):
    decision: DecisionEnum
    notes: Optional[str] = None


class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    role: RoleEnum
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None


class LoginResponse(BaseModel):
    success: bool
    token: str
    user: UserInfo


class RiskAnalysisInfo(BaseModel):
    id: int
    full_name: Optional[str] = None
    risk_level: Optional[RiskLevelEnum] = None
    risk_score: Optional[int] = None
    analyzed_at: Optional[datetime] = None
    decision: Optional[DecisionEnum] = None
    analyst_name: Optional[str] = None


class DashboardStats(BaseModel):
    totalAnalyses: int
    pendingReview: int
    highRiskCases: int
    activeSources: int
    recentAnalyses: List[RiskAnalysisInfo]
    riskDistribution: Optional[Dict[str, int]] = None


class RiskCheckResponse(BaseModel):
    success: bool
    id: int
    risk_score: int
    risk_level: RiskLevelEnum
    matches: List[Dict[str, Any]]
    risk_factors: List[str]
    analyzed_at: datetime


class InfoSourceInfo(BaseModel):
    id: int
    name: str
    source_type: SourceTypeEnum
    file_type: Optional[str] = None
    num_records: int = 0
    uploaded_at: datetime
    uploaded_by_name: Optional[str] = None
    is_active: bool = True
