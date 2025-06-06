import copy
import json

from ayon_hiero.api import constants, plugin, lib, tags

from ayon_core.pipeline.create import CreatorError, CreatedInstance
from ayon_core.lib import BoolDef, EnumDef, TextDef, UILabelDef, NumberDef

import hiero


# Used as a key by the creators in order to
# retrieve the instances data into clip markers.
_CONTENT_ID = "hiero_sub_products"


# Shot attributes
CLIP_ATTR_DEFS = [
    EnumDef(
        "fps",
        items=[
            {"value": "from_selection", "label": "From selection"},
            {"value": 23.976, "label": "23.976"},
            {"value": 24, "label": "24"},
            {"value": 25, "label": "25"},
            {"value": 29.97, "label": "29.97"},
            {"value": 30, "label": "30"}
        ],
        label="FPS"
    ),
    NumberDef(
        "workfileFrameStart",
        default=1001,
        label="Workfile start frame"
    ),
    NumberDef(
        "handleStart",
        default=0,
        label="Handle start"
    ),
    NumberDef(
        "handleEnd",
        default=0,
        label="Handle end"
    ),
    NumberDef(
        "frameStart",
        default=0,
        label="Frame start",
        disabled=True,
    ),
    NumberDef(
        "frameEnd",
        default=0,
        label="Frame end",
        disabled=True,
    ),
    NumberDef(
        "clipIn",
        default=0,
        label="Clip in",
        disabled=True,
    ),
    NumberDef(
        "clipOut",
        default=0,
        label="Clip out",
        disabled=True,
    ),
    NumberDef(
        "clipDuration",
        default=0,
        label="Clip duration",
        disabled=True,
    ),
    NumberDef(
        "sourceIn",
        default=0,
        label="Media source in",
        disabled=True,
    ),
    NumberDef(
        "sourceOut",
        default=0,
        label="Media source out",
        disabled=True,
    )
]


class _HieroInstanceCreator(plugin.HiddenHieroCreator):
    """Wrapper class for clip types products.
    """

    def create(self, instance_data, _):
        """Return a new CreateInstance for new shot from Hiero.

        Args:
            instance_data (dict): global data from original instance

        Return:
            CreatedInstance: The created instance object for the new shot.
        """
        instance_data.update({
            "newHierarchyIntegration": True,
        })

        new_instance = CreatedInstance(
            self.product_type, instance_data["productName"], instance_data, self
        )
        self._add_instance_to_context(new_instance)
        new_instance.transient_data["has_promised_context"] = True
        return new_instance

    def update_instances(self, update_list):
        """Store changes of existing instances so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and it's changes.
        """
        for created_inst, _changes in update_list:
            track_item = created_inst.transient_data["track_item"]
            tag = lib.get_trackitem_ayon_tag(track_item)
            tag_data = tags.get_tag_data(tag)

            try:
                instances_data = tag_data[_CONTENT_ID]

            # Backwards compatible (Deprecated since 24/09/05)
            except KeyError:
                tag_data[_CONTENT_ID] = {}
                instances_data = tag_data[_CONTENT_ID]

            instances_data[self.identifier] = created_inst.data_to_store()
            tags.update_tag(tag, {"metadata": tag_data})

    def remove_instances(self, instances):
        """Remove instance marker from track item.

        Args:
            instance(List[CreatedInstance]): Instance objects which should be
                removed.
        """
        for instance in instances:
            track_item = instance.transient_data["track_item"]
            tag = lib.get_trackitem_ayon_tag(track_item)
            tag_data = tags.get_tag_data(tag)
            instances_data = tag_data.get(_CONTENT_ID, {})
            instances_data.pop(self.identifier, None)
            self._remove_instance_from_context(instance)

            # Remove markers if deleted all of the instances
            if not instances_data:
                track_item.removeTag(tag)

            # Push edited data in marker
            else:
                tags.update_tag(tag, {"metadata": tag_data})


