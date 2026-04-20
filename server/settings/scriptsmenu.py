from ayon_server.settings import BaseSettingsModel, SettingsField


def item_type_enum_resolver():
    return [
        {"value": "action", "label": "Action"},
        {"value": "menu", "label": "Menu"},
        {"value": "separator", "label": "Separator"},
    ]


def menu_item_type_enum_resolver():
    return [
        {"value": "action", "label": "Action"},
        {"value": "separator", "label": "Separator"},
    ]


def source_type_enum_resolver():
    return [
        {"value": "python", "label": "Python"},
        {"value": "file", "label": "Python file (set filepath as command)"},
    ]


class ScriptsActionModel(BaseSettingsModel):
    """Action Definition"""
    title: str = SettingsField("", title="Title")
    tooltip: str = SettingsField("", title="Tooltip")
    source_type: str = SettingsField(
        "file",
        title="Source Type",
        enum_resolver=source_type_enum_resolver,
        conditional_enum=True,
    )
    python: str = SettingsField(
        "",
        title="Python",
        widget="textarea",
        syntax="python",
    )
    file: str = SettingsField("", title="Filepath")


def _menu_item_definition(*args, **kwargs):
    return MenuItemDefinition(*args, **kwargs)


class MenuItemDefinition(BaseSettingsModel):
    """Item Definition"""
    _isGroup = True

    item_type: str = SettingsField(
        "action",
        title="Type",
        enum_resolver=menu_item_type_enum_resolver,
        conditional_enum=True,
    )
    action: ScriptsActionModel = ScriptsActionModel(
        default_factory=ScriptsActionModel,
    )


class CustomMenuItemDefinition(BaseSettingsModel):
    """Item Definition"""
    _isGroup = True

    item_type: str = SettingsField(
        "action",
        title="Type",
        enum_resolver=item_type_enum_resolver,
        conditional_enum=True,
    )
    action: ScriptsActionModel = ScriptsActionModel(
        default_factory=ScriptsActionModel,
    )
    menu: list[MenuItemDefinition] = SettingsField(
        default_factory=list,
    )



class ScriptsmenuSettings(BaseSettingsModel):
    """Nuke script menu project settings."""
    _isGroup = True

    """# TODO: enhance settings with host api:
    - in api rename key `name` to `menu_name`
    """
    name: str = SettingsField(title="Menu name")
    definition: list[CustomMenuItemDefinition] = SettingsField(
        default_factory=list,
        title="Definition",
        description="Scriptmenu Items Definition"
    )


DEFAULT_SCRIPTSMENU_SETTINGS = {
    "name": "Custom Tools",
    "definition": [
        {
            "item_type": "action",
            "action": {
                "title": "AYON Hiero Docs",
                "source_type": "python",
                "tooltip": "Open the AYON Hiero user doc page",
                "python": "import webbrowser\n\nwebbrowser.open(url='https://ayon.ynput.io/docs/addon_hiero_artist')",
                "file": "",
            }
        }
    ]
}
