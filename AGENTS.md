# AGENTS.md

Unofficial Home Assistant integration for Paprika Recipe Manager, distributed via HACS. Domain `paprika`, source in `custom_components/paprika/`. More in [DEVELOPING.md](./DEVELOPING.md) and [CONTRIBUTING.md](./CONTRIBUTING.md).

## Layout

- `api.py`: `PaprikaApi` (aiohttp) and `TypedDict` payload models.
- `coordinator.py`: polls every 15 min; refetches only when `sync/status` changes.
- `calendar.py`, `todo.py`: meal plan calendars, grocery list todo lists.
- `config_flow.py`, `strings.json`, `translations/en.json`: setup UI and text.
- `manifest.json`: version set by `scripts/bump_version_and_release`. Don't edit by hand.

## Commands

uv manages the environment (`pyproject.toml`, `uv.lock`, `.python-version`). Run tools with `uv run`.

- `scripts/setup`: `uv sync`.
- `scripts/lint`: ruff format + fix. CI runs it in check mode.
- `scripts/develop`: local Home Assistant using `config/`.
- `uv run pytest`: tests. CI runs these too.
- `scripts/capture_fixtures.py`: refresh `tests/fixtures/` from a real account (anonymised).

## Conventions

- Target the HA version pinned in `hacs.json` and `pyproject.toml`. Line length 100.
- The Paprika API is undocumented. Note behaviour found by experiment, and how it was verified, in a comment or the PR. Known behaviour: `tests/fixtures/README.md`.
- User-facing strings go in `strings.json` and `translations/en.json`. Update the README when behaviour changes.
- HA patterns: reads go through the coordinator; entities never call the API to read; options go through the config/options flow.
- Lazy `%s` logging. Never log tokens or passwords.
- New dependencies need a strong reason. Add with `uv add --group <dev|test>`.

## Design

- Keep the integration thin: mirror Paprika's data, no heuristics of our own. If one is worthwhile, make it opt-in and labelled as a best guess.
- Changes to what existing users see are opt-in (off by default).
- Use a `SelectSelector` rather than a boolean for options that may grow more values.
- Caching lives in `PaprikaApi`, applied consistently, and only for a stated need.
- One bad record must not break setup: skip it and log a warning that includes the record.
- One behaviour change per PR. No unrelated reformatting.

## Testing

- Bug fixes need a regression test that fails without the fix. New behaviour needs tests for the success path and the main failure cases.
- Run `uv run pytest` and `scripts/lint` before finishing. Report only what you ran.
- Don't weaken or delete assertions to make a test pass.
- Tests live in `tests/test_<module>.py`, one behaviour per test, named for the behaviour.
- Every request goes to `FakePaprika` (`tests/fake_paprika.py`) through an autouse fixture. Don't add per-test mocks; drive the fake instead (`paprika.edit`, `edit_recipe`, `fail`, `requests`).
- Test at the right layer. `api.py`: through the fake, asserting on the requests and POST bodies. Coordinator: polling and caching via `paprika.requests`. Entities and config flow: through `hass` with a `MockConfigEntry`, using service calls and states.
- Never contact the real Paprika service or use real credentials. Fixtures must stay anonymised.
- No sleeps or real timers. Use `async_fire_time_changed` or freezegun.
