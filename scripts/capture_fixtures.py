#!/usr/bin/env python3
"""Capture anonymised Paprika sync payloads for use as test fixtures.

Reads from a real account, keeps the shape of every payload (keys, types,
nulls, uid cross-references, dates) and replaces anything identifying:
uids, names, recipe text, URLs, hashes and photo names. The output goes to
tests/fixtures/<endpoint>.json and is checked for leaks of original values
before it is written.

The token comes from PAPRIKA_TOKEN, or from the paprika entry in a Home
Assistant config dir (default: ./config). It is never printed.

    scripts/capture_fixtures.py [--ha-config config] [--meals 40] [--recipes 6]
"""

# A developer script: printing, a seeded non-crypto RNG and urlopen on a fixed
# https URL are all intended here.
# ruff: noqa: T201, S310, S311

import argparse
import gzip
import hashlib
import json
import os
import random
import re
import secrets
import sys
import urllib.request
from collections.abc import Iterator
from pathlib import Path

BASE = "https://www.paprikaapp.com/api/v2/"
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
LIST_ENDPOINTS = [
    "status",
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
]

DISHES = [
    "Lentil Soup",
    "Chicken Traybake",
    "Vegetable Curry",
    "Mushroom Risotto",
    "Fish Tacos",
    "Shepherd's Pie",
    "Pesto Pasta",
    "Chickpea Stew",
    "Beef Chilli",
    "Roast Squash Salad",
    "Pad Thai",
    "Tomato Tart",
    "Bean Burritos",
    "Leek and Potato Soup",
    "Lemon Chicken",
    "Spinach Dal",
    "Fried Rice",
    "Minestrone",
    "Halloumi Wraps",
    "Sausage Casserole",
    "Pumpkin Gnocchi",
    "Prawn Linguine",
    "Falafel Bowls",
    "Cottage Pie",
    "Miso Noodles",
    "Ratatouille",
    "Pea Risotto",
    "Baked Salmon",
    "Bolognese",
    "Veggie Lasagne",
    "Pancakes",
    "Porridge",
    "Granola",
    "Banana Bread",
    "Flapjacks",
    "Apple Crumble",
    "Scones",
    "Shortbread",
]
INGREDIENTS = [
    "onion",
    "garlic",
    "carrot",
    "celery",
    "potato",
    "tomato",
    "spinach",
    "lemon",
    "lime",
    "butter",
    "milk",
    "eggs",
    "flour",
    "sugar",
    "rice",
    "pasta",
    "lentils",
    "chickpeas",
    "chicken thighs",
    "salmon",
    "prawns",
    "cheddar",
    "parmesan",
    "yoghurt",
    "bread",
    "oats",
    "honey",
    "olive oil",
    "stock cube",
    "coriander",
    "basil",
    "parsley",
    "ginger",
    "chilli",
    "peppers",
    "courgette",
    "mushrooms",
    "leek",
    "peas",
    "sweetcorn",
    "apples",
    "bananas",
    "cream",
    "tinned tomatoes",
    "kidney beans",
    "tortillas",
    "noodles",
    "soy sauce",
    "cumin",
    "paprika",
    "cinnamon",
    "bay leaves",
    "thyme",
    "rosemary",
    "cabbage",
    "broccoli",
    "cauliflower",
    "beetroot",
    "avocado",
    "feta",
    "mozzarella",
    "tofu",
    "pine nuts",
    "walnuts",
    "almonds",
    "raisins",
    "vinegar",
    "mustard",
    "mayonnaise",
    "ketchup",
    "jam",
    "peanut butter",
    "coffee",
    "tea",
    "orange juice",
    "baking powder",
    "yeast",
    "vanilla",
    "cocoa",
    "chocolate",
    "crackers",
    "crisps",
    "sparkling water",
    "dishwasher tablets",
    "bin bags",
    "kitchen roll",
    "foil",
    "sponges",
    "soap",
    "shampoo",
]
AISLES = [
    "Produce",
    "Dairy",
    "Bakery",
    "Meat",
    "Fish",
    "Frozen",
    "Tins and Jars",
    "Pasta and Rice",
    "Spices",
    "Baking",
    "Drinks",
    "Snacks",
    "Household",
    "Toiletries",
    "World Foods",
    "Condiments",
    "Cereal",
    "Deli",
    "Health",
    "Pet",
    "Baby",
    "Alcohol",
    "Free From",
    "Seasonal",
    "Other",
]
MIN_HEADER_LENGTH = 2  # an all-caps line longer than this is a section header
MIN_NOTED_LENGTH = 4  # shorter originals ("1", "tsp") are too generic to count as leaks
MIN_SUBSTRING_LEAK = 12  # long originals (URLs, uids) are also searched for as substrings


