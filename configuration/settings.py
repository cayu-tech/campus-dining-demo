"""The only ambient environment reader; no credentials are read from shell files."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCAFFOLDED_PROVIDER = "openai"
SCAFFOLDED_DATABASE = "sqlite"
RUNTIME_SHA = "c5816d06f2555bf85cbb8f22f27e9b94e85f0c2b"
# A transition includes old-worker shutdown, Python imports, and new-worker startup.
PRESENTER_STARTUP_SECONDS = 120
PRESENTER_TRANSITION_SECONDS = 180
CUSTOMERS = {"north-campus": "North Campus Dining", "south-campus": "South Campus Dining"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path | None = None
    customer: str = "north-campus"
    model: str = "gpt-5.6-sol"
    browser: bool = False
    seccomp_path: Path | None = None
    viewer_state: Path | None = None

    def __post_init__(self):
        if self.data_dir is None:
            object.__setattr__(self, "data_dir", ROOT / "data")
        if self.seccomp_path is None:
            object.__setattr__(
                self, "seccomp_path", ROOT / "browser-worker/seccomp_profile.json"
            )
        if self.customer not in CUSTOMERS:
            raise ValueError("Unknown synthetic customer")

    @property
    def namespace(self):
        return f"demo:customer:{self.customer}"

    @property
    def database(self):
        return self.data_dir / f"cayu-{self.customer}.db"

    @property
    def portal_database(self):
        return self.data_dir / "portal.db"

    def evidence_key(self):
        path = self.data_dir / "memory-evidence.key"
        if not path.is_file():
            raise RuntimeError("Run `python demo.py init` before constructing the application")
        return path.read_text().strip()


def settings_from_environment():
    return Settings(
        data_dir=Path(os.environ.get("CAMPUS_DATA_DIR", ROOT / "data")).resolve(),
        customer=os.environ.get("CAMPUS_CUSTOMER", "north-campus"),
        model=os.environ.get("CAYU_MODEL", "gpt-5.6-sol"),
        browser=os.environ.get("CAMPUS_BROWSER", "0") == "1",
        viewer_state=Path(os.environ["CAMPUS_VIEWER_STATE"]).resolve()
        if os.environ.get("CAMPUS_VIEWER_STATE") else None,
    )


def configured_api_key():
    key = os.environ.get("OPENAI_API_KEY")
    return key


def configured_model():
    return settings_from_environment().model


def configured_provider_name():
    return "openai"


def configured_provider_choice():
    return "openai"
