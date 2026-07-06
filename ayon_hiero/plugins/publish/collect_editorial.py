import pyblish.api
from ayon_core.pipeline import publish


class CollectEditorialInstances(publish.BaseCreator):
    """Collect editorial instances from Hiero timeline."""

    def process(self, instance):
        # Assume instance has 'handleStart', 'handleEnd', 'sourceStart', 'sourceDuration'
        source_start = instance.data.get('sourceStart', 0)
        source_duration = instance.data.get('sourceDuration', 0)
        handle_start = instance.data.get('handleStart', 0)
        handle_end = instance.data.get('handleEnd', 0)

        # Compute frame range
        frame_start = source_start - handle_start
        frame_end = source_start + source_duration - 1 + handle_end  # Fixed off-by-one

        instance.data['frameStart'] = frame_start
        instance.data['frameEnd'] = frame_end

        self.log.debug(f"Frame range: {frame_start} - {frame_end}")
