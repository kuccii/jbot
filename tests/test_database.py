from job_bot.database.models import Opportunity


class TestOpportunityModel:
    def test_new_columns_exist(self):
        cols = {c.name for c in Opportunity.__table__.columns}
        assert "liveness_status" in cols
        assert "liveness_checked_at" in cols
        assert "score_cv_match" in cols
        assert "score_compensation" in cols
        assert "score_culture" in cols
        assert "score_red_flags" in cols
        assert "score_legitimacy" in cols
        assert "score_global" in cols
        assert "score_prose" in cols

    def test_repository_add_and_get(self, db, sample_opportunity):
        oid = db.add_opportunity(sample_opportunity)
        assert oid > 0
        pending = db.get_pending_opportunities()
        assert len(pending) == 1

    def test_repository_dedup(self, db, sample_opportunity):
        oid1 = db.add_opportunity(sample_opportunity)
        oid2 = db.add_opportunity(sample_opportunity)
        pending = db.get_pending_opportunities()
        assert len(pending) == 1
        assert oid1 == oid2

    def test_update_opportunity_liveness_dead(self, db, sample_opportunity):
        oid = db.add_opportunity(sample_opportunity)
        db.update_opportunity_liveness(oid, "dead")
        opp = db.get_pending_opportunities()
        assert len(opp) == 0

    def test_update_opportunity_scores(self, db, sample_opportunity):
        oid = db.add_opportunity(sample_opportunity)
        scores = {
            "cv_match": 85, "compensation": 60, "culture": 70,
            "red_flags": 90, "legitimacy": 80, "global": 75,
            "prose": "Good fit", "composite": 76,
        }
        db.update_opportunity_scores(oid, scores)
        from sqlalchemy.orm import Session
        with Session(db.engine) as s:
            opp = s.query(Opportunity).filter_by(id=oid).first()
            assert opp.score_cv_match == 85
            assert opp.score_prose == "Good fit"
            assert opp.score == 0.76

    def test_get_stats_has_new_fields(self, db):
        stats = db.get_stats()
        assert "scored" in stats
        assert "dead" in stats
        assert "unscored" in stats

    def test_sorted_query(self, db, sample_opportunity):
        db.add_opportunity(sample_opportunity)
        opp2 = dict(sample_opportunity)
        opp2["url"] = "https://example.com/job/456"
        opp2["title"] = "Senior Engineer"
        db.add_opportunity(opp2)
        sorted_opps = db.get_pending_opportunities_sorted(sort_by="created_desc")
        assert len(sorted_opps) >= 2
