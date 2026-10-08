# Campus dining purchasing demo

A fictional university dining agent built with Cayu. It keeps a planned meal feasible by comparing supplier products against cooked yield, kitchen inventory, preparation capacity, delivery time, dietary requirements, stock and budget. It explains its choice, prepares an exact proposal, and needs a person's approval before recording an order.

All suppliers, prices, yields, dietary attestations and delivery promises are synthetic.

## The scenario

Tomorrow's dinner for 400 students needs 80 kg of cooked potatoes, and the kitchen already has 20 kg. The kitchen is short-staffed, with 45 minutes of preparation time:

- Seven cases of peeled diced potatoes give 66.5 kg for $175 and need 35 minutes. That fits.
- Four cases of whole potatoes cost $96 but need 180 minutes of preparation. That doesn't fit yet.
- Frozen potatoes arrive after the receiving deadline, the prepared mash has unverified dairy, and baby potatoes are out of stock.

Tell the agent the full kitchen team is now available and ask it to reconsider. The plan now has 240 minutes, so the cheaper whole potatoes become the better draft. The prompt doesn't name a product: deterministic tools calculate eligibility and the model chooses and explains.

Rice lunch and a carrot side have their own meal records. Requests outside these records need clarification; this is a bounded fixture, not a general purchasing integration.

## Set up

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --extra dev
uv run --no-sync python demo.py setup
```

`setup` creates private local keys under the git-ignored `data/` directory, the dining records, and the published purchasing policy. These checks need no model API key:

```sh
uv run --no-sync cayu check --fail-on warning --json
uv run --no-sync pytest
uv run --no-sync python -m evals.run
```

## Run the agent

Set `OPENAI_API_KEY` (or choose another provider with `CAYU_PROVIDER`; see `configuration/settings.py`), then:

```sh
uv run --no-sync python demo.py run --message "Find a replacement potato draft for tomorrow's dinner for 400 students. We are short-staffed. Do not order."
uv run --no-sync python demo.py run --session SESSION_ID --message "The full kitchen team is now available. Reconsider."
uv run --no-sync python demo.py run --session SESSION_ID --message "Place that order."
```

When the agent asks a question or requests approval, the session pauses. Answer or decide in the dashboard:

```sh
CAYU_OPERATOR_USERNAME=operator CAYU_OPERATOR_PASSWORD=choose-a-password uv run --no-sync python serve.py
```

Open http://127.0.0.1:8000/cayu/, sign in, open the session, and click **Refresh review**. The review shows the exact product, cases, cost, meal revision, preparation, yield and delivery that approval would record. Approve or deny there. Then `uv run --no-sync python demo.py orders` prints the recorded receipts.

`serve.py` runs Cayu's packaged control plane and dashboard. It exists because the dashboard needs a review purpose that `cayu serve` doesn't set; otherwise `cayu serve` works the same way.

## How it's built

| Concern | Where |
| --- | --- |
| Meal plans, products, proposals and receipts (business records) | `domain/` |
| Exact purchasing arithmetic and constraints | `domain/planning.py` |
| Model-callable tools | `tools/dining.py`, `tools/questions.py` |
| Approval before an order, tool exposure | `policies/tools.py` |
| What a reviewer sees before deciding | `policies/human_review.py` |
| Agent instructions | `prompts/agent.py` |
| Purchasing policy in knowledge | `knowledge/curation.py` |
| Composition | `app.py` |

The model makes the purchasing decision; code keeps the authority. `submit_proposal` always pauses for approval. A plan change invalidates the previous proposal. Submission rechecks the policy, plan, product facts and stock, and an idempotent receipt records one stock decrement. Model text is never approval.

Cayu records the execution (sessions, events, approvals) in `data/cayu.db`, or PostgreSQL when `CAYU_DATABASE_URL` is set. The dining records live in `data/dining.db`. Both are needed.

## Evals

`uv run --no-sync python -m evals.run` runs nine scenarios on the real application with a scripted provider and private fixture data: short staffing, a full kitchen team, an infeasible budget, rice lunch, a carrot side, later receiving, fewer diners, a dietary boundary, and the approval gate. Grading checks the exact draft (product, cases, cost), the requested plan changes, that no order is recorded, and the reviewed approval request where applicable. No eval approves an order. Scripted evals prove tool behavior, not model understanding.

To evaluate the configured live model (this incurs provider usage):

```sh
uv run --no-sync python -m evals.run --live --case short-staffed
uv run --no-sync python -m evals.run --live --all
```

`uv run --no-sync cayu eval run` runs the same scripted suite through Cayu's eval runner and records it for the dashboard's Evals page.
