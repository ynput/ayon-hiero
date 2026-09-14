import pyblish.api

from ayon_core.pipeline.publish import (
    ValidateContentsOrder,
    PublishValidationError,
    RepairAction,
)
from ayon_hiero.api import lib, tags


class ValidateCollectedTrackItem(
    pyblish.api.InstancePlugin
):
    """Validate the collected timeline clip."""

    order = ValidateContentsOrder
    hosts = ["hiero"]
    families = ["shot", "audio", "plate", "take"]
    label = "Validate Collected Timeline Clip"
    actions = [RepairAction]

    def process(self, instance):
        if instance.data["trackItem"] is None:
            raise PublishValidationError(
                "Could not find track item associated to this instance. "
                "This might be because the timeline clip was copied/pasted from another sequence. \n"
                "Use 'Repair' to relink the source clip to this instance."
            )

    @classmethod
    def is_associated_item(
        cls,
        instance,
        track_item,
    ) -> bool:
        """
        """
        item_tag = lib.get_trackitem_ayon_tag(track_item)
        if not item_tag:
            return False

        tag_data = tags.get_tag_data(item_tag) or {}
        if "hiero_sub_products" not in tag_data:
            return False

        for value in tag_data.get("hiero_sub_products", {}).values():
            if (
                value.get("productBaseType") == instance.data["productBaseType"]
                and value.get("folderPath") == instance.data["folderPath"]
            ):
                track_item_index = track_item.guid()
                value["clip_index"] = track_item_index
                tag_data["clip_index"] = track_item_index
                instance.data["clip_index"] = track_item_index
                tags.update_tag(item_tag, {"metadata": tag_data})
                return True

        return False

    @classmethod
    def repair(cls, instance):
        """Attempt to relink the clip to the instance."""
        active_timeline = instance.context.data["activeTimeline"]
        for video_track in active_timeline.videoTracks():
            for item in video_track.items():
                if cls.is_associated_item(instance, item):
                    instance.data["clip_index"] = item.guid()
                    return

        raise PublishValidationError(
            "Could not find track item associated "
            "to this instance in the active timeline."
        )
