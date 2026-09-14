"""Read-only synthetic supplier portal. Submission exists only in the agent tool."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

CUSTOMERS = {"north-campus": "North Campus Dining", "south-campus": "South Campus Dining"}
from catalog_app.catalog import MEALS, POLICY
from catalog_app.store import PortalStore

TEMPLATES = Path(__file__).parent / "templates"


def build_portal(*, database, customer="north-campus"):
    if customer not in CUSTOMERS:
        raise ValueError("Unknown synthetic customer")
    store = PortalStore(database)
    app = FastAPI(
        title="Campus Supply • Synthetic Cayu demo", docs_url=None, redoc_url=None, openapi_url=None
    )
    templates = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())
    app.mount("/static", StaticFiles(directory=TEMPLATES / "static"), name="static")

    def page(name, **values):
        return HTMLResponse(
            templates.get_template(name).render(customer=CUSTOMERS[customer], **values)
        )

    @app.get("/", response_class=HTMLResponse)
    def catalog(q: str = ""):
        if len(q) > 100:
            raise HTTPException(400, "Search is too long")
        return page("catalog.html", products=store.products(q), q=q, categories=sorted({p["category"] for p in store.products()}))

    @app.get("/products/{sku}", response_class=HTMLResponse)
    def product(sku: str):
        try:
            p = store.product(sku)
        except ValueError:
            raise HTTPException(404, "Product not found")
        return page("product.html", product=p, )

    @app.get("/proposals", response_class=HTMLResponse)
    def proposals():
        return page(
            "proposals.html",
            proposals=store.proposals(customer),
            orders=store.orders(customer),
        )

    @app.get("/planning", response_class=HTMLResponse)
    def planning():
        return page("planning.html", plans=[store.plan(customer, "presenter", meal_id) for meal_id in MEALS], policy=POLICY)

    @app.get("/health")
    def health():
        return {"status": "ok", "synthetic": True}

    @app.middleware("http")
    async def browser_boundary(request: Request, call_next):
        # The browser can read. It cannot create, approve, or submit any order.
        if request.method not in {"GET", "HEAD"}:
            return HTMLResponse(
                "Read-only portal: use the approval-protected Cayu operation.", status_code=405
            )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; img-src 'self'; script-src 'none'; frame-ancestors 'none'"
        )
        return response

    return app
