from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Column, String, Date, DateTime, Text, Index
from sqlalchemy.sql import func

from app.db import Base


class PepRecord(Base):
    """
    PEP Record (fonte de compliance interna/externa).

    Este modelo é pensado para:
    - bulk upload (JSON agora; Excel depois)
    - matching simples por BI / passaporte / nome
    - evoluir para múltiplas fontes e normalizações
    """
    __tablename__ = "pep_records"

    id = Column(String, primary_key=True)

    # Multi-tenant / scoping
    entity_id = Column(String, nullable=False, index=True)

    # Identificação do alvo
    full_name = Column(String, nullable=False, index=True)
    aka = Column(String, nullable=True)

    bi = Column(String, nullable=True, index=True)
    passport = Column(String, nullable=True, index=True)
    dob = Column(Date, nullable=True)
    nationality = Column(String, nullable=True)

    # Informação PEP (para relatório institucional)
    pep_category = Column(String, nullable=True)   # Ex: "Gov Executive", "SOE", "Judiciary", etc
    pep_role = Column(String, nullable=True)       # Cargo/posição
    country = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Classificação de risco da fonte (pode influenciar score)
    risk_level = Column(String, nullable=True)     # LOW|MEDIUM|HIGH

    # Proveniência
    source_name = Column(String, nullable=False, default="PEP_INTERNAL")
    source_ref = Column(String, nullable=True)     # ID externo, link, ref documento
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())


# Índices compostos úteis para matching rápido por entidade
Index("ix_pep_entity_bi_pass", PepRecord.entity_id, PepRecord.bi, PepRecord.passport)
Index("ix_pep_entity_name", PepRecord.entity_id, PepRecord.full_name)
