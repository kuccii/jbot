import pytest
from httpx import AsyncClient, ASGITransport
from job_bot.dashboard.server import app


class TestDashboard:
    @pytest.mark.asyncio
    async def test_home_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code == 200
            assert "Dashboard" in resp.text

    @pytest.mark.asyncio
    async def test_opportunities_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/opportunities")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_review_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/review")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_settings_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/settings")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_applications_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/applications")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_opportunities_jobs_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/opportunities/job")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_opportunities_startup_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/opportunities/startup")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_opportunities_grant_page(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/opportunities/grant")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_stats_has_by_category(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/stats")
            data = resp.json()
            assert "by_category" in data

    @pytest.mark.asyncio
    async def test_review_page_with_category(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/review/job")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_daily_stats_api(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/stats/daily")
            assert resp.status_code == 200
            data = resp.json()
            assert "labels" in data
            assert "values" in data
