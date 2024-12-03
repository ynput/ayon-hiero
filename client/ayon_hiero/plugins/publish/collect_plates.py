import os
import pyblish

from ayon_core.pipeline import PublishError
from ayon_hiero.api.otio import utils


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
        instance.data["families"].append("clip")

        # Adjust instance data from parent otio timeline.
        otio_timeline = instance.context.data["otioTimeline"]
        otio_clip, _ = utils.get_marker_from_clip_index(
            otio_timeline, instance.data["clip_index"]
        )
        if not otio_clip:
            raise PublishError(
                f"Could not retrieve otioClip for shot {instance}")

        instance.data["otioClip"] = otio_clip

        # solve reviewable options
        review_switch = instance.data["creator_attributes"].get(
            "review")
        reviewable_source = instance.data["creator_attributes"].get(
            "reviewableSource")

        if review_switch is True:
            if reviewable_source == "clip_media":
                instance.data["families"].append("review")
                instance.data.pop("reviewTrack", None)

                # Retrieve source clip media from otio clip.
                # image sequence
                if hasattr(otio_clip.media_reference, "target_url_for_image_number"):
                    file_url = otio_clip.media_reference.target_url_for_image_number(0)
                    sequence_length = (
                        otio_clip.media_reference.end_frame()
                        - otio_clip.media_reference.start_frame
                    )
                    file_names = [
                        os.path.basename(
                            otio_clip.media_reference.target_url_for_image_number(frame)
                        )
                        for frame in range(0, sequence_length)
                    ]

                # movie
                else:
                    file_url = otio_clip.media_reference.target_url
                    file_names = os.path.basename(file_url)

                _, ext = os.path.splitext(file_url)

                repre = {
                    "name": ext[1:],
                    "ext": ext[1:],
                    "files": file_names,
                    "stagingDir": os.path.dirname(file_url),
                    "tags": ["review", "delete"]
                }
                instance.data["representations"].append(repre)

            else:
                instance.data["reviewTrack"] = reviewable_source

        # remove creator-specific review keys from instance data
        instance.data.pop("reviewableSource", None)
        instance.data.pop("review", None)

        # Retrieve instance data from parent instance shot instance.
        parent_instance_id = instance.data["parent_instance_id"]
        edit_shared_data = instance.context.data["editorialSharedData"]

        instance.data.update(
            edit_shared_data[parent_instance_id]
        )

        track_item = instance.data["item"]
        clip_colorspace = track_item.sourceMediaColourTransform()

        # add colorspace data to versionData
        version_data = instance.data.setdefault("versionData", {})
        version_data["colorSpace"] = clip_colorspace

        # add colorspace data to instance
        instance.data["colorspace"] = clip_colorspace
