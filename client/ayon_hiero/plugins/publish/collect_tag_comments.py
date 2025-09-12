"""Collect comments from tags on selected track items and their sources."""
from __future__ import annotations
from pyblish import api

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hiero.core import Tag


class CollectClipTagComments(api.InstancePlugin):
    """Collect comments from tags on selected track items and their sources."""

    order = api.CollectorOrder + 0.013
    label = "Collect Comments"
    hosts = ["hiero"]
    families = ["clip"]

    def process(self, instance: api.Instance) -> None:
        # Collect comments.
        instance.data["comments"] = []

        # Exclude non-tagged instances.
        for tag in instance.data["tags"]:
            tag: Tag
            if tag.name().lower() == "comment":
                instance.data["comments"].append(
                    tag.metadata()["tag.note"]
                )

        # Find tags on the source clip.
        tags = instance.data["trackItem"].source().tags()
        for tag in tags:
            tag: Tag
            if tag.name().lower() == "comment":
                instance.data["comments"].append(
                    tag.metadata().dict()["tag.note"]
                )

        # Update label with comments counter.
        instance.data["label"] = (
            f'{instance.data["label"]} - '
            f'comments:{len(instance.data["comments"])}'
        )