class HieroShotInstanceCreator(_HieroInstanceCreator):
    """Shot product type creator class"""
    identifier = "io.ayon.creators.hiero.shot"
    product_type = "shot"
    label = "Editorial Shot"

    def get_instance_attr_defs(self):
        instance_attributes = CLIP_ATTR_DEFS
        instance_attributes.append(
            BoolDef(
                "useSourceResolution",
                label="Set shot resolution from plate",
                tooltip="Is resolution taken from timeline or source?",
                default=False,
            )
        )
        return instance_attributes


class _HieroInstanceClipCreatorBase(_HieroInstanceCreator):
    """ Base clip product creator.
    """

    def register_callbacks(self):
        self.create_context.add_value_changed_callback(self._on_value_change)

    def _on_value_change(self, event):
        if self.product_type != "plate":
            return

        for item in event["changes"]:
            instance = item["instance"]
            if (
                instance is None
                or instance.creator_identifier != self.identifier
            ):
                continue

            changes = item["changes"].get("creator_attributes", {})

            attr_defs = instance.creator_attributes.attr_defs

            if "review" not in changes:
                continue

            review_value = changes["review"]
            reviewable_source = next(
                attr_def
                for attr_def in attr_defs
                if attr_def.key == "reviewableSource"
            )
            reviewable_source.disabled = not review_value

            instance.set_create_attr_defs(attr_defs)

    def get_attr_defs_for_instance(self, instance):

        current_sequence = lib.get_current_sequence()
        if current_sequence is not None:
            gui_tracks = [
                {"value": tr.name(), "label": f"Track: {tr.name()}"}
                for tr in current_sequence.videoTracks()
            ]
        else:
            gui_tracks = []

        instance_attributes = [
            TextDef(
                "parentInstance",
                label="Linked to",
                disabled=True,
            )
        ]

        if self.product_type in ("audio", "plate"):
            instance_attributes.append(
                BoolDef(
                    "review",
                    label="Review",
                    tooltip="Switch to reviewable instance",
                    default=False,
                )
            )

        if self.product_type == "plate":
            # Review track visibility
            current_review = instance.creator_attributes.get("review", False)

            instance_attributes.extend(
                [
                    EnumDef(
                        "reviewableSource",
                        label="Reviewable Source",
                        tooltip=("Selecting source for reviewable files."),
                        items=(
                            [
                                {
                                    "value": "clip_media",
                                    "label": "[ Clip's media ]",
                                },
                            ]
                            + gui_tracks
                        ),
                        disabled=not current_review,
                    ),
                    BoolDef(
                        "publish_effects",
                        label="Publish clip effects",
                        tooltip="Discover and publish clip effects",
                        default=True,
                    ),
                ]
            )
        return instance_attributes


class EditorialPlateInstanceCreator(_HieroInstanceClipCreatorBase):
    """Plate product type creator class"""
    identifier = "io.ayon.creators.hiero.plate"
    product_type = "plate"
    label = "Editorial Plate"


class EditorialAudioInstanceCreator(_HieroInstanceClipCreatorBase):
    """Audio product type creator class"""
    identifier = "io.ayon.creators.hiero.audio"
    product_type = "audio"
    label = "Editorial Audio"


