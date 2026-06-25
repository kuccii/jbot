from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from job_bot.database.models import Base, Opportunity, Application, AuditLog


def init_db(db_path: str) -> str:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return f"sqlite:///{db_path}"


class Repository:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)

    def add_opportunity(self, opp: dict) -> int:
        with Session(self.engine) as session:
            existing = session.query(Opportunity).filter_by(url=opp.get("url")).first()
            if existing:
                return existing.id
            cols = [c.name for c in Opportunity.__table__.columns]
            record = Opportunity(**{k: v for k, v in opp.items() if k in cols})
            session.add(record)
            session.commit()
            return record.id

    def get_pending_opportunities(self, min_score: float = 0.0) -> list:
        from sqlalchemy import or_
        with Session(self.engine) as session:
            return session.query(Opportunity).filter(
                Opportunity.status == "new",
                or_(Opportunity.score.is_(None), Opportunity.score >= min_score),
            ).all()

    def update_opportunity_status(self, opp_id: int, status: str) -> bool:
        with Session(self.engine) as session:
            record = session.query(Opportunity).filter_by(id=opp_id).first()
            if not record:
                return False
            record.status = status
            session.commit()
            return True

    def add_application(self, app_data: dict) -> int:
        with Session(self.engine) as session:
            cols = [c.name for c in Application.__table__.columns]
            record = Application(**{k: v for k, v in app_data.items() if k in cols})
            session.add(record)
            session.commit()
            return record.id

    def log_audit(self, action: str, component: str, details: Optional[dict] = None):
        with Session(self.engine) as session:
            record = AuditLog(action=action, component=component, details=details or {})
            session.add(record)
            session.commit()

    def get_audit_logs(self, limit: int = 20) -> list:
        with Session(self.engine) as session:
            return session.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()

    def get_daily_trend(self, days: int = 14) -> dict:
        labels = []
        values = []
        from datetime import datetime, timedelta
        from sqlalchemy import func
        with Session(self.engine) as session:
            for i in range(days - 1, -1, -1):
                date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
                labels.append(date)
                count = session.query(Opportunity).filter(
                    func.date(Opportunity.created_at) == date
                ).count()
                values.append(count)
        return {"labels": labels, "values": values}

    def get_stats(self) -> dict:
        with Session(self.engine) as session:
            return {
                "total": session.query(Opportunity).count(),
                "new": session.query(Opportunity).filter_by(status="new").count(),
                "applied": session.query(Opportunity).filter_by(status="applied").count(),
                "rejected": session.query(Opportunity).filter_by(status="rejected").count(),
            }
