from pydantic import BaseModel
from typing import Optional

class InfoSourceRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    row_count: Optional[int] = None

    class Config:
        from_attributes = True
