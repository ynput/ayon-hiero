# Hiero addon

**Primary guidance:** [`.agents-main/AGENTS.md`](.agents-main/AGENTS.md) and
its `fragments/host-integration.md` — universal AYON rules, read this file
first. This file *extends* that shared guidance with repository-specific facts
only; it never replaces, overrides, or contradicts it.

## What this addon is

Hiero integration for AYON — host addon implementing publish, load, and create
plugins inside Foundry's Hiero. [`package.py`](package.py),
[`README.md`](README.md).

- **Server addon** — [`server/__init__.py`](server/__init__.py): `HieroAddon`
  with `HieroSettings` model, serves settings to the AYON server.
- **Client addon** — [`client/ayon_hiero/addon.py`](client/ayon_hiero/addon.py):
  `HieroAddon(AYONAddon, IHostAddon)`, configures `HIERO_PLUGIN_PATH` with
  `api/startup`, adds `vendor/` to `PYTHONPATH`, registers `.hrox` workfiles.
- **Client structure** — `client/ayon_hiero/` has `api/`, `plugins/`, `vendor/`;
  no top-level `startup/`, `hooks/`, or `otio/`.

## Repo facts

- Addon name: `hiero`; label `Hiero`; client code dir `ayon_hiero`
  (`client_dir` in `package.py`).
- `package.py` declares the version compatibility constraints — read
  `package.py:ayon_required_addons` (and `ayon_server_version` /
  `ayon_launcher_version` / `ayon_compatible_addons`, if set) there before
  touching any compatibility-import branch. Values change with releases, so
  they are not restated here.
- Settings model: `HieroSettings` in `server/settings/main.py`, exposed
  under the settings category **`hiero`** (client code reads it
  via `get_current_project_settings()["hiero"]`).
- Settings override migrations live in
  [`server/settings/conversions.py`](server/settings/conversions.py)
  (`_convert_*` helpers chained through `convert_settings_overrides`). Any
  settings rename must add a conversion there — never rename a settings field
  without one.
- Style: [`ruff.toml`](ruff.toml) at repo root — line length **79**, select
  `["E4", "E7", "E9", "F", "W"]`; vendor excluded:
  `client/ayon_hiero/vendor`, `client/ayon_hiero/api/startup/Python`.
- Tests: none — validate with the narrowest relevant lint/build/package
  command. CI runs only Ruff (`.github/workflows/pr_linting.yml`).

## Development checks

```bash
ruff check .
ruff format --check .
python create_package.py --skip-zip
```

Validation requiring the host application (Hiero itself) cannot run in an
agent session; describe the manual steps a reviewer must run instead.

## Spec Kit

### Spec Kit

Spec-driven development setup: [SPEC_KIT.md](SPEC_KIT.md). This repo is
harness-agnostic — no agent config is committed; each teammate installs their
own Spec Kit integration and links `.agents-main` via
`python agentic_setup.py install`. The AYON constitution is loaded only for
`/speckit.*` work; `.specify/memory/ayon-addon-constitution.md` is this
repository's tracked extension layer (it may only tighten the shared
constitution).
