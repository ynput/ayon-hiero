import pyblish


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
        edit_shared_data = instance.context.data["editorialSharedData"]
        instance.data.update(
            edit_shared_data[parent_instance_id]
        )

        if instance.data.get("reviewTrack") is not None:
            instance.data["reviewAudio"] = True
            instance.data.pop("reviewTrack")

        clip_src = instance.data["otioClip"].source_range
        clip_src_in = clip_src.start_time.to_frames()
        clip_src_out = clip_src_in + clip_src.duration.to_frames()
        instance.data.update({
            "clipInH": clip_src_in,
            "clipOutH": clip_src_out
        })
