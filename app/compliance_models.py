from __future__ import annotations

from sqlalchemy import Column, String, Date, DateTime, Text
from sqlalchemy.sql import text

from app.db import Base


class PepRecord(Base):
    __tablename__ = "pep_records"

    id = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False, index=True)

    full_name = Column(String, nullable=False, index=True)
    aka = Column(String, nullable=True)

    bi = Column(String, nullable=True, index=True)
    passport = Column(String, nullable=True, index=True)
    dob = Column(Date, nullable=True)
    nationality = Column(String, nullable=True)

    pep_category = Column(String, nullable=True)
    pep_role = Column(String, nullable=True)
    country = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    risk_level = Column(String, nullable=True)  # LOW|MEDIUM|HIGH

    source_name = Column(String, nullable=False, server_default=text("'PEP_INTERNAL'"))
    source_ref = Column(String, nullable=True)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=text("now()"))
