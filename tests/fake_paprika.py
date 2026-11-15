"""An in-memory stand-in for the Paprika API, served through aioresponses.

It starts from the anonymised payloads in tests/fixtures and copies the API behaviour
verified against a live account (see tests/fixtures/README.md):

- `sync/status` counters are per-entity revision numbers.
- A grocery POST bumps `groceries` once per item, and `"deleted": true` removes it.
- Edits made "in the app" (`edit`, `edit_recipe`) bump only that entity's counter.
- Unknown endpoints return 404 with `{"error": ...}`.

Every request is logged in `requests`, so tests can assert on which calls were made.
"""

import copy
import gzip
from http import HTTPStatus
import json
from pathlib import Path
import secrets
from typing import Any
from urllib.parse import parse_qs

from aiohttp import ClientConnectionError
from aioresponses import CallbackResult
from yarl import URL

FIXTURES = Path(__file__).parent / "fixtures"
API_V2 = "/api/v2/"

TOKEN = "fake-token"
EMAIL = "cook@example.com"
PASSWORD = "correct horse"

LIST_ENTITIES = (
    "groceries",
    "grocerylists",
    "groceryaisles",
    "groceryingredients",
    "meals",
    "mealtypes",
    "recipes",
    "categories",
    "photos",
    "menus",
    "menuitems",
)


def load_fixture(name: str) -> Any:
    """Return the `result` of a fixture file."""
    return json.loads((FIXTURES / f"{name}.json").read_text())["result"]


class FakePaprika:
    """The fake account's data, plus the logic that serves it."""

    def __init__(self) -> None:
        self.status: dict[str, int] = load_fixture("status")
        self.data: dict[str, list[dict]] = {e: load_fixture(e) for e in LIST_ENTITIES}
        self.recipes: dict[str, dict] = {
            p.stem.removeprefix("recipe_"): json.loads(p.read_text())["result"]
            for p in FIXTURES.glob("recipe_*.json")
        }
        self.requests: list[tuple[str, str]] = []
        self.posted: dict[str, list[list[dict]]] = {}
        self._failures: dict[str, int | BaseException] = {}

    # Test helpers

    def paths(self, method: str = "GET") -> list[str]:
        """The paths requested so far with `method`, in order."""
        return [p for m, p in self.requests if m == method]

    def fail(self, path: str, error: int | BaseException = 500) -> None:
        """Make `path` return an HTTP error status, or raise an exception, from now on."""
        self._failures[path] = error

    def edit(self, entity: str, change: Any) -> None:
        """Change an entity's list as an edit in the app would, bumping its counter."""
        change(self.data[entity])
        self.status[entity] += 1

    def edit_recipe(self, uid: str, **fields: Any) -> None:
        """Edit a recipe in the app: new content and hash, `recipes` counter bumped."""
        new_hash = secrets.token_hex(8).upper()
        self.recipes[uid] = {**self.recipes[uid], **fields, "hash": new_hash}
        for item in self.data["recipes"]:
            if item["uid"] == uid:
                item["hash"] = new_hash
        self.status["recipes"] += 1

    def meal_with_recipe(self) -> dict:
        """A planned meal whose full recipe is in the fixtures."""
        return next(m for m in self.data["meals"] if m["recipe_uid"] in self.recipes)

    # Request handling, called by aioresponses

    def handle(self, url: URL, **kwargs: Any) -> CallbackResult:
        """Serve one intercepted request."""
        method = kwargs["method"]
        if url.path == "/api/v1/account/login":
            self.requests.append((method, "account/login"))
            return self._login(kwargs.get("data"))
        path = url.path.removeprefix(API_V2).rstrip("/")
        self.requests.append((method, path))

        failure = self._failures.get(path)
        if isinstance(failure, BaseException):
            raise failure
        if failure:
            return _error(failure, "Simulated failure.")

        entity = path.removeprefix("sync/")
        if method == "GET" and entity == "status":
            return _ok(copy.deepcopy(self.status))
        if method == "GET" and entity in self.data:
            return _ok(copy.deepcopy(self.data[entity]))
        if method == "GET" and entity.startswith("recipe/"):
            recipe = self.recipes.get(entity.removeprefix("recipe/"))
            return _ok(copy.deepcopy(recipe)) if recipe else _error(404, "Not found.")
        if method == "POST" and entity == "groceries":
            self._save_groceries(decode_sync_body(kwargs["data"]))
            return _ok(True)
        return _error(404, "Not found.")

    def _login(self, form: Any) -> CallbackResult:
        if isinstance(form, (bytes, str)):
            form = {
                k: v[0]
                for k, v in parse_qs(form if isinstance(form, str) else form.decode()).items()
            }
        if form and form.get("email") == EMAIL and form.get("password") == PASSWORD:
            return _ok({"token": TOKEN})
        return _error(200, "Invalid email or password.")

    def _save_groceries(self, items: list[dict]) -> None:
        self.posted.setdefault("groceries", []).append(items)
        groceries = self.data["groceries"]
        for item in items:
            groceries[:] = [g for g in groceries if g["uid"] != item["uid"]]
            if not item.get("deleted"):
                groceries.append(item)
            self.status["groceries"] += 1


def decode_sync_body(body: bytes) -> Any:
    """Undo PaprikaApi._post_sync: a multipart body wrapping gzipped JSON."""
    _headers, _, rest = body.partition(b"\r\n\r\n")
    payload, _, _closing = rest.rpartition(b"\r\n--")
    return json.loads(gzip.decompress(payload))


def _ok(result: Any) -> CallbackResult:
    return CallbackResult(status=200, payload={"result": result})


def _error(status: int, message: str) -> CallbackResult:
    return CallbackResult(
        status=status,
        reason=HTTPStatus(status).phrase,
        payload={"error": {"code": 0, "message": message}},
    )


def refuse(url: URL, **kwargs: Any) -> CallbackResult:
    """Fail any request that isn't to Paprika, so nothing real is ever contacted."""
    raise ClientConnectionError(f"Test tried to reach a non-Paprika URL: {url}")
