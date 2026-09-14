"""Read-only browser layout checks using an existing completed presenter session.

Lifecycle responses are simulated only in this browser. No run/reset/approval is sent.
"""

import argparse
import asyncio
import json
import ssl
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect


async def exercise(root: Path, session_id: str, output: Path):
    config = json.loads((root / "configuration.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    phase = "running"
    mutations = []
    async with httpx.AsyncClient(
        verify=ssl.create_default_context(cafile=str(root / "certificate.pem")),
        auth=("local-presenter", config["password"]), trust_env=False,
    ) as http, async_playwright() as playwright:
        original = await http.get(f"{config['origin']}/api/sessions/{session_id}/state")
        original.raise_for_status()
        if original.json()["status"] != "completed":
            raise RuntimeError("Choose an existing completed session; active/review sessions are left alone")
        browser = await playwright.chromium.launch(
            args=[f"--ignore-certificate-errors-spki-list={config['spki_pin']}"]
        )
        context = await browser.new_context(
            http_credentials={
                "username": "local-presenter", "password": config["password"],
                "origin": config["origin"],
            }, viewport={"width": 1600, "height": 1100},
        )

        async def lifecycle(route):
            request = route.request
            if "/api/browser-control/" in request.url:
                await route.fulfill(json={"operator_session_token": "layout-test-only", "browsers": []})
                return
            summary_read = (
                request.method == "POST"
                and request.url.split("?")[0] == config["origin"] + "/api/sessions/summary"
            )
            if request.method not in ("GET", "HEAD") and not summary_read:
                mutations.append(request.url)
                await route.abort()
                return
            response = (
                await http.post(request.url, json=request.post_data_json)
                if summary_read else await http.get(request.url)
            )
            if request.url.split("?")[0] in (
                f"{config['origin']}/api/sessions/{session_id}",
                f"{config['origin']}/api/sessions/{session_id}/state",
            ):
                data = response.json()
                data["status"] = phase
                await route.fulfill(status=response.status_code, json=data)
            else:
                await route.fulfill(status=response.status_code, body=response.content,
                                    content_type=response.headers.get("content-type", "application/json"))

        await context.route("**/api/**", lifecycle)
        page = await context.new_page()
        await page.goto(f"{config['origin']}/operator/sessions/{session_id}")
        workspace = page.get_by_test_id("session-workspace")
        composer = page.get_by_test_id("session-composer")
        conversation = page.get_by_label("Conversation messages")
        browser_panel = page.get_by_role("region", name="Browser preview", exact=True)
        await expect(composer.get_by_role("button", name="Running...", exact=True)).to_be_visible()
        await expect(conversation).not_to_contain_text("Loading conversation…")
        await expect(conversation).to_contain_text("potatoes")
        before = {
            "workspace": await workspace.bounding_box(), "composer": await composer.bounding_box(),
            "browser": await browser_panel.bounding_box(),
        }
        await conversation.evaluate("e=>{e.scrollTop=0}")
        await page.screenshot(path=str(output / "running.png"))
        phase = "completed"
        await expect(composer.get_by_role("button", name="Resume", exact=True)).to_be_visible(
            timeout=20000
        )
        await expect(page.get_by_label("Recorded browser video")).to_be_visible(timeout=20000)
        await page.wait_for_timeout(500)
        after = {
            "workspace": await workspace.bounding_box(), "composer": await composer.bounding_box(),
            "browser": await browser_panel.bounding_box(),
        }
        for name in before:
            for axis in ("x", "y", "width", "height"):
                assert abs(before[name][axis] - after[name][axis]) <= 1, (name, before, after)
        assert await conversation.evaluate("e=>e.scrollTop") == 0
        assert await page.locator('canvas[aria-label="Live browser frame"]').is_hidden()
        await page.screenshot(path=str(output / "completed.png"))
        await page.get_by_role("button", name="Collapse sidebar", exact=True).click()
        await expect(page.get_by_role("navigation", name="Main navigation")).to_have_attribute(
            "data-collapsed", "true"
        )
        assert (await workspace.bounding_box())["width"] > after["workspace"]["width"]
        await page.get_by_placeholder("Continue with a new prompt...").fill("Keep this draft")
        await page.get_by_role("button", name="Expand sidebar", exact=True).click()
        await expect(page.get_by_placeholder("Continue with a new prompt...")).to_have_value(
            "Keep this draft"
        )
        await page.get_by_role("button", name="Collapse sidebar", exact=True).click()
        await page.reload()
        await expect(page.get_by_role("button", name="Expand sidebar", exact=True)).to_be_visible()
        await expect(page.get_by_role("link", name="Sessions", exact=True)).to_be_visible()
        await expect(workspace).to_be_visible()
        await expect(page.get_by_label("Recorded browser video")).to_be_visible()
        await page.screenshot(path=str(output / "collapsed.png"))
        await page.get_by_role("link", name="Sessions", exact=True).click()
        await page.wait_for_url("**/operator/sessions")
        await expect(page.get_by_role("button", name="Expand sidebar", exact=True)).to_be_visible()
        await page.go_back()
        await expect(workspace).to_be_visible()
        toggle = page.get_by_role("button", name="Expand sidebar", exact=True)
        await toggle.focus()
        await page.keyboard.press("Enter")
        await expect(page.get_by_role("button", name="Collapse sidebar", exact=True)).to_be_visible()
        await page.keyboard.press("Space")
        await expect(page.get_by_role("button", name="Expand sidebar", exact=True)).to_be_visible()
        video = page.get_by_label("Recorded browser video")
        await video.evaluate("v=>v.play()")
        await page.wait_for_timeout(1200)
        assert await video.evaluate("v=>v.currentTime>0 && v.videoWidth>0")
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(path=str(output / "mobile.png"), full_page=True)
        assert await page.locator("main").evaluate("e=>e.scrollWidth<=e.clientWidth+1")
        assert not mutations, mutations
        (output / "proof.json").write_text(json.dumps({
            "before": before, "after": after, "mutations": mutations,
            "sidebar_persisted": True, "reading_position_preserved": True,
        }, indent=2))
        await browser.close()
        print("PASS: fixed workspace, retained reading/input, sidebar persistence, playback, mobile")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--session", default="comparison")
    parser.add_argument("--output", type=Path, default=Path("validation/private/layout"))
    args = parser.parse_args()
    asyncio.run(exercise(args.state_dir, args.session, args.output))
