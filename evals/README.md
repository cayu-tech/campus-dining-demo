# Dining agent evals

Run the nine credential-free contract scenarios:

```sh
uv run --no-sync python -m evals.run
```

This uses the real application, tools, policies, and native Cayu eval runner with a scripted provider. It checks tool execution and business outcomes; it does not measure model understanding. Every invocation creates isolated private fixture state and prints the path to its JSON result and HTML report. It does not use or change presenter sessions and does not launch Chrome.

The cases cover short staffing, a full kitchen team, an infeasible budget, rice lunch, a vegetable side, later receiving, fewer diners, dietary uncertainty, and the submission approval gate. Grading checks exact draft SKU, quantity and cost, requested plan changes, absence of orders, and the protected approval request where applicable. Expected outcomes live in evaluator-owned case definitions. No eval approves an order.

To evaluate decisions by the configured live model, provide `OPENAI_API_KEY` and explicitly select a case or the full suite. These commands incur provider usage:

```sh
uv run --no-sync python -m evals.run --live --case short-staffed
uv run --no-sync python -m evals.run --live --all
```

Use `--list` to list prompts, repeated `--case NAME` flags to select cases, or `--output-dir /absolute/new/private/directory` to choose report storage. Provider failures remain execution errors; they are not treated as successful decisions. Keep the retained fixture state with reports when inspecting business facts or rescoring.

The standard SDK entry point also runs the contract suite:

```sh
uv run --no-sync cayu eval run
```

`tests/test_evals.py` verifies repeatability and concurrent trial isolation, and proves the grader rejects a feasible but wrong recommendation and an unrequested plan change. These evals do not automate the presenter UI, score explanation quality, or test the two-turn browser conversation. The existing `evals.browser_rehearsal` is a separate opt-in UI rehearsal. The operator dashboard’s Evals page displays all nine cases and can run this contract suite, retaining its latest result and full HTML report in the presenter’s private state. Dashboard execution uses separate fixture databases, so it does not change dining sessions. CLI reports remain in their selected output directory.

For credential-free browser coverage of navigation, published knowledge, the
nine-check Evals button, and mobile width, run
`uv run --no-sync python -m evals.ui_smoke` after building the dashboard and
installing Chromium. It starts an isolated loopback presenter and removes its
temporary state afterward. It does not measure live-model decisions.
