#!/usr/bin/env python
"""Set up agentic instructions and Spec Kit integration for this repo.

Requires Python 3.9+.

Cross-platform one-time setup for agentic development, replacing the
manual steps documented in ``SPEC_KIT.md``:

- ensure the shared AYON agent instructions repository
  (``ayon-agentic-instructions``) is cloned next to this repository
- link it as ``.agents-main`` (symlink on macOS/Linux; directory
  junction on Windows, which needs no administrator privileges)
- link the three shared constitution files (pointer stub
  ``constitution.md``, canonical ``ayon-constitution.md`` and evidence
  annex ``ayon-constitution-evidence.md``) from the shared repository's
  ``.specify/memory/`` into this repository's ``.specify/memory/``
  (on Windows a real symlink is attempted first; if Developer Mode is
  not available the user is asked to enable it, copy the files
  instead, or skip)
- copy the addon-constitution seed ``ayon-addon-constitution.md`` as a
  real, version-controlled file owned by this repository (a committed
  ``.gitignore`` exception keeps it tracked; ``--force`` refreshes it
  from the shared seed, discarding local amendments)
- copy the repository instruction templates from the shared repository's
  ``addon_repo_setup/`` folder into this repository root, stripping the
  ``template-`` prefix (``template-AGENTS.md`` -> ``AGENTS.md``,
  ``template-SPEC_KIT.md`` -> ``SPEC_KIT.md``); existing files are
  preserved unless ``--force`` is given, so finished guidance is never
  clobbered by a re-run
- verify the copied instruction files (``check``) contain no leftover
  generation markers or ``[PLACEHOLDER]`` tokens — for CI / pre-commit use
- optionally install the ``specify`` CLI (via ``uv``), run the
  integration install for the chosen agent harness, and install the
  AYON constitution governance preset and extension (which registers
  the mandatory ``after_constitution`` verification hook) from the
  shared repository, plus the opt-in ``bug`` extension for the
  bug-fixing workflow (``--specify``)
- ensure the configurable harness / Spec Kit ignore policy in
  ``GITIGNORE_SNIPPET`` is present in the addon repository's ``.gitignore``
  (and ``.agents-main`` is also ignored by git)

Usage::

    python agentic_setup.py install
    python agentic_setup.py check
    python agentic_setup.py install --specify --integration=goose
    python agentic_setup.py install --force --specify \\
        --integration=goose --arbitrary-arg arbitrary-arg-value

Unknown options are passed verbatim to ``specify integration
install <integration>``, so the script does not need updates when the
specify CLI changes its interface. Place the script's own options
(``--force``, ``--integration``, ``--constitution``) before the
pass-through arguments, or separate them with ``--``.

Windows notes:
- ``.agents-main`` is created as a directory junction via
  ``cmd /c mklink /J`` — junctions need no administrator rights and
  no Developer Mode. Do **not** use ``ln -s`` in Git Bash: it copies
  instead of linking.
- The constitution symlinks are machine-local (gitignored) and are
  (re)created by this script on every machine. A real symlink is
  attempted first (works when Developer Mode is enabled); otherwise
  the user is asked to enable Developer Mode and retry, copy the shared
  constitution files instead (they are added to ``.gitignore`` and must
  be refreshed by re-running this script after shared-repo amendments),
  or skip — which also skips the specify installation.
"""

import argparse
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from typing import List, Optional

CURRENT_ROOT: str = os.path.dirname(os.path.abspath(__file__))
IS_WINDOWS: bool = platform.system().lower() == "windows"


