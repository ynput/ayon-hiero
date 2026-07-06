import hiero.core
from ayon_core.pipeline import KnownPublishError


class EditorialPublisher:
    """Publish editorial clips."""

    def __init__(self):
        self._clip_data = {}

    def _get_frame_range(self, clip):
        """Return correct frame range for a clip.

        Returns:
            dict: {'start': int, 'end': int, 'duration': int}
        """
        start = clip.sourceIn()
        duration = clip.sourceDuration()
        # BUG FIX: end frame must be inclusive (start + duration - 1)
        end = start + duration - 1
        return {
            'start': start,
            'end': end,
            'duration': duration
        }

    def _create_clip_data(self, clip):
        frame_range = self._get_frame_range(clip)
        data = {
            'name': clip.name(),
            'start_frame': frame_range['start'],
            'end_frame': frame_range['end'],
            'duration': frame_range['duration'],
            # ... other fields
        }
        return data

    def process(self, clip):
        if not clip:
            raise KnownPublishError("Invalid clip")
        return self._create_clip_data(clip)
