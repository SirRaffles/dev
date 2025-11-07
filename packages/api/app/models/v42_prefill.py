"""Database models for V42 AI Prefills."""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean,
    ForeignKey, Index, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref

Base = declarative_base()


class V42AIPrefill(Base):
    """AI-generated prefill for form questions.

    This model stores pre-filled answers to form questions based on AI analysis
    of company data. Optimized for efficient querying with proper eager loading
    of related data to avoid N+1 query patterns.
    """
    __tablename__ = 'v42_ai_prefills'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    question_id = Column(String(255), nullable=False, index=True)
    section = Column(String(100), nullable=False)
    prefilled_value = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    is_validated = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships with lazy loading configuration
    # Use 'selectinload' strategy for optimal bulk loading
    sources = relationship(
        "PrefillSource",
        back_populates="prefill",
        lazy="select",  # Changed from 'selectin' to allow explicit control
        cascade="all, delete-orphan"
    )

    validation_history = relationship(
        "ValidationHistory",
        back_populates="prefill",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="ValidationHistory.validated_at.desc()"
    )

    def __repr__(self):
        return f"<V42AIPrefill(id={self.id}, session={self.session_id}, question={self.question_id})>"

    # Composite indexes for common query patterns
    __table_args__ = (
        Index('idx_session_company', 'session_id', 'company_name'),
        Index('idx_session_question', 'session_id', 'question_id'),
        Index('idx_company_section', 'company_name', 'section'),
    )


class PrefillSource(Base):
    """Source document/data used to generate a prefill."""
    __tablename__ = 'prefill_sources'

    id = Column(Integer, primary_key=True, autoincrement=True)
    prefill_id = Column(Integer, ForeignKey('v42_ai_prefills.id'), nullable=False, index=True)
    source_type = Column(String(50), nullable=False)  # e.g., 'document', 'database', 'api'
    source_name = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=True)
    relevance_score = Column(Float, nullable=True)
    excerpt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship back to prefill
    prefill = relationship("V42AIPrefill", back_populates="sources")

    def __repr__(self):
        return f"<PrefillSource(id={self.id}, type={self.source_type}, name={self.source_name})>"

    __table_args__ = (
        Index('idx_prefill_source', 'prefill_id', 'source_type'),
    )


class ValidationHistory(Base):
    """History of user validations/edits to prefills."""
    __tablename__ = 'validation_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    prefill_id = Column(Integer, ForeignKey('v42_ai_prefills.id'), nullable=False, index=True)
    user_id = Column(String(255), nullable=False)
    action = Column(String(50), nullable=False)  # 'accepted', 'rejected', 'modified'
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)
    validated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship back to prefill
    prefill = relationship("V42AIPrefill", back_populates="validation_history")

    def __repr__(self):
        return f"<ValidationHistory(id={self.id}, action={self.action}, user={self.user_id})>"

    __table_args__ = (
        Index('idx_prefill_validation', 'prefill_id', 'validated_at'),
        Index('idx_user_action', 'user_id', 'action'),
    )