SHARED_REPO_URL: str = "https://github.com/ynput/ayon-agentic-instructions"
SHARED_REPO_DIR: str = os.path.join(
    CURRENT_ROOT, "..", "ayon-agentic-instructions"
)
AGENTS_MAIN: str = os.path.join(CURRENT_ROOT, ".agents-main")
AGENTS_MAIN_REL: str = "../ayon-agentic-instructions"
SPECIFY_CLI_URL: str = "git+https://github.com/github/spec-kit.git"
# Shared constitution files: local name in .specify/memory -> source name
# in the shared repository's .specify/memory/. All three are symlinked
# (machine-local, gitignored). 'constitution.md' is the pointer stub the
# Spec Kit commands read; 'ayon-constitution.md' is the canonical shared
# constitution; 'ayon-constitution-evidence.md' is its evidence annex.
MEMORY_FILES: List[tuple[str, str]] = [
    ("constitution.md", "constitution.md"),
    ("ayon-constitution.md", "ayon-constitution.md"),
    ("ayon-constitution-evidence.md", "ayon-constitution-evidence.md"),
]
# The addon-constitution seed is COPIED (not symlinked): each consumer
# repository owns and version-controls its own extension constitution.
ADDON_CONSTITUTION_NAME: str = "ayon-addon-constitution.md"
# Governance preset/extension shipped by the shared repository, wrapped
# around /speckit.constitution and the after_constitution hook.
GOVERNANCE_PRESET_ID: str = "ayon-constitution"
GOVERNANCE_PRESET_REL: str = os.path.join(
    "..", "ayon-agentic-instructions", ".specify", "presets",
    "ayon-constitution",
)
GOVERNANCE_EXTENSION_REL: str = os.path.join(
    "..", "ayon-agentic-instructions", ".specify", "extensions",
    "ayon-constitution",
)
# Opt-in Spec Kit bug extension (bug-fixing workflow); installed from
# the extension registry, records live in '.specify/bugs/'.
BUG_EXTENSION_ID: str = "bug"
# Repository instruction templates live in this folder of the shared
# repository; each 'template-<name>.md' is copied to '<name>.md' in the
# consumer repository root (e.g. template-AGENTS.md -> AGENTS.md).
TEMPLATE_DIR_NAME: str = "addon_repo_setup"
TEMPLATE_PREFIX: str = "template-"
# Fallback instruction files checked by 'check' when the shared repository
# is unavailable (e.g. in CI): the files this script is known to copy.
DEFAULT_INSTRUCTION_FILES: List[str] = ["AGENTS.md", "SPEC_KIT.md"]
GENERATION_MARKER: str = "GENERATION INSTRUCTIONS"
PLACEHOLDER_RE = re.compile(r"\[[A-Z][A-Z0-9_]*\]")
CONSTITUTION_LINK: str = os.path.join(
    CURRENT_ROOT, ".specify", "memory", "constitution.md"
)
CONSTITUTION_REL_TARGET: str = "../../.agents-main/.specify/memory/{}"
GITIGNORE_COPIED: List[str] = [
    ".specify/memory/constitution.md",
    ".specify/memory/ayon-constitution.md",
    ".specify/memory/ayon-constitution-evidence.md",
]
# Managed as one configurable block so new harnesses, Spec Kit artifacts, or
# durable-record exceptions can be added here without changing setup logic.
GITIGNORE_SNIPPET: str = """# Agent harness / Spec Kit state (this repo is harness-agnostic)
# Each teammate installs their own AI-coding-agent integration and links
# .agents-main themselves (see SPEC_KIT.md). Never commit harness output.
.agents/
.agents-main
.github/skills/
.github/agents/
.github/prompts/
.github/copilot-instructions.md
.goose/
.kilo/
.zed/
.specify/*
!.specify/memory/
.specify/memory/*
# Bug triage records (speckit.bug.assess/fix/test) — durable, commit them:
!.specify/bugs/
.specify/bugs/*
!.specify/bugs/*/
.specify/bugs/*/*
!.specify/bugs/*/assessment.md
!.specify/bugs/*/fix.md
!.specify/bugs/*/test.md
# (keeps only the tracked constitution symlink and bug reports above)

# Feature spec records — commit the durable record for agents
# (spec = what/why, plan = how/decisions, tasks = what was done);
# ignore plan-phase working artifacts (research, data-model, quickstart,
# contracts, checklists) — regenerate them with /speckit.plan if needed.
specs/*
!specs/*/
specs/*/*
!specs/*/spec.md
!specs/*/plan.md
!specs/*/tasks.md

# Common agent config dirs (add any further agent config here)
.claude/
CLAUDE.md
.cursor/
.copilot/
.windsurf/
.grok/
.codex/
.gemini/

!.specify/memory/ayon-addon-constitution.md"""
DEFAULT_INTEGRATION: str = "copilot"

LOG = logging.getLogger("agentic_setup")


# ---------------------------------------------------------------------------
# Low level helpers
# ---------------------------------------------------------------------------

