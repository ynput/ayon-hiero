import pyblish

from ayon_core.pipeline import PublishError
from ayon_hiero.api.otio import utils
from ayon_editorial.otio.effects import get_retime_info
from ayon_editorial.shots.retime import RetimeOptions, handles_for_core


class CollectPlate(pyblish.api.InstancePlugin):
    """Collect new plates."""

    order = pyblish.api.CollectorOrder - 0.48
    label = "Collect Plate"
    hosts = ["hiero"]
    families = ["plate"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        instance.data["families"].extend([
            "clip",
            # Mark for 'CollectOTIORanges' in core
            "otio.clip.ranges",
            # Mark for 'CollectOTIOProductResources' in core
            "otio.clip.resources",
            # Mark for 'CollectOTIOReviewTrack' in core
            "otio.review.track",
        ])

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, _ = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise PublishError(
                f"Could not retrieve otioClip for shot {instance}")

        instance.data["otioClip"] = otio_clip

        # Adjust info from track_item on timeline
        active_timeline = instance.context.data["activeTimeline"]
        track_item = None
        for video_track in active_timeline.videoTracks():
            for item in video_track.items():
                if item.guid() == instance.data["clip_index"]:
                    track_item = item
                    break

        instance.data["trackItem"] = track_item

        # solve reviewable options
        review_switch = instance.data["creator_attributes"].get(
            "review")
        reviewable_source = instance.data["creator_attributes"].get(
            "reviewableSource")

        if review_switch is True:
            if reviewable_source == "clip_media":
                instance.data["families"].append("review")
                # Tell 'CollectOTIOReviewTrack' to use the current clip
                instance.data["otioReviewClips"] = [otio_clip]
                instance.data.pop("reviewTrack", None)
            else:
                instance.data["reviewTrack"] = reviewable_source

        # remove creator-specific review keys from instance data
        instance.data.pop("reviewableSource", None)
        instance.data.pop("review", None)

        # Retrieve instance data from parent instance shot instance.
        parent_instance_id = instance.data["parent_instance_id"]

        try:
            edit_shared_data = instance.context.data["editorialSharedData"]
            instance.data.update(
                edit_shared_data[parent_instance_id]
            )

        # Ensure shot instance related to the audio instance exists.
        except KeyError:
            raise PublishError(
                f'Could not find shot instance for {instance.data["label"]}.'
                " Please ensure it is set and enabled."
            )

        # Without retimed handles, hand ayon-core handles it scales back
        # to the configured ones (it scales them by the clip speed).
        retime_options = RetimeOptions.from_data(
            instance.data,
            defaults=RetimeOptions(retimed_framerange=False),
        )
        if not retime_options.retimed_handles:
            speed = get_retime_info(otio_clip).time_scalar
            handle_start, handle_end = handles_for_core(
                int(instance.data.get("handleStart", 0)),
                int(instance.data.get("handleEnd", 0)),
                speed,
                retime_options.retimed_handles,
            )
            instance.data.update({
                "handleStart": handle_start,
                "handleEnd": handle_end,
            })

        if track_item is not None:
            clip_colorspace = track_item.sourceMediaColourTransform()

            # add colorspace data to versionData
            version_data = instance.data.setdefault("versionData", {})
            version_data["colorSpace"] = clip_colorspace

            # add colorspace data to instance
            instance.data["colorspace"] = clip_colorspace
