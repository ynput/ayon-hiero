from ayon_server.settings import BaseSettingsModel, SettingsField


class CollectShotClipInstancesModels(BaseSettingsModel):
    collectSelectedInstance: bool = SettingsField(
        False,
        title="Collect only instances from selected clips.",
        description=(
            "This feature allows to restrict instance "
            "collection to selected timeline clips "
            "in the active sequence."
        )
    )


class CreatorPluginsSettings(BaseSettingsModel):
    CollectShotClip: CollectShotClipInstancesModels = SettingsField(
        default_factory=CollectShotClipInstancesModels,
        title="Collect Shot Clip instances"
    )


DEFAULT_CREATE_SETTINGS = {
    "create": {
        "CollectShotClip": {
            "collectSelectedInstance": False
        }
    }
}
