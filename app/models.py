# app/models_compliance.py (novo ficheiro) OU dentro do app/models.py

from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db import Base  # ajusta se o teu Base estiver noutro sítio

class ComplianceRecord(Base):
    __tablename__ = "compliance_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_id = Column(String, index=True, nullable=False)

    category = Column(String, index=True, nullable=False)       # PEP | SANCTIONS | WATCHLIST | ADVERSE_MEDIA
    source_system = Column(String, index=True, nullable=False)  # OFAC | UN | EU | INTERNAL | ...

    source_ref = Column(String, index=True, nullable=True)      # id original da fonte
    full_name = Column(String, index=True, nullable=False)
    nationality = Column(String, nullable=True)
    dob = Column(String, nullable=True)
    id_number = Column(String, nullable=True)

    aliases = Column(JSONB, nullable=True)
    risk_level = Column(String, nullable=True)

    raw = Column(JSONB, nullable=True)  # payload completo da fonte (auditoria)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ComplianceHit(Base):
    __tablename__ = "compliance_hits"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_id = Column(String, index=True, nullable=False)
    risk_id = Column(String, index=True, nullable=False)  # se tiveres FK Risk.id, mete ForeignKey

    category = Column(String, index=True, nullable=False)
    source_system = Column(String, index=True, nullable=False)

    record_id = Column(String, index=True, nullable=False)  # ideal: ForeignKey(compliance_records.id)
    match_score = Column(Integer, nullable=False, default=0)

    match_reason = Column(JSONB, nullable=True)  # ex: {"name":0.92,"doc":1.0}
    snapshot = Column(JSONB, nullable=True)      # cópia do record na data (prova)

    matched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
