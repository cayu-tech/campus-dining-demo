"""Run the standalone synthetic catalog without Cayu or model credentials."""

import argparse
from pathlib import Path

import uvicorn

from catalog_app.portal import CUSTOMERS, build_portal
from catalog_app.store import PortalStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/portal.db"))
    parser.add_argument("--customer", choices=sorted(CUSTOMERS), default="north-campus")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    PortalStore(args.database).initialize()
    uvicorn.run(
        build_portal(database=args.database, customer=args.customer),
        host="127.0.0.1",
        port=args.port,
    )


if __name__ == "__main__":
    main()
