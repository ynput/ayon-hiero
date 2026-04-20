from typing import Any
from semver import VersionInfo


def _convert_scripts_menu_0_5_13(
    version: VersionInfo,
    overrides: dict[str, Any]
) -> None:
    defs = overrides.get("scriptsmenu", {}).get("definition")
    if not isinstance(defs, list):
        return

    # Skip conversion of newer versions
    if (version.major, version.minor, version.patch) > (0, 5, 12):
        return

    first_action_checked = False
    new_defs = []
    for item in defs:
        item_type = item.get("type")
        if item_type is None:
            return

        if item_type.lower() == "separator":
            new_defs.append({
                "item_type": "separator",
            })
            continue

        if not first_action_checked:
            first_action_checked = True
            for key in (
                "sourcetype",
                "title",
                "command",
                "tooltip",
            ):
                if key not in item:
                    return

        source_type = item["sourcetype"]
        python_code = ""
        filepath = ""
        if source_type == "python":
            python_code = item["command"]
        else:
            source_type = "file"
            filepath = item["command"]

        new_defs.append({
            "item_type": "action",
            "action": {
                "title": item["title"],
                "tooltip": item["tooltip"],
                "source_type": source_type,
                "file": filepath,
                "python": python_code,
            }
        })

    overrides["scriptsmenu"]["definition"] = new_defs


def convert_settings_overrides(
    source_version: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    version = VersionInfo.parse(source_version)
    _convert_scripts_menu_0_5_13(version, overrides)
    return overrides
