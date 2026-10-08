"""Hermetic configuration: private keys and a fresh dining database per test."""

import os
import secrets

import pytest

from domain.store import DiningStore


@pytest.fixture(autouse=True)
def private_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPUS_DINING_DATABASE", str(tmp_path / "dining.db"))
    monkeypatch.setenv("CAMPUS_HUMAN_REVIEW_KEY", secrets.token_hex(32))
    if "CAYU_MEMORY_EVIDENCE_KEY" not in os.environ:
        monkeypatch.setenv("CAYU_MEMORY_EVIDENCE_KEY", secrets.token_hex(32))


@pytest.fixture
def store(tmp_path):
    return DiningStore(tmp_path / "dining.db")
