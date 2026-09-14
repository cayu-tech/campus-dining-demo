"""View-only access to an explicit application-owned session allowlist."""

from cayu import BrowserControlPolicy, BrowserControlPolicyResult


class ViewOnly(BrowserControlPolicy):
    identity = "campus-demo-view-only:2026-09-08.1"

    def __init__(self, settings, session_ids):
        self.customer = settings.customer
        self.session_ids = frozenset(session_ids)

    async def decide(self, request):
        return BrowserControlPolicyResult(allowed=(
            request.principal.subject == "local-presenter"
            and request.principal.tenant == self.customer
            and request.identity.session_id in self.session_ids
            and request.identity.environment_name == "demo-browser"
            and request.action == "view"
        ))
