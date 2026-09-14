"""Application-owned meal plans, immutable proposals and atomic purchase receipts."""

import hashlib
import json
import sqlite3
from pathlib import Path

from catalog_app.catalog import POLICY, PRODUCTS, default_plan, tomorrow
from catalog_app.planning import assess, revise


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class PortalStore:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS products(sku TEXT PRIMARY KEY, payload TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS configuration(key TEXT PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS plans(customer TEXT, session_id TEXT, meal_id TEXT, payload TEXT,
                PRIMARY KEY(customer,session_id,meal_id));
              CREATE TABLE IF NOT EXISTS plan_changes(identity TEXT PRIMARY KEY, digest TEXT, payload TEXT);
              CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, customer TEXT NOT NULL,
                session_id TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS current_proposals(customer TEXT NOT NULL, session_id TEXT NOT NULL,
                proposal_id TEXT NOT NULL, PRIMARY KEY(customer,session_id));
              CREATE TABLE IF NOT EXISTS orders(proposal_id TEXT PRIMARY KEY, customer TEXT NOT NULL,
                digest TEXT NOT NULL, payload TEXT NOT NULL);
            """)
            db.execute(
                "INSERT OR IGNORE INTO configuration VALUES ('service_date',?)", (tomorrow(),)
            )
            service_date = db.execute(
                "SELECT value FROM configuration WHERE key='service_date'"
            ).fetchone()[0]
            for item in PRODUCTS:
                p = {**item, "delivery_date": service_date}
                db.execute("INSERT OR IGNORE INTO products VALUES (?,?)", (p["sku"], canonical(p)))

    def products(self, query=""):
        with self.connect() as db:
            rows = [
                json.loads(r[0]) for r in db.execute("SELECT payload FROM products ORDER BY sku")
            ]
        terms = query.lower().split()
        return [
            p
            for p in rows
            if all(t in (p["sku"] + " " + p["name"] + " " + p["category"]).lower() for t in terms)
        ]

    @staticmethod
    def _product(db, sku):
        row = db.execute("SELECT payload FROM products WHERE sku=?", (sku,)).fetchone()
        if row is None:
            raise ValueError("Unknown SKU")
        return json.loads(row[0])

    def product(self, sku):
        with self.connect() as db:
            return self._product(db, sku)

    @staticmethod
    def _plan(db, customer, session_id, meal_id):
        row = db.execute(
            "SELECT payload FROM plans WHERE customer=? AND session_id=? AND meal_id=?",
            (customer, session_id, meal_id),
        ).fetchone()
        if row:
            return json.loads(row[0])
        service_date = db.execute(
            "SELECT value FROM configuration WHERE key='service_date'"
        ).fetchone()[0]
        return default_plan(meal_id, service_date)

    def plan(self, customer, session_id, meal_id="dinner"):
        with self.connect() as db:
            return self._plan(db, customer, session_id, meal_id)

    def revise_plan(self, customer, session_id, meal_id, expected_revision, changes, identity):
        material = {
            "customer": customer,
            "session": session_id,
            "meal": meal_id,
            "revision": expected_revision,
            "changes": changes,
        }
        digest = hashlib.sha256(canonical(material).encode()).hexdigest()
        key = hashlib.sha256(canonical([customer, session_id, identity]).encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT digest,payload FROM plan_changes WHERE identity=?", (key,)
            ).fetchone()
            if old:
                if old[0] != digest:
                    raise ValueError("Plan change identity reused with different arguments")
                return json.loads(old[1])
            plan = self._plan(db, customer, session_id, meal_id)
            if type(expected_revision) is not int or plan["revision"] != expected_revision:
                raise ValueError("Meal plan changed; inspect it again")
            updated = revise(plan, changes)
            db.execute(
                "INSERT INTO plans VALUES (?,?,?,?) ON CONFLICT(customer,session_id,meal_id) DO UPDATE SET payload=excluded.payload",
                (customer, session_id, meal_id, canonical(updated)),
            )
            db.execute("INSERT INTO plan_changes VALUES (?,?,?)", (key, digest, canonical(updated)))
            db.execute(
                "DELETE FROM current_proposals WHERE customer=? AND session_id=?",
                (customer, session_id),
            )
            return updated

    def assess(self, customer, session_id, meal_id, sku, cases=None):
        with self.connect() as db:
            return assess(
                self._product(db, sku), self._plan(db, customer, session_id, meal_id), cases
            )

    def prepare(self, customer, session_id, meal_id, sku, cases, expected_plan_revision):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            p = self._product(db, sku)
            plan = self._plan(db, customer, session_id, meal_id)
            if plan["revision"] != expected_plan_revision:
                raise ValueError("Meal plan changed; inspect and compare again")
            result = assess(p, plan, cases)
            if not result["eligible"]:
                raise ValueError("; ".join(result["reasons"]))
            material = {
                "customer": customer,
                "session_id": session_id,
                "meal_id": meal_id,
                "sku": sku,
                "cases": cases,
                "product_revision": p["revision"],
                "product": p,
                "plan": plan,
                "policy": POLICY,
                "assessment": result,
            }
            digest = hashlib.sha256(canonical(material).encode()).hexdigest()
            proposal = {"proposal_id": "proposal-" + digest[:24], "digest": digest, **material}
            db.execute(
                "INSERT OR IGNORE INTO proposals VALUES (?,?,?,?,?)",
                (proposal["proposal_id"], customer, session_id, digest, canonical(proposal)),
            )
            db.execute(
                "INSERT INTO current_proposals VALUES (?,?,?) ON CONFLICT(customer,session_id) DO UPDATE SET proposal_id=excluded.proposal_id",
                (customer, session_id, proposal["proposal_id"]),
            )
            return proposal

    def current_proposal(self, customer, session_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT p.payload FROM current_proposals c JOIN proposals p ON p.id=c.proposal_id WHERE c.customer=? AND c.session_id=?",
                (customer, session_id),
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def proposal(self, proposal_id, customer, session_id=None):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM proposals WHERE id=? AND customer=?", (proposal_id, customer)
            ).fetchone()
        if row is None:
            raise ValueError("Proposal not found in customer scope")
        value = json.loads(row[0])
        if session_id is not None and value["session_id"] != session_id:
            raise ValueError("Proposal belongs to another session")
        return value

    def submit(self, proposal_id, digest, customer, session_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM proposals WHERE id=? AND customer=? AND session_id=?",
                (proposal_id, customer, session_id),
            ).fetchone()
            if row is None:
                raise ValueError("Proposal outside session/customer scope")
            proposal = json.loads(row[0])
            if proposal["digest"] != digest:
                raise ValueError("Proposal fingerprint changed")
            old = db.execute(
                "SELECT payload,digest FROM orders WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            if old:
                if old["digest"] != digest:
                    raise ValueError("Conflicting submission identity")
                return json.loads(old["payload"])
            current = db.execute(
                "SELECT proposal_id FROM current_proposals WHERE customer=? AND session_id=?",
                (customer, session_id),
            ).fetchone()
            if current is None or current[0] != proposal_id:
                raise ValueError("Proposal superseded: review the current proposal")
            plan = self._plan(db, customer, session_id, proposal["meal_id"])
            if plan != proposal["plan"] or POLICY != proposal["policy"]:
                raise ValueError("Meal plan or purchasing policy changed; prepare a new proposal")
            p = self._product(db, proposal["sku"])
            if p != proposal["product"]:
                raise ValueError("Product or stock changed; prepare a new proposal")
            check = assess(p, plan, proposal["cases"])
            if not check["eligible"]:
                raise ValueError("Proposal no longer eligible")
            receipt = {
                "status": "submitted",
                "proposal_id": proposal_id,
                "customer": customer,
                "sku": p["sku"],
                "cases": proposal["cases"],
                "total_cents": check["total_cents"],
                "delivery_date": p["delivery_date"],
                "delivery_minute": p["delivery_minute"],
                "plan_revision": plan["revision"],
                "digest": digest,
            }
            db.execute(
                "INSERT INTO orders VALUES (?,?,?,?)",
                (proposal_id, customer, digest, canonical(receipt)),
            )
            p["stock"] -= proposal["cases"]
            p["revision"] += 1
            db.execute("UPDATE products SET payload=? WHERE sku=?", (canonical(p), p["sku"]))
            return receipt

    def orders(self, customer):
        with self.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM orders WHERE customer=? ORDER BY rowid DESC", (customer,)
                )
            ]

    def proposals(self, customer):
        with self.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM proposals WHERE customer=? ORDER BY rowid DESC LIMIT 30",
                    (customer,),
                )
            ]
