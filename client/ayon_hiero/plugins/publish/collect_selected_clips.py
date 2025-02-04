from pyblish import api

from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
)

from ayon_hiero.api import lib

import hiero


class CollectSelectedInstancesOnly(api.ContextPlugin, OptionalPyblishPluginMixin):
    """TODO"""

    order = api.CollectorOrder - 0.491
    label = "Publish only instance(s) from selected clips"
    hosts = ["hiero"]

    optional = True
    active = False

    def process(self, context):
        """
        """
        if not self.is_active(context.data):
            self.log.debug("Publish only instance(s) from selected clips was skipped")
            return

        to_remove = []
        current_selection = lib.get_timeline_selection()

        for instance in context:

            # Check if a clip item is associated
            # to the instance. If yes, then remove it
            # if it is not selected.
            clip_index = instance.data.get("clip_index")
            item = self._find_track_item_from_clip_index(clip_index)
            if item and item not in current_selection:
                to_remove.append(instance)

        # TODO:
        # Check if a plate/audio instance remains
        # with no shot associated

        for re_instance in to_remove:
            context.remove(re_instance)

    @staticmethod
    def _find_track_item_from_clip_index(clip_index):
        active_timeline = hiero.ui.activeSequence()
        for video_track in active_timeline.videoTracks():
            for item in video_track.items():
                if item.guid() == clip_index:
                    return item

        return None
