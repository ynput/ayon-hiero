from ayon_server.settings import BaseSettingsModel, SettingsField


def _product_name_enum():
    """Return a list of product name options."""
    return [
        {"value": "fromAttributes", "label": "From attributes"},
        {"value": "fromTemplate", "label": "From template"},
    ]

def _product_variant_enum():
    """Return a list of product variant options."""
    return [
        {"value": "<track_name>", "label": "Inherited from a track name"},
        {"value": "<token>", "label": "From token definition"},
        {"value": "main", "label": "Main"},
        {"value": "bg", "label": "Bg"},
        {"value": "fg", "label": "Fg"},
        {"value": "animatic", "label": "Animatic"},
    ]

def _product_type_enum():
    """Return a list of product type options."""
    return [
        {"value": "plate", "label": "Plate"},
    ]

class CreateShotClipModels(BaseSettingsModel):
    hierarchy: str = SettingsField(
        "{folder1}/{sequence}",
        title="Shot parent hierarchy",
        section="Shot Hierarchy And Rename Settings"
    )
    clipRename: bool = SettingsField(
        True,
        title="Rename clips"
    )
    clipName: str = SettingsField(
        "{shot}",
        title="Clip name template"
    )
    countFrom: int = SettingsField(
        10,
        title="Count sequence from"
    )
    countSteps: int = SettingsField(
        10,
        title="Stepping number"
    )

    folder1Token: str = SettingsField(
        "shots",
        title="{folder1}",
        section="Hierarchy related token definitions"
    )
    folder2Token: str = SettingsField(
        "",
        title="{folder2}",
    )
    folder3Token: str = SettingsField(
        "",
        title="{folder3}",
    )
    episodeToken: str = SettingsField(
        "ep01",
        title="{episode}"
    )
    sequenceToken: str = SettingsField(
        "sq01",
        title="{sequence}"
    )
    trackToken: str = SettingsField(
        "{_track_}",
        title="{track}"
    )
    shotToken: str = SettingsField(
        "sh###",
        title="{shot}"
    )
    productVariantToken: str = SettingsField(
        "Main",
        title="{productVariant}"
    )
    productNameToken: str = SettingsField(
        "{productType}{productVariant}",
        title="{productName}"
    )

    vSyncOn: bool = SettingsField(
        False,
        title="Enable Vertical Sync",
        section="Vertical Synchronization Of Attributes"
    )
    productVariant: str = SettingsField(
        "<track_name>",
        title="Product Variant",
        enum_resolver=_product_variant_enum,
        section="Publish Settings"
    )
    productType: str = SettingsField(
        "plate",
        title="Product Type",
        enum_resolver=_product_type_enum,
    )
    productName: str = SettingsField(
        "fromAttributes",
        title="Product Name",
        enum_resolver=_product_name_enum,
    )
    exportAudio: bool = SettingsField(
        False,
        title="Include audio product"
    )
    sourceResolution: bool = SettingsField(
        False,
        title="Source resolution"
    )
    workfileFrameStart: int = SettingsField(
        1001,
        title="Workfiles Start Frame",
        section="Shot Attributes"
    )
    handleStart: int = SettingsField(
        10,
        title="Handle start (head)"
    )
    handleEnd: int = SettingsField(
        10,
        title="Handle end (tail)"
    )


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
    CreateShotClip: CreateShotClipModels = SettingsField(
        default_factory=CreateShotClipModels,
        title="Create Shot Clip"
    )

    CollectShotClip: CollectShotClipInstancesModels = SettingsField(
        default_factory=CollectShotClipInstancesModels,
        title="Collect Shot Clip instances"
    )


DEFAULT_CREATE_SETTINGS = {
    "create": {
        "CreateShotClip": {
            "hierarchy": "{folder1}/{sequence}",
            "clipRename": True,
            "clipName": "{shot}",
            "countFrom": 10,
            "countSteps": 10,
            "folder1Token": "shots",
            "folder2Token": "",
            "folder3Token": "",
            "episodeToken": "ep01",
            "sequenceToken": "sq01",
            "trackToken": "{_track_}",
            "shotToken": "sh###",
            "productVariantToken": "Main",
            "productNameToken": "{productType}{productVariant}",
            "vSyncOn": False,
            "productVariant": "<track_name>",
            "productType": "plate",
            "productName": "fromAttributes",
            "sourceResolution": False,
            "exportAudio": False,
            "workfileFrameStart": 1001,
            "handleStart": 10,
            "handleEnd": 10
        }
    }
}
