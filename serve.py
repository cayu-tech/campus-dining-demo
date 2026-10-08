"""Serve the Cayu control plane and dashboard with protected order review.

    CAYU_OPERATOR_USERNAME=... CAYU_OPERATOR_PASSWORD=... python serve.py

`cayu serve` runs the same control plane but has no setting for the dashboard's
review purpose, so this entry point composes Cayu's server parts directly. The
dashboard then shows each pending question or order with the fields from
policies/human_review.py. Open http://127.0.0.1:8000/cayu/ and sign in.
"""

import argparse

import uvicorn
from cayu.server import DashboardConfig, ServerConfig, create_server
from cayu.server.auth import BasicAuth

from app import build_app
from configuration.settings import CUSTOMER
from policies.human_review import REVIEW_PURPOSE


def build_server():
    # The operator's tenant is the demo's single customer; the review policy checks it.
    auth = BasicAuth.from_environment(tenant=CUSTOMER)
    config = ServerConfig.protected(
        auth,
        dashboard=DashboardConfig(runtime_config={"humanReviewPurpose": REVIEW_PURPOSE}),
    )
    return create_server(build_app(), config=config)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Dashboard: http://{args.host}:{args.port}/cayu/")
    uvicorn.run(build_server(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
