"""A stand-in for httpx.AsyncClient that answers from a table of canned responses."""


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeAsyncClient:
    """Routes calls by (method, url) to `responses`, and records every request."""

    responses: dict = {}
    calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def _answer(self, method, url, **kwargs):
        type(self).calls.append((method, url, kwargs))
        payload = type(self).responses[(method, url)]
        if isinstance(payload, FakeResponse):
            return payload
        return FakeResponse(payload)

    async def get(self, url, **kwargs):
        return await self._answer("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self._answer("POST", url, **kwargs)


def fake_http(monkeypatch, module, responses):
    """Point `module.httpx.AsyncClient` at a fresh FakeAsyncClient serving `responses`."""
    client = type("Client", (FakeAsyncClient,), {"responses": responses, "calls": []})
    monkeypatch.setattr(module.httpx, "AsyncClient", client)
    return client