class CreateShotClip(plugin.HieroCreator):
    """Publishable clip"""

    identifier = "io.ayon.creators.hiero.clip"
    label = "Create Publishable Clip"
    product_type = "editorial"
    icon = "film"
    defaults = ["Main"]

    detailed_description = """
Publishing clips/plate, audio for new shots to project
or updating already created from Hiero. Publishing will create
OTIO file.
"""
    create_allow_thumbnail = False

    def get_pre_create_attr_defs(self):

        def header_label(text):
            return f"<br><b>{text}</b>"

        tokens_help = """\nUsable tokens:
    {_clip_}: name of used clip
    {_track_}: name of parent track layer
    {_sequence_}: name of parent sequence (timeline)"""

        current_sequence = lib.get_current_sequence()
        if current_sequence is not None:
            gui_tracks = [
                {"value": tr.name(), "label": f"Track: {tr.name()}"}
                for tr in current_sequence.videoTracks()
            ]
        else:
            gui_tracks = []

        # Project settings might be applied to this creator via
        # the inherited `Creator.apply_settings`
        presets = self.presets

        return [

            BoolDef("use_selection",
                    label="Use only selected clip(s).",
                    tooltip=(
                        "When enabled it restricts create process "
                        "to selected clips."
                    ),
                    default=True),

            # renameHierarchy
            UILabelDef(
                label=header_label("Shot Hierarchy And Rename Settings")
            ),
            TextDef(
                "hierarchy",
                label="Shot Parent Hierarchy",
                tooltip="Parents folder for shot root folder, "
                        "Template filled with *Hierarchy Data* section",
                default=presets.get("hierarchy", "{folder}/{sequence}"),
            ),
            BoolDef(
                "clipRename",
                label="Rename clips",
                tooltip="Renaming selected clips on fly",
                default=presets.get("clipRename", False),
            ),
            TextDef(
                "clipName",
                label="Clip Name Template",
                tooltip="template for creating shot names, used for "
                        "renaming (use rename: on)",
                default=presets.get("clipName", "{sequence}{shot}"),
            ),
            NumberDef(
                "countFrom",
                label="Count sequence from",
                tooltip="Set where the sequence number starts from",
                default=presets.get("countFrom", 10),
            ),
            NumberDef(
                "countSteps",
                label="Stepping number",
                tooltip="What number is adding every new step",
                default=presets.get("countSteps", 10),
            ),

            # hierarchyData
            UILabelDef(
                label=header_label("Shot Template Keywords")
            ),
            TextDef(
                "folder",
                label="{folder}",
                tooltip="Name of folder used for root of generated shots.\n"
                        f"{tokens_help}",
                default=presets.get("folder", "shots"),
            ),
            TextDef(
                "episode",
                label="{episode}",
                tooltip=f"Name of episode.\n{tokens_help}",
                default=presets.get("episode", "ep01"),
            ),
            TextDef(
                "sequence",
                label="{sequence}",
                tooltip=f"Name of sequence of shots.\n{tokens_help}",
                default=presets.get("sequence", "sq01"),
            ),
            TextDef(
                "track",
                label="{track}",
                tooltip=f"Name of timeline track.\n{tokens_help}",
                default=presets.get("track", "{_track_}"),
            ),
            TextDef(
                "shot",
                label="{shot}",
                tooltip="Name of shot. '#' is converted to padded number."
                        f"\n{tokens_help}",
                default=presets.get("shot", "sh###"),
            ),

            # verticalSync
            UILabelDef(
                label=header_label("Vertical Synchronization Of Attributes")
            ),
            BoolDef(
                "vSyncOn",
                label="Enable Vertical Sync",
                tooltip="Switch on if you want clips above "
                        "each other to share its attributes",
                default=presets.get("vSyncOn", True),
            ),
            EnumDef(
                "vSyncTrack",
                label="Hero track",
                tooltip="Select driving track name which should "
                        "be mastering all others",
                items=(
                    gui_tracks or [
                        {"value": None, "label": "< nothing to select> "}
                        ]
                ),
            ),
            # publishSettings
            UILabelDef(
                label=header_label("Publish Settings")
            ),
            EnumDef(
                "clipVariant",
                label="Product Variant",
                tooltip="Chose variant which will be then used for "
                        "product name, if <track_name> "
                        "is selected, name of track layer will be used",
                items=['<track_name>', 'main', 'bg', 'fg', 'bg', 'animatic'],
            ),
            EnumDef(
                "productType",
                label="Product Type",
                tooltip="How the product will be used",
                items=['plate', 'take'],
            ),
            EnumDef(
                "reviewableSource",
                label="Reviewable Source",
                tooltip="Generate preview videos on fly, if "
                "'< none >' is defined nothing will be generated.",
                items=[
                    {"value": None, "label": "< none >"},
                    {"value": "clip_media", "label": "[ Clip's media ]"},
                ]
                + gui_tracks,
            ),
            BoolDef(
                "export_audio",
                label="Include audio",
                tooltip="Process subsets with corresponding audio",
                default=False,
            ),
            BoolDef(
                "sourceResolution",
                label="Source resolution",
                tooltip="Is resolution taken from timeline or source?",
                default=False,
            ),
            # shotAttr
            UILabelDef(
                label=header_label("Shot Attributes"),
            ),
            NumberDef(
                "workfileFrameStart",
                label="Workfiles Start Frame",
                tooltip="Set workfile starting frame number",
                default=presets.get("workfileFrameStart", 1001),
            ),
            NumberDef(
                "handleStart",
                label="Handle start (head)",
                tooltip="Handle at start of clip",
                default=presets.get("handleStart", 0),
            ),
            NumberDef(
                "handleEnd",
                label="Handle end (tail)",
                tooltip="Handle at end of clip",
                default=presets.get("handleEnd", 0),
            ),
        ]

    def create(self, subset_name, instance_data, pre_create_data):
        super(CreateShotClip, self).create(subset_name,
                                           instance_data,
                                           pre_create_data)

        if len(self.selected) < 1:
            return

        self.log.info(self.selected)
        self.log.debug(f"Selected: {self.selected}")

        audio_clips = []
        for audio_track in self.sequence.audioTracks():
            audio_clips.extend(audio_track.items())

        if not audio_clips and pre_create_data.get("export_audio"):
            raise CreatorError(
                "You must have audio in your active "
                "timeline in order to export audio."
            )

        instance_data["task"] = None

        # sort selected trackItems by
        sorted_selected_track_items = list()
        unsorted_selected_track_items = list()
        v_sync_track = pre_create_data.get("vSyncTrack", "")
        for _ti in self.selected:
            if _ti.parent().name() in v_sync_track:
                sorted_selected_track_items.append(_ti)
            else:
                unsorted_selected_track_items.append(_ti)

        sorted_selected_track_items.extend(unsorted_selected_track_items)

        shot_creator_id = "io.ayon.creators.hiero.shot"
        audio_creator_id = "io.ayon.creators.hiero.audio"
        plate_creator_id = "io.ayon.creators.hiero.plate"

        # detect enabled creators for review, plate and audio
        all_creators = {
            shot_creator_id: True,
            plate_creator_id: True,
            audio_creator_id: True,
        }

        instances = []
        all_shot_instances = {}
        vertical_clip_match = {}
        vertical_clip_used = {}

        for idx, track_item in enumerate(sorted_selected_track_items):
            _instance_data = copy.deepcopy(instance_data)
            _instance_data["clip_index"] = track_item.guid()

            # convert track item to timeline media pool item
            publish_clip = plugin.PublishClip(
                track_item,
                vertical_clip_match,
                vertical_clip_used,
                pre_create_data=pre_create_data,
                rename_index=idx,
                data=_instance_data,
            )

            track_item = publish_clip.convert()
            if track_item is None:
                # Ignore input clips that do not convert into a track item
                # from `PublishClip.convert`
                continue

            self.log.info(
                "Processing track item data: {} (index: {})".format(
                    track_item, idx)
            )
            _instance_data.update(publish_clip.tag_data)

            # Delete any existing instances previously generated for the clip.
            prev_tag = lib.get_trackitem_ayon_tag(track_item)
            if prev_tag:
                prev_tag_data = tags.get_tag_data(prev_tag)
                for creator_id, inst_data in prev_tag_data[_CONTENT_ID].items():
                    creator = self.create_context.creators[creator_id]
                    prev_instances = [
                        inst for inst_id, inst
                        in self.create_context.instances_by_id.items()
                        if inst_id == inst_data["instance_id"]
                    ]
                    creator.remove_instances(prev_instances)

            # Create new product(s) instances.
            shot_folder_path = _instance_data["folderPath"]
            shot_instances = all_shot_instances.setdefault(
                shot_folder_path, {})

            # desable shot creator if heroTrack is not enabled
            all_creators[shot_creator_id] = _instance_data.get(
                "heroTrack", False)
            # desable audio creator if audio is not enabled
            all_creators[audio_creator_id] = (
                _instance_data.get("heroTrack", False) and
                pre_create_data.get("export_audio", False)
            )

            enabled_creators = tuple(
                cre for cre, enabled in all_creators.items() if enabled
            )
            clip_instances = {}
            for creator_id in enabled_creators:
                creator = self.create_context.creators[creator_id]
                sub_instance_data = copy.deepcopy(_instance_data)
                creator_attributes = sub_instance_data.setdefault(
                    "creator_attributes", {})
                shot_folder_path = sub_instance_data["folderPath"]

                # Shot creation
                if creator_id == shot_creator_id:
                    track_item_duration = track_item.duration()
                    workfileFrameStart = \
                        sub_instance_data["workfileFrameStart"]

                    sub_instance_data.update(
                        {
                            "variant": "main",
                            "productType": "shot",
                            "productName": "shotMain",
                            "label": (
                                f"{sub_instance_data['folderPath']} shotMain"),
                        }
                    )
                    creator_attributes.update(
                        {
                            "workfileFrameStart": sub_instance_data[
                                "workfileFrameStart"
                            ],
                            "handleStart": sub_instance_data["handleStart"],
                            "handleEnd": sub_instance_data["handleEnd"],
                            "frameStart": workfileFrameStart,
                            "frameEnd": (
                                workfileFrameStart + track_item_duration),
                            "clipIn": track_item.timelineIn(),
                            "clipOut": track_item.timelineOut(),
                            "clipDuration": track_item_duration,
                            "sourceIn": track_item.sourceIn(),
                            "sourceOut": track_item.sourceOut(),
                            "useSourceResolution": sub_instance_data["sourceResolution"],
                        }
                    )

                # Plate, Audio
                # insert parent instance data to allow
                # metadata recollection as publish time.
                elif creator_id == plate_creator_id:
                    parenting_data = shot_instances[shot_creator_id]
                    sub_instance_data.update({
                        "parent_instance_id": parenting_data["instance_id"],
                        "label": (
                            f"{sub_instance_data['folderPath']} "
                            f"{sub_instance_data['productName']}"
                        )
                    })
                    creator_attributes["parentInstance"] = parenting_data[
                        "label"]
                    if sub_instance_data.get("reviewableSource"):
                        creator_attributes.update({
                            "review": True,
                            "reviewableSource": sub_instance_data[
                                "reviewableSource"],
                        })

                elif creator_id == audio_creator_id:
                    sub_instance_data["variant"] = "main"
                    sub_instance_data["productType"] = "audio"
                    sub_instance_data["productName"] = "audioMain"

                    parenting_data = shot_instances[shot_creator_id]
                    sub_instance_data.update(
                        {
                            "parent_instance_id": parenting_data["instance_id"],
                            "label": (
                                f"{sub_instance_data['folderPath']} "
                                f"{sub_instance_data['productName']}"
                            )
                        }
                    )
                    creator_attributes["parentInstance"] = parenting_data[
                        "label"]

                    if sub_instance_data.get("reviewableSource"):
                        creator_attributes["review"] = True

                instance = creator.create(sub_instance_data, None)
                instance.transient_data["track_item"] = track_item
                self._add_instance_to_context(instance)
                instance_data_to_store = instance.data_to_store()
                shot_instances[creator_id] = instance_data_to_store
                clip_instances[creator_id] = instance_data_to_store

            lib.imprint(
                track_item,
                data={
                    _CONTENT_ID: clip_instances,
                    "clip_index": track_item.guid(),
                }
            )
            instances.append(instance)

        return instances

    def _create_and_add_instance(self, data, creator_id,
            track_item, instances):
        """
        Args:
            data (dict): The data to re-recreate the instance from.
            creator_id (str): The creator id to use.
            track_item (obj): The associated track item.
            instances (list): Result instance container.

        Returns:
            CreatedInstance: The newly created instance.
        """
        creator = self.create_context.creators[creator_id]
        instance = creator.create(data, None)
        instance.transient_data["track_item"] = track_item
        self._add_instance_to_context(instance)
        instances.append(instance)
        return instance

    def _collect_legacy_instance(self, track_item):
        """Collect a legacy instance from previous creator if any.#

        Args:
            track_item (obj): The Hiero track_item to inspect.
        """
        tag = lib.get_trackitem_ayon_tag(
            track_item,
            tag_name=constants.LEGACY_OPENPYPE_TAG_NAME,
        )
        if not tag:
            return

        data = tag.metadata()

        clip_instances = {}
        instance_data = {
            "clip_index": track_item.guid(),
            "task": None,
            "variant": track_item.parentTrack().name(),
            "extract_audio": False,
        }
        for create_attr in self.get_pre_create_attr_defs():
            if isinstance(create_attr.key, str):
                instance_data[create_attr.key] = create_attr.default

        required_key_mapping = {
            "tag.audio": ("extract_audio", bool),
            "tag.heroTrack": ("heroTrack", bool),
            "tag.handleStart": ("handleStart", int),
            "tag.handleEnd": ("handleEnd", int),
            "tag.folderPath": ("folderPath", str),
            "tag.reviewTrack": ("reviewableSource", str),
            "tag.variant": ("variant", str),
            "tag.workfileFrameStart": ("workfileFrameStart", int),
            "tag.sourceResolution": ("sourceResolution", bool),
            "tag.hierarchy": ("hierarchy", str),
            "tag.hierarchyData": ("hierarchyData", json),
            "tag.asset_name": ("folderName", str),
            "tag.asset": ("productName", str),
            "tag.active": ("active", bool),
            "tag.productName": ("productName", str),
            "tag.parents": ("parents", json),
        }

        for key, value in required_key_mapping.items():
            if key not in data:
                continue

            try:
                instance_key, type_cast = value
                if type_cast is bool:
                    instance_data[instance_key] = data[key] == "True"
                elif type_cast is json:
                    conformed_data = data[key].replace("'", "\"")
                    conformed_data = conformed_data.replace('u"', '"')
                    instance_data[instance_key] = json.loads(conformed_data)
                else:
                    instance_data[instance_key] = type_cast(data[key])

            except Exception as error:
                self.log.warning(
                    "Cannot retrieve instance from legacy "
                    f"tag data: {error}."
                )

        if "folderPath" not in instance_data:
            try:
                instance_data["folderPath"] = (
                    "/" + instance_data["hierarchy"] + "/" +
                    instance_data["productName"]
                )
            except KeyError:
                instance_data["folderPath"] = "unknown"
                instance_data["active"] = False

        if "tag.subset" in data:
            instance_data["variant"] = data["tag.subset"].replace("plate", "")

        for folder in instance_data.get("parents", []):
            if "entity_name" in folder:
                folder["folder_name"] = folder["entity_name"]
            if "entity_type" in folder:
                folder["folder_type"] = folder["entity_type"]

        # Create parent shot instance.
        sub_instance_data = instance_data.copy()
        track_item_duration = track_item.duration()
        workfileFrameStart = \
            sub_instance_data["workfileFrameStart"]
        sub_instance_data.update({
            "label": (
                f"{sub_instance_data['folderPath']} "
                f"{sub_instance_data['productName']}"),
            "variant": "main",
            "creator_attributes": {
                "workfileFrameStart": workfileFrameStart,
                "handleStart": sub_instance_data["handleStart"],
                "handleEnd": sub_instance_data["handleEnd"],
                "frameStart": workfileFrameStart,
                "frameEnd": (workfileFrameStart +
                    track_item_duration),
                "clipIn": track_item.timelineIn(),
                "clipOut": track_item.timelineOut(),
                "clipDuration": track_item_duration,
                "sourceIn": track_item.sourceIn(),
                "sourceOut": track_item.sourceOut(),
                "useSourceResolution": sub_instance_data.get("sourceResolution", False),
            }
        })

        shot_creator_id = "io.ayon.creators.hiero.shot"
        creator = self.create_context.creators[shot_creator_id]
        instance = creator.create(sub_instance_data, None)
        instance.transient_data["track_item"] = track_item
        self._add_instance_to_context(instance)
        clip_instances[shot_creator_id] = instance.data_to_store()
        parenting_data = instance

        # Create plate/audio instance
        if instance_data["extract_audio"]:
            sub_creators = (
                "io.ayon.creators.hiero.plate",
                "io.ayon.creators.hiero.audio"
            )
        else:
            sub_creators = ("io.ayon.creators.hiero.plate",)

        for sub_creator_id in sub_creators:
            sub_instance_data = instance_data.copy()
            creator = self.create_context.creators[sub_creator_id]
            sub_instance_data.update(
                {
                    "parent_instance_id": parenting_data["instance_id"],
                    "label": (
                        f"{sub_instance_data['folderPath']} "
                        f"{sub_instance_data['productName']}"
                    ),
                    "creator_attributes": {
                        "parentInstance": parenting_data["label"],
                        "reviewableSource": sub_instance_data[
                            "reviewableSource"],
                        "review": False,
                    }
                }
            )

            instance = creator.create(sub_instance_data, None)
            instance.transient_data["track_item"] = track_item
            self._add_instance_to_context(instance)
            clip_instances[sub_creator_id] = instance.data_to_store()

        # Adjust clip tag to match new publisher
        track_item.removeTag(tag)
        lib.imprint(
            track_item,
            data={
                _CONTENT_ID: clip_instances,
                "clip_index": track_item.guid(),
            }
        )

    def collect_instances(self):
        """Collect all created instances from current timeline."""
        current_sequence = lib.get_current_sequence()
        if current_sequence:
            all_video_tracks = current_sequence.videoTracks()
        else:
            all_video_tracks = []

        create_settings = self.project_settings["hiero"]["create"]
        collect_settings = create_settings.get("CollectShotClip", {})
        restrict_to_selection = collect_settings.get("collectSelectedInstance", False)
        current_selection = [
            item for item in lib.get_timeline_selection()
            if isinstance(item, hiero.core.TrackItem)  # get only clips
        ]

        self.log.debug(
            "Collect instances from timeline. "
            f"restrict_to_selection setting: {restrict_to_selection} "
            f"current_selection: {current_selection}"
        )

        instances = []
        for video_track in all_video_tracks:
            for track_item in video_track:

                # Should we restrict collection to selected item ?
                # This might be convenient for heavy timelines and
                # can be handled via creator settings.
                # When nothing is selected, collect everything.
                if (restrict_to_selection and current_selection
                    and track_item not in current_selection):
                    continue

                # attempt to get AYON tag data
                tag = lib.get_trackitem_ayon_tag(track_item)
                if not tag:
                    self._collect_legacy_instance(track_item)
                    continue

                tag_data = tags.get_tag_data(tag)
                for creator_id, data in tag_data.get(_CONTENT_ID, {}).items():
                    self._create_and_add_instance(
                        data, creator_id, track_item, instances)

        if restrict_to_selection:
            # Ensure that parent shot instance are enabled.
            # This can happen when vertical_align is enabled
            # but hero track is not part of the collected clips.
            all_shot_ids = [inst.id for inst in instances if inst.data["productType"] == "shot"]

            for inst in instances:
                if inst.id in all_shot_ids:
                    continue

                elif inst.data["active"] and inst.data["parent_instance_id"] not in all_shot_ids:
                    raise CreatorError(
                        "Incomplete selection: please select hero track"
                        f' for {inst.data["label"]} instance.'
                    )

        return instances

    def update_instances(self, update_list):
        """Never called, update is handled via _HieroInstanceCreator."""
        pass

    def remove_instances(self, instances):
        """Never called, update is handled via _HieroInstanceCreator."""
        pass
