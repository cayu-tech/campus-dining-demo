"""Credential-free Chromium proof of the protected presenter and contract-eval UI."""

import argparse
import asyncio
import json
import secrets
import socket
import tempfile
from pathlib import Path

import uvicorn
from cayu import ScriptedModelProvider
from playwright.async_api import async_playwright, expect

from configuration.settings import Settings
from operations.initialize import initialize
from operations.viewer_host import certificates
from operations.viewer_server import build_server


async def exercise(output):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="campus-ui-smoke-") as temporary:
        root = Path(temporary)
        pin = certificates(root)
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        origin = f"https://127.0.0.1:{listener.getsockname()[1]}"
        password = secrets.token_urlsafe(24)
        (root / "configuration.json").write_text(json.dumps({
            "password": password, "origin": origin, "viewer_key": secrets.token_hex(32),
            "view_sessions": [], "recording_sessions": [],
        }))
        settings = Settings(data_dir=root / "data", viewer_state=root)
        await initialize(settings)
        server = uvicorn.Server(uvicorn.Config(
            build_server(settings, provider=ScriptedModelProvider([])),
            ssl_certfile=str(root / "certificate.pem"), ssl_keyfile=str(root / "key.pem"),
            access_log=False, log_level="error",
        ))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(20):
                while not server.started:
                    if serving.done():
                        await serving
                        raise RuntimeError("Presenter did not start")
                    await asyncio.sleep(0.05)
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    args=[f"--ignore-certificate-errors-spki-list={pin}"]
                )
                context = await browser.new_context(
                    http_credentials={"username": "local-presenter", "password": password,
                                      "origin": origin},
                    viewport={"width": 1440, "height": 1000},
                )
                page = await context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto(origin + "/operator/run")
                await expect(page.locator("#demo-session")).to_be_visible()
                await page.screenshot(path=str(output / "new-run.png"))
                await page.goto(origin + "/operator/knowledge")
                await expect(page.get_by_role("heading", name="University dining purchasing policy", exact=True)).to_be_visible()
                await page.screenshot(path=str(output / "knowledge.png"))
                await page.goto(origin + "/operator/evals")
                await page.get_by_role("button", name="Run all 9 checks", exact=True).click()
                await expect(page.get_by_text("9 / 9 passed", exact=True)).to_be_visible(timeout=300000)
                await expect(page.get_by_role("link", name="Open full report")).to_be_visible()
                await page.screenshot(path=str(output / "evals-passed.png"), full_page=True)
                await page.set_viewport_size({"width": 390, "height": 844})
                await expect(page.get_by_role("navigation", name="Main navigation")).to_have_attribute(
                    "data-collapsed", "true"
                )
                assert await page.locator("main").evaluate("e=>e.clientWidth >= 300")
                assert await page.locator("main").evaluate("e=>e.scrollWidth <= e.clientWidth")
                await page.screenshot(path=str(output / "mobile.png"), full_page=True)
                assert await page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                ), "Mobile page overflows horizontally"
                assert not errors, errors
                await browser.close()
                (output / "proof.json").write_text(json.dumps({
                    "status": "passed", "contract_cases": 9, "page_errors": errors,
                    "mobile_horizontal_overflow": False, "live_model": False,
                }, indent=2))
                print("PASS: Chromium navigation, knowledge, 9/9 UI evals, mobile width, no JS errors")
        finally:
            server.should_exit = True
            await serving
            listener.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("validation/private/ui-smoke"))
    args = parser.parse_args()
    asyncio.run(exercise(args.output.resolve()))