class Anonymiser:
    """Consistent stand-ins for identifying values, remembering the originals."""

    def __init__(self, seed: int = 1234) -> None:
        """Seed the stand-in generator so runs are repeatable."""
        self.rng = random.Random(seed)
        self.uids: dict[str, str] = {}
        self.pools: dict[str, dict[str, str]] = {}
        self.originals: set[str] = set()

    def note(self, value: str | None) -> None:
        """Remember an original value so the leak check can look for it."""
        if isinstance(value, str) and len(value.strip()) >= MIN_NOTED_LENGTH:
            self.originals.add(value.strip())

    def uid(self, value: str | None) -> str | None:
        """Map a uid to a stable fake uid, so cross-references still line up."""
        if not value:
            return value
        self.note(value)
        if value not in self.uids:
            h = hashlib.sha256(f"{len(self.uids)}:{self.rng.random()}".encode()).hexdigest().upper()
            # Keep Paprika's uppercase UUID layout (8-4-4-4-12).
            self.uids[value] = f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"
        return self.uids[value]

    def word(self, pool: str, choices: list[str], value: str | None) -> str | None:
        """Map an original name to a stand-in, consistently (case-insensitive)."""
        if not value:
            return value
        self.note(value)
        mapping = self.pools.setdefault(pool, {})
        key = value.strip().lower()
        if key not in mapping:
            n = len(mapping)
            mapping[key] = (
                choices[n]
                if n < len(choices)
                else f"{choices[n % len(choices)]} {n // len(choices) + 1}"
            )
        return mapping[key]

    def hex(self, value: str | None) -> str | None:
        """Replace a hash with random hex of the same length and case."""
        if not value:
            return value
        self.note(value)
        out = secrets.token_hex(len(value))[: len(value)]
        return out.upper() if value.isupper() else out

    def text(self, value: str | None, kind: str) -> str | None:
        """Replace free text line by line, keeping line count and blank lines."""
        if not value:
            return value
        self.note(value)
        for line in value.splitlines():
            self.note(line)
        lines = []
        for i, line in enumerate(value.split("\n")):
            s = line.strip()
            if not s:
                lines.append(line)
            elif s.endswith(":") or (s.isupper() and len(s) > MIN_HEADER_LENGTH):
                lines.append(f"SECTION {i + 1}:")
            elif kind == "ingredients":
                qty = self.rng.choice(["1", "2", "200 g", "1 tbsp", "½ tsp", "1 tin", "3"])
                lines.append(f"{qty} {self.rng.choice(INGREDIENTS)}")
            else:
                lines.append(f"{kind.capitalize()} line {i + 1}.")
        return "\n".join(lines)


def get(path: str, token: str) -> object:
    """GET a sync endpoint and return its `result`."""
    req = urllib.request.Request(
        BASE + path,
        headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)["result"]


def load_token(ha_config: Path) -> str:
    """Read the token from PAPRIKA_TOKEN or the HA config. Never printed."""
    if os.environ.get("PAPRIKA_TOKEN"):
        return os.environ["PAPRIKA_TOKEN"]
    entries = json.loads((ha_config / ".storage" / "core.config_entries").read_text())
    for entry in entries["data"]["entries"]:
        if entry["domain"] == "paprika":
            return entry["data"]["token"]
    sys.exit("No PAPRIKA_TOKEN and no paprika entry in the HA config")


def pick_meals(meals: list[dict], limit: int) -> list[dict]:
    """Keep recent meals plus a few old ones, so the date cutoff can be tested."""
    meals = sorted(meals, key=lambda m: m["date"])
    old = [m for m in meals if m["date"] < "2025-01-01"][-3:]
    recent = meals[-limit:]
    return old + recent


