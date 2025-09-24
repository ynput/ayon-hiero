"""Collect comments from tags on selected track items and their sources."""
from __future__ import annotations
from pyblish import api

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hiero.core import Tag


class CollectClipTagComments(api.InstancePlugin):
    """Collect comments from tags on selected track items and their sources."""

    order = api.CollectorOrder - 0.077
    label = "Collect Comments"
    hosts = ["hiero"]
    families = ["clip"]

    def process(self, instance: api.Instance) -> None:
        # Collect comments.
        comments = []

        # Exclude non-tagged instances.
        for tag in instance.data["tags"]:
            tag: Tag
            if tag.name().lower() == "comment":
                comment = tag.metadata()["tag.note"]
                comments.extend(
                    comment.split("\n")
                )

        if comments:
            # first get any existing comment
            comment = instance.data.get("comment", "")
            if comment:
                # include the existing comment
                comments.insert(0, comment)

            instance.data["comment"] = " | ".join(comments)

        self.log.info(f"Collected {len(comments)} comments.")
        self.log.debug(f"Comments: {comments}")
