import pyblish


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

        # solve reviewable options
        review_switch = instance.data["creator_attributes"].get("review")
        review_track_name = instance.data["creator_attributes"].get(
            "reviewableTrack")

        if review_switch is True:
            instance.data["families"].append("review")
            instance.data.pop("reviewTrack")

        if (
            review_track_name != "< none >"
            and review_switch is not True
        ):
            instance.data["reviewTrack"] = review_track_name

        elif (
            review_track_name == "< none >"
            # the reviewTrack key is set to None if '< none >' is selected
            # in creator plugin
            and instance.data.get("reviewTrack", False) is None
        ):
            # lets just remove it if it is not relevant
            instance.data.pop("reviewTrack")

        # Retrieve instance data from parent instance shot instance.
        parent_instance_id = instance.data["parent_instance_id"]
        edit_shared_data = instance.context.data["editorialSharedData"]

        instance.data.update(
            edit_shared_data[parent_instance_id]
        )

        track_item = instance.data["item"]
        version_data = instance.data.setdefault("versionData", {})
        version_data["colorSpace"] = track_item.sourceMediaColourTransform()
