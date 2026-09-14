"""Separate presenter playback and download authorization."""


class RecordingAccess:
    def __init__(self, customer, session_ids):
        self.customer = customer
        self.session_ids = frozenset(session_ids)

    async def authorize(self, principal, manifest, purpose):
        return (
            principal.subject == "local-presenter"
            and principal.tenant == self.customer
            and manifest.identity.session_id in self.session_ids
            and purpose in {"view", "download"}
        )
