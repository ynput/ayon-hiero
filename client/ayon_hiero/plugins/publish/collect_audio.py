import pyblish

from ayon_core.pipeline import PublishError
from ayon_hiero.api.otio import utils


class CollectAudio(pyblish.api.InstancePlugin):
    """Collect new audio."""

    order = pyblish.api.CollectorOrder - 0.48
    label = "Collect Audio"
    hosts = ["hiero"]
    families = ["audio"]

    def process(self, instance):
        """
        Args:
            instance (pyblish.Instance): The shot instance to update.
        """
        # Retrieve instance data from parent instance shot instance.
        parent_instance_id = instance.data["parent_instance_id"]

        try:
            edit_shared_data = instance.context.data["editorialSharedData"]
            shot_instance_data = edit_shared_data[parent_instance_id]

        # Ensure shot instance related to the audio instance exists.
        except KeyError:
            raise PublishError(
                f'Could not find shot instance for {instance.data["label"]}.'
                " Please ensure it is set and enabled."
            )

        instance.data.update(shot_instance_data)

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        # Clip index has to be taken form hero shot data
        # audio could be shorter but we need to get full length
        otio_clip, _ = utils.get_marker_from_clip_index(
            otio_timeline, shot_instance_data["shot_clip_index"]
        )
        if not otio_clip:
            raise PublishError(
                f"Could not retrieve otioClip for shot {instance}")

        instance.data["otioClip"] = otio_clip

        # solve reviewable options
        review_switch = instance.data["creator_attributes"].get("review")

        if review_switch is True:
            instance.data["reviewAudio"] = True
            instance.data.pop("review", None)

        clip_src = otio_clip.source_range
        clip_src_in = clip_src.start_time.to_frames()
        clip_src_out = clip_src_in + clip_src.duration.to_frames()
        instance.data.update({
            "clipInH": clip_src_in,
            "clipOutH": clip_src_out
        })
