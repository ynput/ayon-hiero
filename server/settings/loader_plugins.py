from ayon_server.settings import BaseSettingsModel, SettingsField


class LoadClipModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        True,
        title="Enabled"
    )
    clip_name_template: str = SettingsField(
        title="Clip name template"
    )


class LoaderPluginsModel(BaseSettingsModel):
    LoadClip: LoadClipModel = SettingsField(
        default_factory=LoadClipModel,
        title="Load Clip"
    )


DEFAULT_LOADER_PLUGINS_SETTINGS = {
    "LoadClip": {
        "enabled": True,
        "clip_name_template": "{folder[name]}_{product[name]}_{representation}"
    }
}
