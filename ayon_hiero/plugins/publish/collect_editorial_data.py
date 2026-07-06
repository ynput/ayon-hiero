import hiero.core
from ayon_core.pipeline import KnownPublishError


class EditorialDataCollector:
    """Collects editorial data for publish."""

    def collect_clip_data(self, clip):
        """Extract frame range from a clip."""
        # Fix: correct end frame calculation (inclusive range)
        start = clip.sourceIn()
        duration = clip.sourceDuration()
        end = start + duration - 1

        return {
            "startFrame": start,
            "endFrame": end,
            "duration": duration
        }


def get_editorial_data(sequence):
    """Main entry point for editorial data collection."""
    collector = EditorialDataCollector()
    data = []
    for track in sequence.videoTracks():
        for clip in track:
            if not isinstance(clip, hiero.core.Clip):
                continue
            clip_data = collector.collect_clip_data(clip)
            data.append(clip_data)
    return data
