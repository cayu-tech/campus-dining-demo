"""Opt-in live UI proof. Uses a fresh allowed comparison session; never orders."""

import argparse
import asyncio
import json
import ssl
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect

from domain.store import PortalStore


async def exercise(root: Path, output: Path):
    config = json.loads((root / "configuration.json").read_text())
    store = PortalStore(root / "data/portal.db")
    origin = config["origin"]
    session_id = "comparison"
    output.mkdir(parents=True, exist_ok=True)
    tls = ssl.create_default_context(cafile=str(root / "certificate.pem"))
    async with httpx.AsyncClient(
        verify=tls, auth=("local-presenter", config["password"]), trust_env=False,
        timeout=httpx.Timeout(30, connect=5),
    ) as client, async_playwright() as playwright:
        existing = await client.get(f"{origin}/api/sessions/{session_id}")
        if existing.status_code != 404:
            raise RuntimeError("Use a fresh presenter: comparison already exists; no run dispatched")
        browser = await playwright.chromium.launch(
            args=[f"--ignore-certificate-errors-spki-list={config['spki_pin']}"]
        )
        context = await browser.new_context(
            http_credentials={
                "username": "local-presenter", "password": config["password"], "origin": origin
            }, viewport={"width": 1600, "height": 1100},
        )
        page_errors = []
        context.on("page", lambda page: page.on("pageerror", lambda error: page_errors.append(str(error))))
        run = await context.new_page()
        await run.goto(origin + "/operator/run")
        await run.locator("#demo-session").select_option(session_id)
        await expect(run.get_by_role("button", name="Run", exact=True)).to_be_enabled()
        assert await run.locator("canvas").count() == 0
        await run.get_by_role("button", name="Run", exact=True).click()
        link = run.get_by_role("link", name="Open session and browser in a new tab →", exact=True)
        await link.wait_for(timeout=210000)
        async with context.expect_page() as popup:
            await link.click()
        page = await popup.value

        async def finish(stage, previous_update=None):
            deadline = time.monotonic() + 420
            live = False
            while time.monotonic() < deadline:
                error = page.locator('[data-testid="session-composer"] .text-destructive')
                if previous_update is not None and await error.count() and await error.first.is_visible():
                    await page.screenshot(path=str(output / f"{stage}-failed.png"))
                    raise AssertionError(await error.first.inner_text())
                try:
                    response = await client.get(f"{origin}/api/sessions/{session_id}/state")
                except httpx.TransportError:
                    # A slow status read must not replay or abandon the active run.
                    continue
                if response.status_code == 200:
                    state = response.json()
                    frame = page.locator('canvas[aria-label="Live browser frame"]')
                    if await frame.count() and await frame.evaluate("e=>e.width>0"):
                        if not live:
                            await page.screenshot(path=str(output / f"{stage}-live.png"))
                        live = True
                    if state["updated_at"] != previous_update and state["status"] in (
                        "completed", "failed", "interrupted"
                    ):
                        assert state["status"] == "completed", state["status"]
                        await expect(page.get_by_placeholder(
                            "Continue with a new prompt..."
                        )).to_be_enabled(timeout=180000)
                        await page.screenshot(path=str(output / f"{stage}-completed.png"))
                        return state["updated_at"], live
                await asyncio.sleep(1)
            raise TimeoutError(f"{stage}: inspect retained presenter state before retrying")

        updated, live = await finish("short-staffed")
        assert live, "No live browser preview was observed during the first turn"
        baseline = store.current_proposal("north-campus", session_id)
        assert baseline and (baseline["sku"], baseline["cases"]) == ("POT-PEELED-10KG", 7)
        await page.get_by_placeholder("Continue with a new prompt...").fill(
            "Actually, we now have the full kitchen team available to prepare whole potatoes. "
            "Reconsider the options and update the draft if there is a better choice. "
            "Do not submit an order."
        )
        await page.get_by_role("button", name="Resume", exact=True).click()
        await finish("full-team", updated)
        revised = store.current_proposal("north-campus", session_id)
        assert revised and (revised["sku"], revised["cases"]) == ("POT-WHOLE-20KG", 4)
        assert revised["assessment"]["total_cents"] == 9600
        assert revised["plan"]["revision"] == 2 and revised["digest"] != baseline["digest"]
        assert store.orders("north-campus") == []
        video = page.locator("video")
        await video.wait_for(timeout=30000)
        await video.evaluate("v=>v.play()")
        await page.wait_for_timeout(2000)
        playback = await video.evaluate("v=>({time:v.currentTime,width:v.videoWidth})")
        assert playback["time"] > 0 and playback["width"] > 0
        await page.screenshot(path=str(output / "playback.png"))
        assert not page_errors, page_errors
        (output / "proof.json").write_text(json.dumps({
            "baseline": baseline, "revised": revised, "live_preview": live,
            "playback": playback, "orders": 0, "page_errors": page_errors,
        }, indent=2))
        await browser.close()
        print("PASS: live drafts, changed staffing decision, playback, zero orders")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("validation/private/rehearsal"))
    args = parser.parse_args()
    asyncio.run(exercise(args.state_dir.resolve(), args.output))
