"""Run native Cayu evals without touching the presenter's sessions or browsers."""

import argparse
import asyncio
from pathlib import Path
from uuid import uuid4

from cayu import eval_run_to_json, render_html_report, run_eval_plan

from configuration.settings import ROOT
from evals.agent import build_plan
from evals.cases import all_cases
from operations.lifecycle import close_app


async def execute(args):
    directory = (args.output_dir or ROOT / "validation/private/evals" / uuid4().hex).resolve()
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    plan = await build_plan(live=args.live, case_ids=args.case, directory=directory / "fixtures")
    try:
        result = await run_eval_plan(plan, case_timeout_seconds=300, max_concurrency=1)
        (directory / "result.json").write_text(eval_run_to_json(result))
        (directory / "report.html").write_text(render_html_report(result))
        print(f"{result.suite_id}: {result.status.value}")
        for case in result.cases:
            print(f"  {case.case_id}: {case.status.value}")
            for assertion in case.assertions:
                if assertion.outcome.value != "passed":
                    print(f"    {assertion.name}: {assertion.outcome.value}: {assertion.message}")
        print(f"Report: {directory / 'report.html'}")
        return 0 if result.status.value == "passed" else 1
    finally:
        await close_app(plan.app)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Use the configured live model; incurs provider usage"
    )
    parser.add_argument("--case", action="append", choices=[case.id for case in all_cases()])
    parser.add_argument("--all", action="store_true", help="Explicitly select every live case")
    parser.add_argument(
        "--list", action="store_true", help="List cases without constructing the app"
    )
    parser.add_argument(
        "--output-dir", type=Path, help="New private directory for reports and fixture state"
    )
    args = parser.parse_args()
    if args.list:
        for case in all_cases():
            print(f"{case.id}: {case.prompt}")
        return 0
    if args.all and args.case:
        parser.error("Choose --all or individual --case flags")
    if args.live and not (args.case or args.all):
        parser.error("Live execution requires --case NAME or explicit --all")
    return asyncio.run(execute(args))


if __name__ == "__main__":
    raise SystemExit(main())
