"""Explicit private configuration for the local combined viewer/reconnect host."""

import json
import shlex

from cayu import BrowserControlConfig, BrowserOperatorPurpose

from policies.browser_control import ViewOnly


def viewer_configuration(settings):
    if settings.viewer_state is None:
        return None
    return json.loads((settings.viewer_state / "configuration.json").read_text())


def browser_control_options(settings):
    config = viewer_configuration(settings)
    if config is None:
        return None
    return BrowserControlConfig(
        policy=ViewOnly(settings, config["view_sessions"]),
        guest_endpoint="wss://cayu-control:8443/api/browser-control/guest",
        purpose=BrowserOperatorPurpose(
            code="synthetic_order_review",
            expected_origins=("https://supplier.campus-demo.test",),
        ),
    )


def viewer_setup(settings):
    if settings.viewer_state is None:
        return ()
    public_ca = (settings.viewer_state / "certificate.pem").read_text()
    return (
        (f"printf %s {shlex.quote(public_ca)} > /usr/local/share/ca-certificates/campus-demo.crt "
        "&& update-ca-certificates"),
    )