def main() -> None:
    """Capture, anonymise, leak-check and write the fixtures."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ha-config", type=Path, default=Path("config"))
    ap.add_argument("--meals", type=int, default=40)
    ap.add_argument("--recipes", type=int, default=6)
    args = ap.parse_args()
    token = load_token(args.ha_config)
    a = Anonymiser()
    raw = {e: get(f"sync/{e}", token) for e in LIST_ENDPOINTS}
    out: dict[str, object] = {}

    # Counters are revision numbers, not secrets; keep them as they are.
    out["status"] = raw["status"]

    out["mealtypes"] = [
        {
            **t,
            "uid": a.uid(t["uid"]),
            "name": a.word(
                "mealtype",
                ["Breakfast", "Lunch", "Dinner", "Snack", "Dessert"],
                t["name"],
            ),
        }
        for t in raw["mealtypes"]
    ]
    out["grocerylists"] = [
        {
            **g,
            "uid": a.uid(g["uid"]),
            "name": a.word("list", ["Groceries", "Hardware", "Party"], g["name"]),
            "reminders_list": a.word(
                "list", ["Groceries", "Hardware", "Party"], g["reminders_list"]
            ),
        }
        for g in raw["grocerylists"]
    ]
    out["groceryaisles"] = [
        {**x, "uid": a.uid(x["uid"]), "name": a.word("aisle", AISLES, x["name"])}
        for x in raw["groceryaisles"]
    ]
    out["groceryingredients"] = [
        {
            **x,
            "uid": a.uid(x["uid"]),
            "name": a.word("ingredient", INGREDIENTS, x["name"]),
            "aisle_uid": a.uid(x["aisle_uid"]),
        }
        for x in raw["groceryingredients"]
    ]
    out["categories"] = [
        {
            **c,
            "uid": a.uid(c["uid"]),
            "name": a.word("category", ["Mains", "Soups", "Baking", "Sides", "Quick"], c["name"]),
            "parent_uid": a.uid(c["parent_uid"]),
            "cookbook_uid": a.uid(c["cookbook_uid"]),
        }
        for c in raw["categories"]
    ]

    meals = pick_meals(raw["meals"], args.meals)
    planned_recipes = [m["recipe_uid"] for m in reversed(meals) if m.get("recipe_uid")]
    wanted = list(dict.fromkeys(planned_recipes))[: args.recipes]

    recipes_full = []
    for uid in wanted:
        r = get(f"sync/recipe/{uid}", token)
        recipes_full.append(r)
    names = {r["uid"]: r["name"] for r in recipes_full}

    out["meals"] = [
        {
            **m,
            "uid": a.uid(m["uid"]),
            "recipe_uid": a.uid(m["recipe_uid"]),
            "type_uid": a.uid(m["type_uid"]),
            "name": a.word("dish", DISHES, names.get(m["recipe_uid"], m["name"])),
        }
        for m in meals
    ]
    out["groceries"] = [
        {
            **g,
            "uid": a.uid(g["uid"]),
            "recipe_uid": a.uid(g["recipe_uid"]),
            "list_uid": a.uid(g["list_uid"]),
            "aisle_uid": a.uid(g["aisle_uid"]) or g["aisle_uid"],
            "aisle": a.word("aisle", AISLES, g["aisle"]),
            "name": a.word("ingredient", INGREDIENTS, g["name"]),
            "ingredient": a.word("ingredient", INGREDIENTS, g["ingredient"]),
            "recipe": a.word("dish", DISHES, g["recipe"]),
            "instruction": a.text(g["instruction"], "instruction"),
            # Quantities are usually "2" or "200 g"; mask anything wordier.
            "quantity": g["quantity"]
            if re.fullmatch(r"[\d\s./½¼¾]*(g|kg|ml|l|tsp|tbsp)?", g["quantity"] or "")
            else "1",
        }
        for g in raw["groceries"]
    ]
    # sync/recipes lists uid + hash for all recipes; keep fetched ones and a few more.
    kept = set(wanted) | {r["uid"] for r in raw["recipes"][:10]}
    hashes = {}
    out["recipes"] = []
    for r in raw["recipes"]:
        if r["uid"] in kept:
            hashes[r["uid"]] = a.hex(r["hash"])
            out["recipes"].append({"uid": a.uid(r["uid"]), "hash": hashes[r["uid"]]})
    out["photos"] = [
        {
            **p,
            "uid": a.uid(p["uid"]),
            "recipe_uid": a.uid(p["recipe_uid"]),
            "name": f"Photo {i + 1}",
            "filename": f"{a.uid(p['uid'])}.jpg",
            "hash": a.hex(p["hash"]),
        }
        for i, p in enumerate(raw["photos"])
        if p["recipe_uid"] in kept
    ]
    out["menus"] = [
        {
            **m,
            "uid": a.uid(m["uid"]),
            "name": a.word("menu", ["Weeknights", "Batch Cook", "Holiday"], m["name"]),
            "notes": a.text(m["notes"], "note"),
        }
        for m in raw["menus"]
    ]
    out["menuitems"] = [
        {
            **m,
            "uid": a.uid(m["uid"]),
            "recipe_uid": a.uid(m["recipe_uid"]),
            "menu_uid": a.uid(m["menu_uid"]),
            "type_uid": a.uid(m["type_uid"]),
            "name": a.word("dish", DISHES, names.get(m["recipe_uid"], m["name"])),
        }
        for m in raw["menuitems"]
    ]
    for r in recipes_full:
        fake = a.uid(r["uid"])
        for k in (
            "description",
            "notes",
            "nutritional_info",
            "source",
            "source_url",
            "image_url",
            "photo",
            "photo_url",
            "photo_large",
        ):
            a.note(r.get(k))
        out[f"recipe_{fake}"] = {
            **r,
            "uid": fake,
            "name": a.word("dish", DISHES, r["name"]),
            "hash": hashes.get(r["uid"]) or a.hex(r["hash"]),
            "ingredients": a.text(r["ingredients"], "ingredients"),
            "directions": a.text(r["directions"], "step"),
            "description": a.text(r["description"], "description"),
            "notes": a.text(r["notes"], "note"),
            "nutritional_info": a.text(r["nutritional_info"], "nutrition"),
            "source": "example.com" if r["source"] else "",
            "source_url": f"https://example.com/recipes/{fake.lower()}" if r["source_url"] else "",
            "image_url": f"https://example.com/images/{fake.lower()}.jpg" if r["image_url"] else "",
            "photo": f"{fake}.jpg" if r["photo"] else r["photo"],
            "photo_large": f"{fake}-large.jpg" if r.get("photo_large") else r.get("photo_large"),
            "photo_hash": a.hex(r["photo_hash"]),
            "photo_url": f"https://example.com/photos/{fake.lower()}.jpg"
            if r.get("photo_url")
            else r.get("photo_url"),
            "categories": [a.uid(c) for c in r["categories"]],
            "cookbook_uid": a.uid(r["cookbook_uid"]),
        }

    # Leak check: no original identifying string may survive in the output, either
    # as a whole value or line, or (for long values like URLs) as a substring.
    values: set[str] = set()

    def walk(v: object) -> None:
        if isinstance(v, str):
            values.add(v.strip())
            values.update(line.strip() for line in v.splitlines())
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(out)
    blob = json.dumps(out, ensure_ascii=False)
    stand_ins = {v.lower() for pool in a.pools.values() for v in pool.values()}
    leaks = [
        s
        for s in a.originals
        if s.lower() not in stand_ins
        and not re.fullmatch(r"[\d\s./:-]+", s)
        and (s in values or (len(s) >= MIN_SUBSTRING_LEAK and s in blob))
    ]
    if leaks:

        def where(v: object, path: str = "") -> Iterator[str]:
            if isinstance(v, dict):
                for k, x in v.items():
                    yield from where(x, f"{path}.{k}")
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    yield from where(x, f"{path}[{i}]")
            elif isinstance(v, str) and any(s in v for s in leaks):
                yield re.sub(r"\[\d+\]", "[]", path)

        print("Leaks at:", sorted(set(where(out))), file=sys.stderr)
        sys.exit(
            f"Refusing to write: {len(leaks)} original values found in output "
            f"(lengths: {sorted(len(s) for s in leaks)[:10]})"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    for name, payload in out.items():
        (OUT / f"{name}.json").write_text(
            json.dumps({"result": payload}, indent=2, ensure_ascii=False) + "\n"
        )
    print(f"Wrote {len(out)} fixtures to {OUT}")


if __name__ == "__main__":
    main()
