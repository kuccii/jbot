import httpx
from job_bot.notifications.base import BaseNotifier


class WhatsAppNotifier(BaseNotifier):
    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, phone_number_id: str, token: str):
        self.phone_number_id = phone_number_id
        self.token = token

    async def send_message(self, to: str, text: str) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/{self.phone_number_id}/messages",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": text},
                },
            )
            return resp.status_code == 200

    async def send_template(self, to: str, template_name: str, params: dict) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/{self.phone_number_id}/messages",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": "en"},
                        "components": [{
                            "type": "body",
                            "parameters": [{"type": "text", "text": v} for v in params.values()],
                        }],
                    },
                },
            )
            return resp.status_code == 200
