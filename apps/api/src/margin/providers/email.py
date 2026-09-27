import httpx


class ResendProvider:
    def __init__(self, token, client=None):
        self.token = token
        self.client = client or httpx.Client(timeout=30)

    def send(self, recipient, subject, html, idempotency_key, sender):
        response = self.client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {self.token}", "Idempotency-Key": idempotency_key},
            json={"from": sender, "to": [recipient], "subject": subject, "html": html},
        )
        response.raise_for_status()
        return response.json()["id"]
