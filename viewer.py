"""Local protected viewer launch, pinned browser access, and worker restart."""

import argparse
import asyncio
import json
import ssl
from pathlib import Path

import httpx

from configuration.settings import PRESENTER_TRANSITION_SECONDS
from operations.viewer_host import configuration, remove_host, start_host, start_worker, stop_worker
from policies.budgets import MAX_TOTAL_TOKENS


async def open_panel(root):
    from playwright.async_api import async_playwright
    config = configuration(root)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, args=[f"--ignore-certificate-errors-spki-list={config['spki_pin']}"]
        )
        context = await browser.new_context(http_credentials={
            "username": "local-presenter", "password": config["password"], "origin": config["origin"],
        })
        page = await context.new_page()
        await page.goto(config["origin"] + "/operator")
        print("Protected viewer open. Close the browser or press Ctrl-C to exit.", flush=True)
        while browser.is_connected():
            await asyncio.sleep(1)


async def remote_action(root, args):
    config = configuration(root)
    sid = (args.session or ["comparison"])[0]
    tls = ssl.create_default_context(cafile=str(root / "certificate.pem"))
    async with httpx.AsyncClient(base_url=config["origin"], verify=tls, trust_env=False,
                                auth=("local-presenter", config["password"]), timeout=360) as client:
        if args.command == "run":
            if not args.message:
                raise ValueError("--message is required")
            payload = {"agent": "cayu-campus-dining-demo", "session_id": sid, "prompt": args.message,
                       "max_steps": 28,
                       "limits": {"max_tool_calls": 24, "max_total_tokens": MAX_TOTAL_TOKENS,
                                  "max_elapsed_seconds": 300},
                       "retry_policy": {"max_attempts": 1, "max_unknown_attempts": 1}}
            selection = (await client.get("/demo/recording-session")).raise_for_status().json()
            if selection["enabled"] and (not selection["ready"] or selection["session_id"] != sid):
                if selection["session_id"] != sid:
                    from uuid import uuid4
                    selected = await client.post(
                        "/demo/recording-session", headers={"Origin": config["origin"]},
                        json={"session_id": sid, "request_id": str(uuid4())},
                    )
                    selected.raise_for_status()
                deadline = asyncio.get_running_loop().time() + PRESENTER_TRANSITION_SECONDS
                while asyncio.get_running_loop().time() < deadline:
                    try:
                        ready = (await client.get("/demo/recording-session")).raise_for_status().json()
                        if ready.get("status") == "failed":
                            raise RuntimeError("Recording setup failed; inspect the presenter logs.")
                        if ready["ready"] and ready["session_id"] == sid:
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(.5)
                else:
                    raise RuntimeError("Recording session did not become ready; no run submitted.")
            existing = await client.get(f"/api/sessions/{sid}")
            if existing.status_code == 404:
                endpoint = "/api/run"
            else:
                existing.raise_for_status()
                endpoint = "/api/resume"
                payload.pop("agent")
            response = await client.post(endpoint, json=payload)
        else:
            response = await client.get(f"/api/sessions/{sid}/human-review",
                                        params={"purpose": f"order-review:{sid}"})
            response.raise_for_status()
            view = response.json()
            if args.command == "pending":
                print(json.dumps(view, indent=2))
                return
            if not args.review_tag or not view.get("reference") or (
                view["reference"]["content_tag"] != args.review_tag
            ):
                raise ValueError("Inspect pending and pass its current --review-tag")
            if args.command == "answer":
                if not args.answer or view["kind"] != "user_input":
                    raise ValueError("A current input pause and --answer are required")
                endpoint = "/api/user-input/resolve"
                payload = {"session_id": sid, "input_id": view["interaction_id"],
                           "answer": args.answer, "review_reference": view["reference"]}
            else:
                if view["kind"] != "tool_approval":
                    raise ValueError("A current tool approval is required")
                endpoint = "/api/tool-approvals/resolve"
                payload = {"session_id": sid, "approval_id": view["interaction_id"],
                           "tool_round_id": view["tool_round_id"], "tool_call_id": view["tool_call_id"],
                           "decision": "deny" if args.deny else "approve",
                           "review_reference": view["reference"]}
            response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        print(response.text)
        if '"session.failed"' in response.text:
            raise RuntimeError("Runtime recorded a failed invocation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "open", "restart-worker", "stop", "run", "pending", "answer", "approve"])
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--session", action="append")
    parser.add_argument("--message")
    parser.add_argument("--answer")
    parser.add_argument("--review-tag")
    parser.add_argument("--deny", action="store_true")
    args = parser.parse_args()
    root = args.state_dir.resolve()
    if args.command == "start":
        config = start_host(root, sessions=args.session or ["dinner", "comparison", "rice-lunch", "vegetable-side"])
        print(f"Protected operator server: {config['origin']}/operator")
        print("Login: local-presenter / demo")
        print("Open the URL in your browser.")
    elif args.command == "open":
        asyncio.run(open_panel(root))
    elif args.command == "restart-worker":
        stop_worker(root, crash=True)
        start_worker(root)
        print("Replaced the worker in the same application container; re-open pending review.")
    elif args.command in {"run", "pending", "answer", "approve"}:
        asyncio.run(remote_action(root, args))
    else:
        remove_host(root)
        print("Removed the exact application host. Preserve private state for inspection.")


if __name__ == "__main__":
    main()
