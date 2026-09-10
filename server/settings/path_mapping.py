from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    MultiplatformPathModel
)


class PlatformPathMappingModel(BaseSettingsModel):
    _layout = "expanded"
    path: MultiplatformPathModel = SettingsField(
        default_factory=MultiplatformPathModel,
        title="Platform paths"
    )


class PathMappingSettings(BaseSettingsModel):
    remap_anatomy_root: bool = SettingsField(
        default=False,
        title="Remap Anatomy Root By Default"
    )
    platform_paths: list[PlatformPathMappingModel] = SettingsField(
        default_factory=list,
        title="Platform paths"
    )


DEFAULT_PATH_MAPPING_SETTINGS = {
    "remap_anatomy_root": False,
    "platform_paths": []
}
