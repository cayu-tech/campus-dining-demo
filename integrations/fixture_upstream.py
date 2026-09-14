"""Read-only fixture transport. No socket, DNS resolution, or arbitrary URL forwarding."""

import asyncio

import httpx
from cayu.egress import CapturedResponse, EgressUpstreamOperation

from integrations.portal import build_portal


class FixturePortalUpstream:
    def __init__(self, settings, host):
        self.app = build_portal(settings)
        self.host = host

    def prepare(self, request, *, limits):
        # Cayu owns cancellation settlement; no detached transport task.
        return EgressUpstreamOperation(lambda: self.send(request, limits))

    async def send(self, request, limits):
        if request.host != self.host or request.method not in {"GET", "HEAD"} or request.body:
            return CapturedResponse(status_code=403, headers={}, body=b"Fixture destination denied")
        async with asyncio.timeout(limits.total_timeout_s):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app), follow_redirects=False
            ) as client:
                suffix = ("?" + request.query) if request.query else ""
                response = await client.request(
                    request.method, "https://" + self.host + request.path + suffix
                )
                if len(response.content) > limits.max_response_bytes:
                    raise ValueError("Fixture response exceeds admitted limit")
                return CapturedResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.content,
                )
