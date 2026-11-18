from pydantic import validator
from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    ensure_unique_names,
    normalize_name,
    task_types_enum,
)


def _product_resources_product_base_types_enum():
    return [
        {"value": "plate", "label": "Plate"},
    ]


def _render_file_types_enum():
    return [
        {"value": "exr", "label": "OpenEXR"},
        {"value": "dpx", "label": "DPX"},
        {"value": "tiff", "label": "TIFF"},
        {"value": "png", "label": "PNG"},
        {"value": "jpeg", "label": "JPEG"},
        {"value": "mov", "label": "QuickTime (mov)"},
    ]


def _render_submissions_enum():
    return [
        {"value": "Single Render Process", "label": "Single Render Process"},
        {"value": "Frame Server", "label": "Frame Server"},
    ]


class CollectClipEffectsDefModel(BaseSettingsModel):
    _layout = "expanded"
    name: str = SettingsField("", title="Name")
    effect_classes: list[str] = SettingsField(
        default_factory=list, title="Effect Classes"
    )

    @validator("name")
    def validate_name(cls, value):
        """Ensure name does not contain weird characters"""
        return normalize_name(value)


class CollectClipEffectsTracksModel(BaseSettingsModel):
    _layout = "expanded"
    name: str = SettingsField("", title="Name")
    track_names: list[str] = SettingsField("", title="Track Names")


class CollectClipEffectsModel(BaseSettingsModel):
    effect_categories: list[CollectClipEffectsDefModel] = SettingsField(
        default_factory=list, title="Effect Categories"
    )

    effect_tracks: list[CollectClipEffectsTracksModel] = SettingsField(
        default_factory=list, title="Effect Tracks"
    )

    @validator("effect_categories")
    def validate_unique_outputs(cls, value):
        ensure_unique_names(value)
        return value


class CodecPropertyModel(BaseSettingsModel):
    _layout = "compact"
    name: str = SettingsField("", title="Key")
    value: str = SettingsField("", title="Value")


class PlateOutputModel(BaseSettingsModel):
    _layout = "expanded"
    repre_name: str = SettingsField(
        "",
        title="Representation name",
        description=(
            "Name of the representation. Empty uses the file extension."
        ),
        section="Representation",
    )
    tags: list[str] = SettingsField(
        default_factory=list,
        title="Tags",
        description="Representation tags, e.g. 'review'.",
    )
    custom_tags: list[str] = SettingsField(
        default_factory=list,
        title="Custom tags",
        description="For additional filtering in Extract Review.",
    )
    file_type: str = SettingsField(
        "exr",
        title="File type",
        enum_resolver=_render_file_types_enum,
        section="Render",
    )
    codec_properties: list[CodecPropertyModel] = SettingsField(
        default_factory=list,
        title="Codec settings",
        description=(
            "Hiero codec settings of the file type, as in Hiero's export "
            "dialog, e.g. 'datatype' = '16 bit half', 'compression' = "
            "'DWAA' for OpenEXR."
        ),
    )
    colorspace: str = SettingsField(
        "",
        title="Output colorspace",
        description=(
            "Colorspace the files are written in. Empty uses the Hiero "
            "project's default for the file type."
        ),
    )
    with_handles: bool = SettingsField(
        True,
        title="With handles",
    )
    include_effects: bool = SettingsField(
        False,
        title="Bake soft effects",
        description=(
            "Render the clip's soft effects into the files. Retimes are "
            "never baked."
        ),
    )


class ProductResourcesProfileModel(BaseSettingsModel):
    name: str = SettingsField(
        "",
        title="Profile name",
        description=(
            "Name of the profile. Empty gets a name by the product base "
            "type on save."
        ),
    )
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
        enum_resolver=task_types_enum,
        section="Profile Filtering",
    )
    task_names: list[str] = SettingsField(
        default_factory=list,
        title="Task names",
    )
    product_base_type: str = SettingsField(
        "plate",
        title="Product base type",
        enum_resolver=_product_resources_product_base_types_enum,
        conditional_enum=True,
    )
    keep_original_representation: bool = SettingsField(
        False,
        title="Publish clip's original media",
        description=(
            "Publish the clip's original media next to the rendered "
            "outputs. Without a matching profile nothing is rendered and "
            "the original media is always published."
        ),
    )
    plate: list[PlateOutputModel] = SettingsField(
        default_factory=list,
        title="Output definitions",
        description="One representation is rendered for each output.",
    )

    @validator("plate")
    def validate_unique_outputs(cls, value):
        names = set()
        for output in value:
            name = output.repre_name or output.file_type
            if name in names:
                raise ValueError(f"Duplicate representation name: {name}")
            names.add(name)
        return value


class ExtractProductResourcesModel(BaseSettingsModel):
    """Render additional representations of clip products.

    Profiles match the publishing task and the product base type. Without
    a matching profile the clip's original media is published.
    """

    render_submission: str = SettingsField(
        "Single Render Process",
        title="Render with",
        enum_resolver=_render_submissions_enum,
        description=(
            "Hiero render submission. The Frame Server renders image "
            "sequences in parallel; movies always use a single render "
            "process."
        ),
    )
    profiles: list[ProductResourcesProfileModel] = SettingsField(
        default_factory=list,
        title="Profiles",
    )

    @validator("profiles")
    def validate_profile_names(cls, value):
        # Name unnamed profiles by product base type, e.g. 'Plate #2'
        labels = {"plate": "Plate"}
        used_names = {profile.name for profile in value if profile.name}
        for profile in value:
            label = labels.get(profile.product_base_type)
            if profile.name or label is None:
                continue
            index = 1
            while f"{label} #{index}" in used_names:
                index += 1
            profile.name = f"{label} #{index}"
            used_names.add(profile.name)

        ensure_unique_names(value)
        return value


class PublishPluginsModel(BaseSettingsModel):
    CollectClipEffects: CollectClipEffectsModel = SettingsField(
        default_factory=CollectClipEffectsModel,
        title="Collect Clip Effects"
    )
    ExtractProductResources: ExtractProductResourcesModel = SettingsField(
        default_factory=ExtractProductResourcesModel,
        title="Extract Product Resources",
    )


DEFAULT_PUBLISH_PLUGIN_SETTINGS = {
    "CollectClipEffectsModel": {
        "effect_categories": [],
        "effect_tracks": []
    },
    "ExtractProductResources": {
        "render_submission": "Single Render Process",
        "profiles": [],
    },
}
