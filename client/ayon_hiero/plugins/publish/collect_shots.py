import json
import pyblish

from ayon_core.pipeline import PublishError
from ayon_hiero.api import lib
from ayon_hiero.api.otio import utils

import hiero


class CollectShot(pyblish.api.InstancePlugin):
    """Collect new shots."""

    order = pyblish.api.CollectorOrder - 0.49
    label = "Collect Shots"
    hosts = ["hiero"]
    families = ["shot"]

    SHARED_KEYS = (
        "annotations",
        "folderPath",
        "fps",
        "handleStart",
        "handleEnd",
        "resolutionWidth",
        "resolutionHeight",
        "pixelAspect",
        "subtracks",
        "tags",
    )

    @classmethod
    def _inject_editorial_shared_data(cls, instance):
        """
        Args:
            instance (obj): The publishing instance.
        """
        context = instance.context
        instance_id = instance.data["instance_id"]

        # Inject folderPath and other creator_attributes to ensure
        # new shots/hierarchy are properly handled.
        creator_attributes = instance.data['creator_attributes']
        instance.data.update(creator_attributes)

        # Adjust handles:
        # Explain
        track_item = instance.data["trackItem"]
        instance.data.update({
            "handleStart": min(
                instance.data["handleStart"], int(track_item.handleInLength())),
            "handleEnd": min(
                instance.data["handleEnd"], int(track_item.handleOutLength())),
        })

        # Inject/Distribute instance shot data as editorialSharedData
        # to make it available for clip/plate/audio products
        # in sub-collectors.
        if not context.data.get("editorialSharedData"):
            context.data["editorialSharedData"] = {}

        edit_shared_data = context.data["editorialSharedData"].setdefault(
            instance_id, {}
        )
        edit_shared_data.update({
            key: value for key, value in instance.data.items()
            if key in cls.SHARED_KEYS
        })
        # also add `shot_clip_index` to shared data for audio instance
        edit_shared_data["shot_clip_index"] = instance.data["clip_index"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        instance.data["integrate"] = False  # no representation for shot

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, marker = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise PublishError(
                f"Could not retrieve otioClip for shot {instance}")

        # Compute fps from creator attribute.
        if instance.data['creator_attributes']["fps"] == "from_selection":
            instance.data['creator_attributes']["fps"] = instance.context.data["fps"]

        # Retrieve AyonData marker for associated clip.
        instance.data["otioClip"] = otio_clip
        creator_id = instance.data["creator_identifier"]

        marker_metadata = json.loads(marker.metadata["json_metadata"])
        inst_data = marker_metadata["hiero_sub_products"].get(creator_id, {})

        # Overwrite settings with clip metadata is "sourceResolution"
        overwrite_clip_metadata = inst_data.get("sourceResolution", False)
        active_timeline = instance.context.data["activeTimeline"]

        # Adjust info from track_item on timeline
        track_item = None
        for video_track in active_timeline.videoTracks():
            for item in video_track.items():
                if item.guid() == instance.data["clip_index"]:
                    track_item = item
                    break

        if not track_item:
            raise PublishError(
                'Could not retrieve item from '
                f'clip guid: {instance.data["clip_index"]}'
            )

        instance.data.update({
            "annotations": self.clip_annotations(track_item.source()),
            "trackItem": track_item,
            "subtracks": self.clip_subtrack(track_item),
            "tags": lib.get_track_item_tags(track_item),
        })

        # Retrieve clip from active_timeline
        if overwrite_clip_metadata:
            source_clip = track_item.source()
            item_format = source_clip.format()

        # Get resolution from active timeline
        else:
            item_format = active_timeline.format()

        instance.data.update(
            {
                "resolutionWidth": item_format.width(),
                "resolutionHeight": item_format.height(),
                "pixelAspect": item_format.pixelAspect()
            }
        )
        self._inject_editorial_shared_data(instance)

    @staticmethod
    def clip_annotations(clip):
        """
        Args:
            clip (hiero.core.TrackItem): The clip to inspect.

        Returns:
            list[hiero.core.Annotation]: Associated clips annotations.
        """
        annotations = []
        subTrackItems = lib.flatten(clip.subTrackItems())
        annotations += [item for item in subTrackItems if isinstance(
            item, hiero.core.Annotation)]
        return annotations

    @staticmethod
    def clip_subtrack(clip):
        """
        Args:
            clip (hiero.core.TrackItem): The clip to inspect.

        Returns:
            list[hiero.core.SubTrackItem]: Associated clips SubTrackItem.
        """
        subtracks = []
        subTrackItems = lib.flatten(clip.parent().subTrackItems())
        for item in subTrackItems:
            if "TimeWarp" in item.name():
                continue
            # avoid all annotation
            if isinstance(item, hiero.core.Annotation):
                continue
            # avoid all disabled
            if not item.isEnabled():
                continue
            subtracks.append(item)
        return subtracks
