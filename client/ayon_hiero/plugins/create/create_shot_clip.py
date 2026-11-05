import json

from ayon_hiero.api import (
    constants, plugin, lib, tags, clip_info_from_track_item
)

from ayon_core.pipeline import AVALON_CONTAINER_ID, AYON_CONTAINER_ID
from ayon_core.pipeline.create import (
    CreatorError,
    CreatedInstance,
    ParentFlags,
)

from ayon_editorial.create.mixins import (
    ClipCreatorMixin,
    ClipInstanceCreatorMixin,
    ShotInstanceCreatorMixin,
)
from ayon_editorial.shots.hierarchy import ShotHierarchySolver
from ayon_editorial.shots.instances import link_parent_instance
from ayon_editorial.shots.options import (
    CLIP_CREATOR_ATTRIBUTES,
    attribute_default,
)
from ayon_editorial.shots.vertical_sync import VerticalSync

import hiero


# Used as a key by the creators in order to
# retrieve the instances data into clip markers.
_CONTENT_ID = "hiero_sub_products"


def _get_video_track_names():
    sequence = lib.get_current_sequence()
    if sequence is None:
        return []
    return [track.name() for track in sequence.videoTracks()]


class _HieroInstanceCreator(plugin.HiddenHieroCreator):
    """Wrapper class for clip types products.
    """
    skip_discovery = True

    def _add_instance_to_context(self, instance):
        parent_id = instance.get("parent_instance_id")
        if parent_id is not None and ParentFlags is not None:
            instance.set_parent(
                parent_id,
                # Disable if a parent is disabled and delete if a parent
                #   is deleted
                ParentFlags.share_active | ParentFlags.parent_lifetime
            )
        super()._add_instance_to_context(instance)

    def create(self, instance_data):
        """Return a new CreateInstance for new shot from Hiero.

        Args:
            instance_data (dict): global data from original instance

        Return:
            CreatedInstance: The created instance object for the new shot.
        """
        instance_data["newHierarchyIntegration"] = True
        product_type = instance_data.get("productType")
        new_instance = CreatedInstance(
            product_base_type=self.product_base_type,
            product_type=product_type or self.product_base_type,
            product_name=instance_data["productName"],
            data=instance_data,
            creator=self,
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
        legacy_track_items = []
        for created_inst, _changes in update_list:
            track_item = created_inst.transient_data["track_item"]
            tag = lib.get_trackitem_ayon_tag(track_item)
            if tag is None:
                # Instance was collected from legacy (OpenPype) tag
                legacy_track_items.append(track_item)
                continue

            tag_data = tags.get_tag_data(tag)
            instances_data = tag_data.setdefault(_CONTENT_ID, {})
            instances_data[self.identifier] = created_inst.data_to_store()
            tags.update_tag(tag, {"metadata": tag_data})

        self._convert_legacy_tags(legacy_track_items)

    def remove_instances(self, instances):
        """Remove instance marker from track item.

        Args:
            instance(List[CreatedInstance]): Instance objects which should be
                removed.
        """
        legacy_track_items = []
        for instance in instances:
            track_item = instance.transient_data["track_item"]
            self._remove_instance_from_context(instance)

            tag = lib.get_trackitem_ayon_tag(track_item)
            if tag is None:
                # Instance was collected from legacy (OpenPype) tag
                legacy_track_items.append(track_item)
                continue

            tag_data = tags.get_tag_data(tag)
            instances_data = tag_data.get(_CONTENT_ID, {})
            instances_data.pop(self.identifier, None)

            # Remove markers if deleted all of the instances
            if not instances_data:
                track_item.removeTag(tag)

            # Push edited data in marker
            else:
                tags.update_tag(tag, {"metadata": tag_data})

        self._convert_legacy_tags(legacy_track_items)

    def _convert_legacy_tags(self, track_items):
        """Convert legacy (OpenPype) tag of clips to AYON tag.

        All instances collected from the legacy tag of a clip are stored
        into new AYON tag and the legacy tag is removed.

        Args:
            track_items (List[hiero.core.TrackItem]): Clips with instances
                collected from legacy tag.
        """
        if not track_items:
            return

        track_items_by_clip = {
            track_item.guid(): track_item
            for track_item in track_items
        }
        instances_by_clip = {clip: {} for clip in track_items_by_clip}
        for instance in self.create_context.instances:
            clip_instances = instances_by_clip.get(instance.get("clip_index"))
            if clip_instances is not None:
                clip_instances[instance.creator_identifier] = (
                    instance.data_to_store()
                )

        for clip, track_item in track_items_by_clip.items():
            clip_instances = instances_by_clip[clip]
            # All instances of the clip were removed
            if not clip_instances:
                lib.remove_legacy_tags(track_item)
                continue

            lib.imprint(
                track_item,
                data={
                    _CONTENT_ID: clip_instances,
                    "clip_index": clip,
                }
            )


class HieroShotInstanceCreator(
    ShotInstanceCreatorMixin, _HieroInstanceCreator
):
    """Shot product type creator class"""
    host_name = "hiero"
    identifier = "io.ayon.creators.hiero.shot"
    product_base_type = "shot"
    product_type = product_base_type
    label = "Editorial Shot"


class _HieroInstanceClipCreatorBase(
    ClipInstanceCreatorMixin, _HieroInstanceCreator
):
    """ Base clip product creator.
    """
    host_name = "hiero"
    skip_discovery = True

    def get_video_track_names(self):
        return _get_video_track_names()


class EditorialPlateInstanceCreator(_HieroInstanceClipCreatorBase):
    """Plate product type creator class"""
    identifier = "io.ayon.creators.hiero.plate"
    product_base_type = "plate"
    product_type = product_base_type
    label = "Editorial Plate"


class EditorialAudioInstanceCreator(_HieroInstanceClipCreatorBase):
    """Audio product type creator class"""
    identifier = "io.ayon.creators.hiero.audio"
    product_base_type = "audio"
    product_type = product_base_type
    label = "Editorial Audio"


class CreateShotClip(ClipCreatorMixin, plugin.HieroCreator):
    """Publishable clip"""

    host_name = "hiero"
    identifier = "io.ayon.creators.hiero.clip"
    label = "Create Publishable Clip"
    product_base_type = "editorial"
    product_type = product_base_type
    icon = "film"
    defaults = ["Main"]

    detailed_description = """
Publishing clips/plate, audio for new shots to project
or updating already created from Hiero. Publishing will create
OTIO file.
"""
    collect_selected_instance = False

    @property
    def creator_ids(self):
        return {
            "shot": HieroShotInstanceCreator.identifier,
            "plate": EditorialPlateInstanceCreator.identifier,
            "audio": EditorialAudioInstanceCreator.identifier,
        }

    def get_video_track_names(self):
        return _get_video_track_names()

    def apply_settings(self, project_settings):
        super().apply_settings(project_settings)
        self.collect_selected_instance = (
            project_settings["hiero"]["create"]["CollectShotClip"]
            ["collectSelectedInstance"]
        )

    def create(self, product_name, instance_data, pre_create_data):
        super().create(product_name, instance_data, pre_create_data)

        if len(self.selected) < 1:
            return

        self.log.debug(f"Selected: {self.selected}")

        audio_clips = []
        for audio_track in self.sequence.audioTracks():
            audio_clips.extend(audio_track.items())

        if not audio_clips and pre_create_data.get("export_audio"):
            raise CreatorError(
                "You must have audio in your active "
                "timeline in order to export audio."
            )

        pre_create_data = self.prepare_pre_create_data(pre_create_data)
        instance_data["task"] = None
        solver = ShotHierarchySolver(
            pre_create_data,
            self.sequence.name(),
            self.get_video_track_names(),
            VerticalSync(),
        )
        ids = self.creator_ids

        # vertical sync track first: its shot instances are the parents
        v_sync_track = pre_create_data.get("vSyncTrack") or ""
        selected = sorted(
            self.selected,
            key=lambda item: item.parent().name() not in v_sync_track,
        )

        # Instances previously generated for the clips
        prev_instances_by_clip = {}
        for instance in self.create_context.instances:
            track_item = instance.transient_data.get("track_item")
            if track_item is not None:
                prev_instances_by_clip.setdefault(
                    track_item.guid(), []).append(instance)

        instances = []
        all_shot_instances = {}
        for idx, track_item in enumerate(selected):
            clip = clip_info_from_track_item(track_item, self.sequence)
            solution = solver.solve(clip, idx)
            if solution is None:
                # clip of a reviewable source track, not the driving layer
                continue
            self.log.info(
                f"Processing track item data: {track_item} (index: {idx})")

            if solution.new_clip_name:
                track_item.setName(solution.new_clip_name)

            # Delete any existing instances previously generated for the clip.
            for prev_instance in prev_instances_by_clip.pop(clip.uid, []):
                creator = self.create_context.creators[
                    prev_instance.creator_identifier
                ]
                creator.remove_instances([prev_instance])

            solution_data = {**instance_data, **solution.data}
            sub_instances = self.make_clip_instances(
                clip, solution_data, pre_create_data)
            shot_instances = all_shot_instances.setdefault(
                solution.data["folderPath"], {})

            clip_instances = {}
            for creator_id, sub_data in sub_instances.items():
                if creator_id != ids["shot"]:
                    if ids["shot"] not in shot_instances:
                        raise CreatorError(
                            f"No shot instance for '{clip.name}': select"
                            " the hero track clip too."
                        )
                    link_parent_instance(sub_data, shot_instances[ids["shot"]])

                creator = self.create_context.creators[creator_id]
                instance = creator.create(sub_data)
                instance.transient_data["track_item"] = track_item
                self._add_instance_to_context(instance)
                stored = instance.data_to_store()
                shot_instances[creator_id] = stored
                clip_instances[creator_id] = stored

            lib.imprint(
                track_item,
                data={
                    _CONTENT_ID: clip_instances,
                    "clip_index": clip.uid,
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
        # publish effects backward compatibility (YN-0378)
        creator_attributes = data.get("creator_attributes", {})
        publish_effects = creator_attributes.get("publish_effects")
        if isinstance(publish_effects, bool):
            creator_attributes["publish_effects"] = (
                "publish_effects" if publish_effects else "ignore_effects"
            )

        creator = self.create_context.creators[creator_id]
        instance = creator.create(data)
        instance.transient_data["track_item"] = track_item
        self._add_instance_to_context(instance)
        instances.append(instance)
        return instance

    def _collect_legacy_instance(self, track_item):
        """Collect a legacy instance from previous creator if any.

        The legacy (OpenPype) tag is not touched during collection. It is
        converted to AYON tag when the collected instances are stored
        with 'update_instances'.

        Args:
            track_item (obj): The Hiero track_item to inspect.
        """
        tag = lib.get_trackitem_ayon_tag(
            track_item,
            tag_name=constants.LEGACY_OPENPYPE_TAG_NAME,
        )
        if not tag:
            return

        data = tag.metadata().dict()
        # Legacy tag of loaded container is not an instance
        if data.get("tag.id") in {AVALON_CONTAINER_ID, AYON_CONTAINER_ID}:
            return

        instance_data = {
            "clip_index": track_item.guid(),
            "task": None,
            "variant": track_item.parentTrack().name(),
            "extract_audio": False,
        }
        for spec in CLIP_CREATOR_ATTRIBUTES:
            if spec.kind == "label":
                continue
            key = spec.key
            if key == "plate_product_type":
                key = "productType"
            instance_data[key] = attribute_default(spec, self.presets)

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
            # OpenPype stored folder name as 'asset' or 'asset_name'
            #   and product name as 'subset'
            "tag.asset": ("folderName", str),
            "tag.asset_name": ("folderName", str),
            "tag.active": ("active", bool),
            "tag.subset": ("productName", str),
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
                    instance_data["folderName"]
                )
            except KeyError:
                instance_data["folderPath"] = "unknown"
                instance_data["active"] = False

        if "tag.subset" in data:
            instance_data["variant"] = data["tag.subset"].replace("plate", "")

        if "productName" not in instance_data:
            instance_data["productName"] = "{}{}".format(
                instance_data["productType"] or "plate",
                instance_data["variant"].capitalize()
            )

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
            "variant": "main",
            "productType": "shot",
            "productBaseType": "shot",
            "productName": "shotMain",
            "label": f"{sub_instance_data['folderPath']} shotMain",
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

        shot_creator_id = HieroShotInstanceCreator.identifier
        creator = self.create_context.creators[shot_creator_id]
        instance = creator.create(sub_instance_data)
        instance.transient_data["track_item"] = track_item
        self._add_instance_to_context(instance)
        parenting_data = instance

        # Create plate/audio instance
        if instance_data["extract_audio"]:
            sub_creators = (
                EditorialPlateInstanceCreator.identifier,
                EditorialAudioInstanceCreator.identifier
            )
        else:
            sub_creators = (
                EditorialPlateInstanceCreator.identifier,
            )

        for sub_creator_id in sub_creators:
            sub_instance_data = instance_data.copy()
            creator = self.create_context.creators[sub_creator_id]
            if sub_creator_id == EditorialAudioInstanceCreator.identifier:
                sub_instance_data.update({
                    "variant": "main",
                    "productType": "audio",
                    "productBaseType": "audio",
                    "productName": "audioMain",
                })

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

            instance = creator.create(sub_instance_data)
            instance.transient_data["track_item"] = track_item
            self._add_instance_to_context(instance)

    def collect_instances(self):
        """Collect all created instances from current timeline."""
        current_sequence = lib.get_current_sequence()
        if current_sequence:
            all_video_tracks = current_sequence.videoTracks()
        else:
            all_video_tracks = []

        restrict_to_selection = self.collect_selected_instance

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
            all_shot_ids = {
                inst.id
                for inst in instances
                if inst.data["productBaseType"] == "shot"
            }

            for inst in instances:
                if inst.id in all_shot_ids:
                    continue

                if (
                    inst.data["active"]
                    and inst.data["parent_instance_id"] not in all_shot_ids
                ):
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
