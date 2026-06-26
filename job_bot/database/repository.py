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


def migrate_schema(db_path: str):
    """Add new columns introduced in model changes. Safe to run multiple times."""
    from sqlalchemy import text
    engine = create_engine(f"sqlite:///{db_path}")
    new_cols = [
        "liveness_checked_at",
        "liveness_status",
        "score_cv_match", "score_compensation", "score_culture",
        "score_red_flags", "score_legitimacy", "score_global",
        "score_prose",
    ]
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info('opportunities')"))}
        for col in new_cols:
            if col not in existing:
                if col == "score_prose":
                    conn.execute(text(f"ALTER TABLE opportunities ADD COLUMN {col} TEXT"))
                else:
                    conn.execute(text(f"ALTER TABLE opportunities ADD COLUMN {col} FLOAT"))
        conn.commit()


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

    def get_pending_opportunities(self, min_score: float = 0.0, category: str | None = None) -> list:
        from sqlalchemy import or_
        with Session(self.engine) as session:
            query = session.query(Opportunity).filter(
                Opportunity.status == "new",
                or_(Opportunity.liveness_status.is_(None), Opportunity.liveness_status != "dead"),
                or_(Opportunity.score.is_(None), Opportunity.score >= min_score),
            )
            if category:
                query = query.filter(Opportunity.category == category)
            return query.all()

    def get_pending_opportunities_sorted(
        self, min_score: float = 0.0, category: str | None = None,
        limit: int = 50, sort_by: str = "score_desc",
    ) -> list:
        from sqlalchemy import or_
        with Session(self.engine) as session:
            query = session.query(Opportunity).filter(
                Opportunity.status == "new",
                or_(Opportunity.liveness_status.is_(None), Opportunity.liveness_status != "dead"),
                or_(Opportunity.score.is_(None), Opportunity.score >= min_score),
            )
            if category:
                query = query.filter(Opportunity.category == category)
            if sort_by == "score_desc":
                query = query.order_by(Opportunity.score.desc().nullslast())
            elif sort_by == "created_desc":
                query = query.order_by(Opportunity.created_at.desc())
            return query.limit(limit).all()

    def update_opportunity_status(self, opp_id: int, status: str) -> bool:
        with Session(self.engine) as session:
            record = session.query(Opportunity).filter_by(id=opp_id).first()
            if not record:
                return False
            record.status = status
            session.commit()
            return True

    def update_opportunity_liveness(self, opp_id: int, status: str, checked_at=None) -> bool:
        with Session(self.engine) as session:
            record = session.query(Opportunity).filter_by(id=opp_id).first()
            if not record:
                return False
            record.liveness_status = status
            record.liveness_checked_at = checked_at
            if status == "dead":
                record.status = "dead"
            session.commit()
            return True

    def update_opportunity_scores(self, opp_id: int, scores: dict) -> bool:
        with Session(self.engine) as session:
            record = session.query(Opportunity).filter_by(id=opp_id).first()
            if not record:
                return False
            record.score = scores.get("composite", 50) / 100.0
            record.score_cv_match = scores.get("cv_match")
            record.score_compensation = scores.get("compensation")
            record.score_culture = scores.get("culture")
            record.score_red_flags = scores.get("red_flags")
            record.score_legitimacy = scores.get("legitimacy")
            record.score_global = scores.get("global")
            record.score_prose = scores.get("prose")
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
                "dead": session.query(Opportunity).filter_by(status="dead").count(),
                "scored": session.query(Opportunity).filter(Opportunity.score.isnot(None)).count(),
                "unscored": session.query(Opportunity).filter(Opportunity.score.is_(None)).count(),
            }

    def get_stats_by_category(self) -> dict:
        with Session(self.engine) as session:
            cats = [row[0] for row in session.query(Opportunity.category).distinct() if row[0]]
            result = {}
            for cat in cats:
                result[cat] = session.query(Opportunity).filter(
                    Opportunity.category == cat
                ).count()
            return result
