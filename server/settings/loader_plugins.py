from ayon_server.settings import BaseSettingsModel, SettingsField


class LoadClipModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        True,
        title="Enabled"
    )
    product_base_types: list[str] = SettingsField(
        default_factory=list,
        title="Product base types"
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
        "product_base_types": [
            "render2d",
            "source",
            "plate",
            "render",
            "review"
        ],
        "clip_name_template": "{folder[name]}_{product[name]}_{representation}"
    }
}
