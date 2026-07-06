from ayon_core.lib import BoolDef


def hierarchical_settings():
    return {
        "update_to_new_track": {
            "type": "bool",
            "default": False,
            "label": "Update to new track",
            "tooltip": "When enabled, updated versions will be placed on a new track instead of replacing the existing clip."
        }
    }
