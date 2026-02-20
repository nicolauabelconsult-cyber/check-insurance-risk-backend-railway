from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class SourceRecord(Base):
    __tablename__ = "source_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Sector = Tenant (modelo atual do sistema)
    entity_id = Column(String, nullable=False, index=True)

    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # PEP | SANCTIONS | ADVERSE_MEDIA | WATCHLIST
    category = Column(String, nullable=False, index=True)

    # nome normalizado para matching rápido
    subject_name = Column(String, nullable=False, index=True)

    country = Column(String, nullable=True)

    # registo completo conforme CSV oficial
    raw = Column(JSONB, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    source = relationship("Source", backref="records")


Index(
    "ix_source_records_entity_cat_subject",
    SourceRecord.entity_id,
    SourceRecord.category,
    SourceRecord.subject_name,
)
