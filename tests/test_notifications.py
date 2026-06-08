import pytest
from job_bot.notifications.base import BaseNotifier


class FakeNotifier(BaseNotifier):
    async def send_message(self, to, text):
        return True
    async def send_template(self, to, name, params):
        return True


class TestNotifications:
    def test_fake_notifier(self):
        n = FakeNotifier()
        import asyncio
        assert asyncio.run(n.send_message("+123", "Hello"))

    def test_fake_template(self):
        n = FakeNotifier()
        import asyncio
        assert asyncio.run(n.send_template("+123", "test", {"key": "val"}))