def _is_reparse_point(path: str) -> bool:
    """Check if a path is a Windows junction/reparse point."""
    if not IS_WINDOWS:
        return False
    try:
        st_attrs = os.lstat(path).st_file_attributes
    except OSError:
        return False
    return bool(st_attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _same_target(link_path: str, target_path: str) -> bool:
    """Check if a link (symlink or junction) points to target path."""
    try:
        real_link = os.path.realpath(link_path)
        real_target = os.path.realpath(target_path)
    except OSError:
        return False
    return os.path.normcase(real_link) == os.path.normcase(real_target)


def _remove_link(path: str) -> None:
    """Remove a symlink (or junction) without touching its target."""
    if IS_WINDOWS:
        # 'rmdir' removes the reparse point only, never the target.
        os.rmdir(path)
    else:
        os.remove(path)


def _run(
    args: List[str],
    cwd: Optional[str] = None,
    capture: bool = False,
) -> int:
    """Run a subprocess, streaming its output, return its exit code."""
    LOG.debug("Running: %s", " ".join(args))
    try:
        return subprocess.run(
            args,
            cwd=cwd or CURRENT_ROOT,
            check=False,
            **({"capture_output": True, "text": True} if capture else {}),
        ).returncode
    except OSError as error:
        LOG.error("Failed to run %r: %s", args[0], error)
        return 1


def _print(text: str) -> None:
    """Print to stdout and flush (for interactive prompts)."""
    print(text)
    sys.stdout.flush()


def _ask(question: str, default: str) -> str:
    """Ask the user a question, return their (lowercased) answer."""
    if not sys.stdin.isatty():
        return default
    try:
        return input("{}: ".format(question)).strip().lower()
    except EOFError:
        return default


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def ensure_shared_repo() -> bool:
    """Clone the shared instructions repository if it is missing."""
    if os.path.isfile(os.path.join(SHARED_REPO_DIR, "AGENTS.md")):
        LOG.info("Shared instructions found: %s", SHARED_REPO_DIR)
        return True
    if os.path.exists(SHARED_REPO_DIR):
        LOG.error(
            "%s exists but does not look like the shared instructions "
            "repository (no AGENTS.md). Fix or remove it manually.",
            SHARED_REPO_DIR,
        )
        return False
    if shutil.which("git") is None:
        LOG.error(
            "'git' not found. Install git or clone manually:\n"
            "    git clone %s %s", SHARED_REPO_URL, AGENTS_MAIN_REL,
        )
        return False
    LOG.info("Cloning shared instructions repository...")
    if _run(["git", "clone", SHARED_REPO_URL, SHARED_REPO_DIR]) != 0:
        LOG.error("Cloning of shared instructions failed.")
        return False
    return True


def setup_agents_main(force: bool = False) -> bool:
    """Create the '.agents-main' link to the shared instructions repo.

    Symlink on macOS/Linux, directory junction on Windows (junctions
    can be created by non-admin users and need no Developer Mode).
    """
    if os.path.exists(AGENTS_MAIN) or os.path.islink(AGENTS_MAIN):
        if os.path.islink(AGENTS_MAIN) or _is_reparse_point(AGENTS_MAIN):
            if _same_target(AGENTS_MAIN, SHARED_REPO_DIR):
                LOG.info("'.agents-main' link already OK, skipping.")
                return True
            if not force:
                LOG.warning(
                    "'.agents-main' exists but points elsewhere. "
                    "Re-run with --force to replace it."
                )
                return False
            _remove_link(AGENTS_MAIN)
        elif os.path.isdir(AGENTS_MAIN):
            LOG.error(
                "'.agents-main' is a REAL DIRECTORY (probably created by "
                "'ln -s' in Git Bash, which copies instead of linking). "
                "It will NOT receive shared-repo amendments. Re-run with "
                "--force to replace it with a proper link."
            )
            return False
        else:
            if not force:
                LOG.warning(
                    "'.agents-main' exists as a file. "
                    "Re-run with --force to replace it."
                )
                return False
            os.remove(AGENTS_MAIN)

    if IS_WINDOWS:
        result = _run([
            "cmd", "/c", "mklink", "/J", ".agents-main",
            os.path.abspath(SHARED_REPO_DIR),
        ])
    else:
        try:
            os.symlink(AGENTS_MAIN_REL, AGENTS_MAIN)
            result = 0
        except OSError as error:
            LOG.error("Could not create symlink: %s", error)
            result = 1
    if result == 0 and _same_target(AGENTS_MAIN, SHARED_REPO_DIR):
        LOG.info("'.agents-main' linked to shared instructions.")
        return True
    LOG.error("Failed to create '.agents-main' link.")
    return False


def _constitution_link_paths() -> List[str]:
    """Full paths of constitution memory files inside .specify/memory."""
    return [
        os.path.join(CURRENT_ROOT, ".specify", "memory", local_name)
        for local_name, _ in MEMORY_FILES
    ]


def _ensure_gitignore_entries(paths: List[str]) -> None:
    """Add individual .gitignore entries idempotently."""
    path = os.path.join(CURRENT_ROOT, ".gitignore")
    lines = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    existing = {line.strip() for line in lines}
    missing = [p for p in paths if p not in existing]
    if not missing:
        return
    with open(path, "a", encoding="utf-8") as handle:
        if lines and lines[-1].strip():
            handle.write("\n")
        for entry in missing:
            handle.write(entry + "\n")
            LOG.info("Added %r to .gitignore", entry)


def _ensure_gitignore_snippet() -> None:
    """Append the managed harness/Spec Kit ignore policy once.

    The complete block is intentionally configured in ``GITIGNORE_SNIPPET``
    rather than spread across setup code. Existing user rules are preserved.
    """
    path = os.path.join(CURRENT_ROOT, ".gitignore")
    snippet = GITIGNORE_SNIPPET.rstrip() + "\n"
    existing = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    if snippet in existing:
        return
    with open(path, "a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        if existing and existing.rstrip():
            handle.write("\n")
        handle.write(snippet)
    LOG.info("Added managed agent/Spec Kit rules to .gitignore")


def _copy_constitution() -> None:
    """Copy constitution files from shared repo into .specify/memory."""
    for dest_path, (_, source_name) in zip(
        _constitution_link_paths(), MEMORY_FILES
    ):
        source = os.path.join(
            SHARED_REPO_DIR, ".specify", "memory", source_name
        )
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(source, dest_path)
        LOG.info("Copied %s", dest_path)
    # Copied files are 'tracked' in git - ignore them to avoid accidental
    # commits of machine-local copies.
    _ensure_gitignore_entries(GITIGNORE_COPIED)


def _create_constitution_links() -> bool:
    """Symlink constitution memory files into .specify/memory."""
    for dest_path, (_, source_name) in zip(
        _constitution_link_paths(), MEMORY_FILES
    ):
        target = CONSTITUTION_REL_TARGET.format(source_name)
        expected_abs = os.path.normpath(
            os.path.join(
                SHARED_REPO_DIR, ".specify", "memory", source_name
            )
        )
        if os.path.islink(dest_path) or _is_reparse_point(dest_path):
            if os.path.exists(dest_path) and _same_target(
                dest_path, expected_abs
            ):
                continue
            # Stale link (old target layout or broken): replace it.
            _remove_link(dest_path)
        elif os.path.exists(dest_path):
            os.remove(dest_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        try:
            os.symlink(target, dest_path)
        except OSError as error:
            LOG.error("Symlink for %s failed: %s", source_name, error)
            return False
    LOG.info("Constitution links created in .specify/memory.")
    return True


def _ask_constitution_fallback() -> str:
    """Ask what to do when a real symlink is not possible on Windows.

    Returns one of: 'retry', 'copy', 'skip'.
    """
    _print(
        "\nCould not create a real symlink for the constitution.\n"
        "This usually means Developer Mode is disabled.\n"
        "Options:\n"
        "  1) I enabled Developer Mode (Settings > System > For\n"
        "     developers) - retry the symlink\n"
        "  2) Copy the constitution files instead (amendments will not\n"
        "     propagate automatically; re-run this script after updates)\n"
        "  3) Skip (the specify installation will be skipped too)"
    )
    answer = _ask("Choose [1/2/3] (Enter = 3)", "3")
    if answer in ("1", "retry"):
        return "retry"
    if answer in ("2", "copy"):
        return "copy"
    return "skip"


def _constitution_links_ok() -> bool:
    """Check every shared constitution link exists with the right target."""
    for dest_path, (_, source_name) in zip(
        _constitution_link_paths(), MEMORY_FILES
    ):
        if not os.path.islink(dest_path) and not _is_reparse_point(dest_path):
            return False
        expected_abs = os.path.normpath(
            os.path.join(
                SHARED_REPO_DIR, ".specify", "memory", source_name
            )
        )
        if not _same_target(dest_path, expected_abs):
            return False
        if not os.path.exists(dest_path):
            return False
    return True


def setup_constitution(mode: str) -> bool:
    """Repair the shared constitution links in '.specify/memory/'.

    On macOS/Linux symlinks are used. On Windows a real symlink is
    attempted first (works when Developer Mode is enabled); otherwise
    the user chooses to retry after enabling Developer Mode, copy the
    files instead, or skip.
    """
    if _constitution_links_ok():
        LOG.info("Constitution links already OK, skipping.")
        return True

    if IS_WINDOWS:
        while True:
            # Remove a plain-text/junk checked-out file first, then try
            # a real symlink (needs Developer Mode or elevation).
            if os.path.lexists(CONSTITUTION_LINK) and not os.path.islink(
                CONSTITUTION_LINK
            ):
                os.remove(CONSTITUTION_LINK)
            if _create_constitution_links():
                return True
            if mode == "symlink":
                LOG.error(
                    "Symlink creation failed. Enable Developer Mode "
                    "(Settings > System > For developers), or re-run "
                    "with --constitution=copy|skip."
                )
                return False
            choice = _ask_constitution_fallback()
            if choice == "retry":
                continue
            if choice == "copy":
                _copy_constitution()
                return True
            LOG.warning("Skipping constitution setup.")
            return False

    # macOS/Linux: repair missing, broken, or stale-target links.
    if os.path.exists(CONSTITUTION_LINK) and not os.path.islink(
        CONSTITUTION_LINK
    ):
        LOG.warning(
            "'.specify/memory/constitution.md' exists but is not a "
            "symlink - replacing it with the correct symlink."
        )
        os.remove(CONSTITUTION_LINK)
    return _create_constitution_links()


def install_specify(
    integration: str,
    specify_args: Optional[List[str]] = None,
) -> bool:
    """Install the 'specify' CLI (via uv) and the agent integration."""
    if shutil.which("specify") is None:
        uv_path = shutil.which("uv")
        if uv_path is None:
            LOG.error(
                "Neither 'specify' nor 'uv' was found on PATH.\n"
                "Install uv first, e.g.:\n"
                "  - macOS/Linux:  curl -LsSf "
                "https://astral.sh/uv/install.sh | sh\n"
                "  - Windows (PowerShell):  irm "
                "https://astral.sh/uv/install.ps1 | iex\n"
                "then re-run this command."
            )
            return False
        LOG.info("Installing 'specify' CLI via uv...")
        if _run([
            uv_path, "tool", "install", "specify-cli",
            "--from", SPECIFY_CLI_URL,
        ]) != 0:
            LOG.error("'specify' CLI installation failed.")
            return False
    else:
        LOG.info("'specify' CLI already installed, skipping.")

    args = ["specify", "integration", "install", integration]
    args.extend(specify_args or [])
    LOG.info("Installing integration: %s", integration)
    if _run(args) != 0:
        LOG.error(
            "Integration install failed. Check available integrations "
            "with: specify integration list"
        )
        return False
    LOG.info(
        "Integration installed. Verify the expected harness folder "
        "(e.g. .goose/, .github/skills/, ...) was created."
    )
    return True


def _copy_addon_constitution(force: bool = False) -> bool:
    """Copy the addon-constitution seed as this repository's own file.

    Unlike the shared constitution files (symlinked, machine-local), the
    addon extension constitution is owned and version-controlled by this
    repository, so it is copied once and kept tracked via a committed
    '.gitignore' exception. Local amendments are preserved unless
    'force' refreshes the file from the shared seed.
    """
    source = os.path.join(
        SHARED_REPO_DIR, ".specify", "memory", ADDON_CONSTITUTION_NAME
    )
    dest = os.path.join(
        CURRENT_ROOT, ".specify", "memory", ADDON_CONSTITUTION_NAME
    )
    if not os.path.isfile(source):
        LOG.error(
            "Addon-constitution seed missing in the shared repository: %s",
            source,
        )
        return False
    if os.path.islink(dest) or _is_reparse_point(dest):
        # A misconfigured earlier setup left a link - replace with a
        # real file.
        _remove_link(dest)
    if os.path.exists(dest):
        if not force:
            LOG.info(
                "'%s' already present, skipping (re-run with --force to "
                "refresh from the seed, discarding local amendments).",
                ADDON_CONSTITUTION_NAME,
            )
            return True
        LOG.info(
            "Refreshing '%s' from the shared seed (--force).",
            ADDON_CONSTITUTION_NAME,
        )
        os.remove(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(source, dest)
    LOG.info(
        "Copied %s (tracked, owned by this repository).", dest
    )
    return True


def _preset_ids() -> List[str]:
    """Return installed preset IDs from the '.specify/presets/.registry' file.

    Read directly instead of parsing CLI output: 'specify preset list'
    does not support --json in all spec-kit versions.
    """
    registry_file = os.path.join(
        CURRENT_ROOT, ".specify", "presets", ".registry"
    )
    if not os.path.isfile(registry_file):
        return []
    try:
        with open(registry_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    presets = data.get("presets", {}) if isinstance(data, dict) else {}
    if not isinstance(presets, dict):
        return []
    return [
        preset_id
        for preset_id, meta in presets.items()
        if isinstance(meta, dict) and meta.get("enabled", True)
    ]


def _installed_extensions() -> List[str]:
    """Return installed extension IDs from '.specify/extensions.yml'.

    Minimal stdlib parsing (the script avoids non-stdlib dependencies);
    only the top-level 'installed' list is read.
    """
    config_file = os.path.join(
        CURRENT_ROOT, ".specify", "extensions.yml"
    )
    if not os.path.isfile(config_file):
        return []
    installed: List[str] = []
    in_installed = False
    try:
        with open(config_file, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.rstrip("\n")
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if line[0].isspace() or stripped.startswith("- "):
                    # List item: '- <value>' (the CLI writes items
                    # unindented, dict hooks are nested).
                    if in_installed and stripped.startswith("- ") \
                            and ": " not in stripped:
                        installed.append(stripped[2:].strip())
                else:
                    in_installed = stripped == "installed:"
    except OSError:
        return []
    return [item for item in installed if item]


def install_governance(force: bool = False) -> bool:
    """Install the AYON constitution governance preset and extension.

    The preset wraps /speckit.constitution so amendments are routed to
    the correct constitution file (shared 'ayon-constitution.md' in the
    shared repository, per-addon 'ayon-addon-constitution.md' in
    consumer repositories). The extension registers the mandatory
    'after_constitution' verification hook.
    """
    if shutil.which("specify") is None:
        LOG.error(
            "'specify' CLI not found - re-run with --specify to install "
            "it before the governance preset/extension."
        )
        return False

    ids = _preset_ids()
    if GOVERNANCE_PRESET_ID in ids and not force:
        LOG.info("Governance preset already installed, skipping.")
    else:
        if GOVERNANCE_PRESET_ID in ids:
            _run(["specify", "preset", "remove", GOVERNANCE_PRESET_ID])
        if _run(["specify", "preset", "add", "--dev",
                 GOVERNANCE_PRESET_REL]) != 0:
            LOG.error("Governance preset installation failed.")
            return False

    extension_args = [
        "specify", "extension", "add", GOVERNANCE_EXTENSION_REL, "--dev",
    ]
    if GOVERNANCE_PRESET_ID in _installed_extensions() and not force:
        LOG.info("Governance extension already installed, skipping.")
        LOG.info("Governance preset and extension installed.")
        return True
    if force:
        extension_args.append("--force")
    if _run(extension_args) != 0:
        LOG.error("Governance extension installation failed.")
        return False
    LOG.info("Governance preset and extension installed.")
    return True


def install_bug_extension(force: bool = False) -> bool:
    """Install the opt-in Spec Kit 'bug' extension.

    Provides the ``/speckit-bug-assess`` / ``-fix`` / ``-test`` workflow
    whose records are kept in '.specify/bugs/' (durable, tracked via
    '.gitignore' exceptions; see SPEC_KIT.md). Non-fatal on failure: the
    rest of the setup does not depend on it.
    """
    if shutil.which("specify") is None:
        LOG.error(
            "'specify' CLI not found - re-run with --specify to install "
            "it before the bug extension."
        )
        return False
    if BUG_EXTENSION_ID in _installed_extensions() and not force:
        LOG.info("Bug extension already installed, skipping.")
        return True
    args = ["specify", "extension", "add", BUG_EXTENSION_ID]
    if force:
        args.append("--force")
    if _run(args) != 0:
        LOG.warning(
            "Bug extension installation failed - install it manually "
            "with: specify extension add bug"
        )
        return False
    LOG.info("Bug extension installed.")
    return True


def _instruction_templates() -> List[tuple[str, str]]:
    """Return (source, destination) pairs for instruction templates.

    Sources are ``template-*.md`` files in the shared repository's
    ``addon_repo_setup/`` folder; destinations drop the ``template-``
    prefix and land in this repository root.
    """
    source_dir = os.path.join(SHARED_REPO_DIR, TEMPLATE_DIR_NAME)
    if not os.path.isdir(source_dir):
        return []
    pairs: List[tuple[str, str]] = []
    for name in sorted(os.listdir(source_dir)):
        if not name.startswith(TEMPLATE_PREFIX) or not name.endswith(".md"):
            continue
        source = os.path.join(source_dir, name)
        if not os.path.isfile(source):
            continue
        destination = os.path.join(
            CURRENT_ROOT, name[len(TEMPLATE_PREFIX):]
        )
        pairs.append((source, destination))
    return pairs


def copy_instruction_templates(force: bool = False) -> bool:
    """Copy ``template-*.md`` from the shared repo into this repo root.

    The ``template-`` prefix is stripped on the way out
    (``template-AGENTS.md`` -> ``AGENTS.md``). Existing files are
    preserved unless ``force`` is set, so a repository's finished
    guidance is never clobbered by a re-run. The copied files are meant
    to be committed and are then completed by an agent (see README.md).
    """
    pairs = _instruction_templates()
    if not pairs:
        LOG.warning(
            "No '%s*.md' templates found in %s - skipping.",
            TEMPLATE_PREFIX,
            os.path.join(SHARED_REPO_DIR, TEMPLATE_DIR_NAME),
        )
        return True
    for source, destination in pairs:
        name = os.path.basename(destination)
        if os.path.lexists(destination) and not force:
            LOG.info(
                "'%s' already exists, skipping (use --force to overwrite).",
                name,
            )
            continue
        if os.path.islink(destination) or _is_reparse_point(destination):
            _remove_link(destination)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        LOG.info(
            "Copied '%s' (from '%s').",
            name,
            TEMPLATE_PREFIX + name,
        )
    return True


def _instruction_candidates() -> List[str]:
    """Paths to inspect for leftover bootstrap scaffolding.

    Includes the template destinations this script copies (when the shared
    repository is available), every ``AGENTS.md`` outside ``.agents-main``
    (root and nested), and a small fallback set so the check still works
    without the shared repository (e.g. in CI).
    """
    paths = set(dest for _, dest in _instruction_templates())
    for dirpath, dirnames, filenames in os.walk(CURRENT_ROOT):
        dirnames[:] = [
            name for name in dirnames
            if name not in (
                ".git", ".agents-main", "__pycache__", "node_modules",
                ".venv",
            )
        ]
        if "AGENTS.md" in filenames:
            paths.add(os.path.join(dirpath, "AGENTS.md"))
    for name in DEFAULT_INSTRUCTION_FILES:
        paths.add(os.path.join(CURRENT_ROOT, name))
    return sorted(path for path in paths if os.path.isfile(path))


def check_instructions() -> int:
    """Fail if instruction files still contain bootstrap scaffolding.

    Detects the ``GENERATION INSTRUCTIONS`` marker and any leftover
    ``[PLACEHOLDER]`` token in the repository's instruction files. Intended
    for CI or a pre-commit hook so an unfinished bootstrap — or a committed
    template — cannot land. Returns a process exit code.
    """
    paths = _instruction_candidates()
    if not paths:
        LOG.warning(
            "No instruction files found to check - run 'install' first."
        )
        return 1
    problems = 0
    for path in paths:
        name = os.path.relpath(path, CURRENT_ROOT)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError as error:
            LOG.error("Could not read %s: %s", name, error)
            problems += 1
            continue
        if GENERATION_MARKER in text:
            LOG.error(
                "%s still contains the generation instructions block - "
                "complete the file and delete the block.",
                name,
            )
            problems += 1
        tokens = sorted(set(PLACEHOLDER_RE.findall(text)))
        if tokens:
            LOG.error(
                "%s still contains placeholders: %s",
                name,
                ", ".join(tokens),
            )
            problems += 1
    if problems:
        LOG.error("Instruction check FAILED (%d problem(s)).", problems)
        return 1
    LOG.info(
        "Instruction check passed: no generation markers or placeholders "
        "in %d file(s).",
        len(paths),
    )
    return 0


def ensure_git_exclude() -> None:
    """Ensure '.agents-main' is ignored by git.

    No-op when .gitignore already ignores it; otherwise append it to
    '.git/info/exclude'.
    """
    if _run(["git", "check-ignore", "-q", "--", ".agents-main"]) == 0:
        LOG.debug("'.agents-main' already ignored via .gitignore.")
        return
    info_dir = os.path.join(CURRENT_ROOT, ".git", "info")
    os.makedirs(info_dir, exist_ok=True)
    exclude_path = os.path.join(info_dir, "exclude")
    lines = []
    if os.path.isfile(exclude_path):
        with open(exclude_path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    if "/.agents-main" in {line.strip() for line in lines}:
        return
    with open(exclude_path, "a", encoding="utf-8") as handle:
        if lines and lines[-1].strip():
            handle.write("\n")
        handle.write("/.agents-main\n")
    LOG.info("Added '/.agents-main' to .git/info/exclude")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def command_install(args: argparse.Namespace) -> int:
    """Handle the 'install' command."""
    if not ensure_shared_repo():
        return 1
    if not setup_agents_main(force=args.force):
        return 1
    if not copy_instruction_templates(force=args.force):
        return 1
    LOG.info(
        "Instruction templates copied. Complete AGENTS.md with your agent "
        "(see .agents-main/addon_repo_setup/README.md), then run "
        "'python agentic_setup.py check'."
    )
    if not setup_constitution(args.constitution):
        LOG.warning(
            "Constitution is not linked - skipping the specify "
            "installation step."
        )
        return 1
    if not _copy_addon_constitution(force=args.force):
        LOG.warning(
            "Addon constitution seed not copied - /speckit.constitution "
            "will not have a local extension constitution to amend. "
            "Fix the shared repository and re-run."
        )
    ensure_git_exclude()
    _ensure_gitignore_snippet()
    if args.specify:
        if not install_specify(args.integration, args.specify_args):
            return 1
        if not install_governance(force=args.force):
            return 1
        if not install_bug_extension(force=args.force):
            LOG.warning(
                "Continuing without the bug extension - the bug-fixing "
                "workflow commands will not be available until it is "
                "installed (specify extension add bug)."
            )
    LOG.info("Done.")
    return 0


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Set up agentic instructions and Spec Kit "
                    "integration for this repository."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    install = subparsers.add_parser(
        "install",
        help="Clone/link shared instructions and set up the "
             "constitution. Unknown extra arguments are passed "
             "verbatim to 'specify integration install' (only "
             "meaningful with --specify).",
    )
    install.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing '.agents-main' link/directory, "
             "refresh 'ayon-addon-constitution.md' from the shared "
             "seed (discarding local amendments), and reinstall the "
             "governance preset/extension.",
    )
    install.add_argument(
        "--specify",
        action="store_true",
        help="Also install the 'specify' CLI (via uv) and run "
             "'specify integration install <integration>' with any "
             "unknown arguments passed verbatim.",
    )
    install.add_argument(
        "--integration",
        default=DEFAULT_INTEGRATION,
        help="Agent harness for 'specify integration install' "
             "(default: {}, see 'specify integration list').".format(
                 DEFAULT_INTEGRATION
             ),
    )
    install.add_argument(
        "--constitution",
        default="ask",
        choices=["ask", "symlink", "copy", "skip"],
        help=(
            "Windows-only: what to do when a real constitution "
            "symlink cannot be created (Developer Mode disabled). "
            "'ask' prompts interactively; 'skip' also skips the "
            "specify installation. (default: ask)"
        ),
    )
    subparsers.add_parser(
        "check",
        help="Verify the copied instruction files contain no leftover "
             "generation markers or '[PLACEHOLDER]' tokens (for CI / "
             "pre-commit).",
    )
    args, extras = parser.parse_known_args(argv)
    # 'install -- --foo bar' keeps a literal '--' at the front.
    while extras and extras[0] == "--":
        extras = extras[1:]
    args.specify_args = extras
    if extras and not args.specify:
        parser.error(
            "unexpected arguments {!r} - they are only meaningful "
            "with --specify (passed to 'specify integration "
            "install')".format(extras)
        )
    return args


def main() -> int:
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )
    args = _parse_args()
    if args.command == "install":
        return command_install(args)
    if args.command == "check":
        return check_instructions()
    return 1


if __name__ == "__main__":
    sys.exit(main())
