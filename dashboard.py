from pydantic import BaseModel
from typing import Optional

class DashboardStats(BaseModel):
    total_clients: Optional[int] = None
    total_analyses: Optional[int] = None
    high_risk: Optional[int] = None
    medium_risk: Optional[int] = None
    low_risk: Optional[int] = None
    critical_risk: Optional[int] = None
