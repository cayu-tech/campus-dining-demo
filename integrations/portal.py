"""Compose the standalone catalog fixture with the agent's configured business database."""

from catalog_app.portal import build_portal as build_catalog_portal

from configuration.settings import settings_from_environment


def build_portal(settings=None):
    settings = settings or settings_from_environment()
    return build_catalog_portal(database=settings.portal_database, customer=settings.customer)
