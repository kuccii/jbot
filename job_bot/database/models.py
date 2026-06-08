from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Opportunity(Base):
    __tablename__ = "opportunities"
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    company = Column(String(300), nullable=False)
    description = Column(Text)
    url = Column(String(2000))
    source = Column(String(100))
    deadline = Column(DateTime, nullable=True)
    salary_range = Column(String(200))
    location = Column(String(300))
    remote = Column(String(50))
    status = Column(String(50), default="new")
    score = Column(Float, nullable=True)
    matched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False)
    cover_letter = Column(Text)
    answers = Column(JSON)
    platform = Column(String(100))
    status = Column(String(50), default="draft")
    submitted_at = Column(DateTime, nullable=True)
    screenshot_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    action = Column(String(200), nullable=False)
    component = Column(String(100), nullable=False)
    details = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

Index("ix_opportunity_status_score", Opportunity.status, Opportunity.score)
Index("ix_audit_log_action", AuditLog.action)
