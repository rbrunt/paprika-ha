# Test fixtures

Anonymised `sync/*` payloads from a real Paprika account, captured on 2026-11-15
with `scripts/capture_fixtures.py`. Each file is `{"result": ...}`, as the API returns it.

Shapes, types, nulls, dates and uid cross-references are real. Uids, names, recipe
text, URLs, hashes and photo names are stand-ins, so values like aisle-to-item
pairings are not meaningful. The script refuses to write if any original value
survives. Re-run it to refresh; random hashes mean a re-run changes every file.

- `meals.json`: the latest 40 meals plus 3 from before 2025 (for the date cutoff).
- `recipe_<uid>.json`: full recipes behind the most recent planned meals.
- `recipes.json`: uid/hash list for those recipes plus a few others.

## API behaviour verified against the live account (2026-11-15)

The API is undocumented. These were checked by experiment, not from docs.

- `sync/status` counters are per-entity revision numbers, not item counts.
  Repeated reads return the same values (30 back-to-back calls, no rate limiting).
- A `POST sync/groceries/` bumps only `groceries`, by one per item in the payload,
  even when the item is unchanged. Add, tick and `"deleted": true` all count.
- Edits in the Paprika app bumped only the matching counter: grocery add, rename
  and aisle change (`groceries`), new ingredient-to-aisle mapping
  (`groceryingredients`), meal add, move and delete (`meals`), recipe text edit
  (`recipes`, plus that recipe's `hash` in `sync/recipes`).
- In a 15-second poll over those edits, content never changed without its counter
  changing.
- No HTTP caching: no `ETag`, `Last-Modified` or `Cache-Control`. Conditional
  requests return a full 200, and `HEAD` returns 405. Query params such as `since`
  and `limit` are ignored on `sync/meals`.
- `sync/status` also returns `cookbooks` and `recipesearches`. Those endpoints and
  `sync/pantrylocations` return 404.
- `groceries[].recipe` can be `null`, and `meals[].type` is a legacy integer.

Not yet verified: whether a rating-only, photo-only or trash/restore change to a
recipe bumps `recipes` or changes its hash.
