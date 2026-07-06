# Update logic for ayon-hiero
# Adds feature to create new track when updating to a new version

from ayon_hiero.hiero.api import get_current_sequence
from ayon_hiero.hiero.lib import get_version_data
from ayon_core.lib import Logger

log = Logger.get_logger(__name__)

def update_clips_to_latest(clip_items, create_new_track=True):
    """
    Update selected clips to latest version.
    If create_new_track is True, old clips are kept and new clips are placed on a new track.
    """
    sequence = get_current_sequence()
    if not sequence:
        log.error("No active sequence found.")
        return

    # Group selections by track to create one new track per original track
    track_groups = {}
    for item in clip_items:
        track = item.parent()
        if track not in track_groups:
            track_groups[track] = []
        track_groups[track].append(item)

    for original_track, items in track_groups.items():
        if not items:
            continue

        # Determine new track name
        new_track_name = f"{original_track.name()} - Updated"
        # Ensure unique track name
        existing_tracks = [t.name() for t in sequence.videoTracks()]
        if new_track_name in existing_tracks:
            counter = 1
            while f"{new_track_name}_{counter}" in existing_tracks:
                counter += 1
            new_track_name = f"{new_track_name}_{counter}"

        # Create new video track (insert above original)
        new_track = sequence.createTrack("Video", new_track_name)
        # Reorder track to be immediately above original track
        original_index = sequence.videoTracks().index(original_track)
        new_track_index = len(sequence.videoTracks()) - 1  # last index
        # Move new track to just above original (if not already)
        sequence.moveTrack(new_track, original_index)

        # Process each clip
        for item in items:
            original_clip = item.source()
            # Get latest version info
            version_data = get_version_data(item)
            if not version_data:
                log.warning(f"Cannot get version data for {item.name()}")
                continue
            latest_version = version_data.get("latest_version")
            if not latest_version:
                log.warning(f"No latest version found for {item.name()}")
                continue

            # Create new clip from latest version
            # This is a simplified placeholder; actual creation depends on AYON API
            # For production, use hiero.core.createClip or similar
            from ayon_hiero.hiero.lib import create_clip_from_media
            new_clip = create_clip_from_media(latest_version)
            # Copy basic attributes: timecode, duration, effects (simplified)
            new_clip.setTimelineIn(item.timelineIn())
            new_clip.setTimelineOut(item.timelineOut())
            new_clip.setSourceIn(item.sourceIn())
            new_clip.setSourceOut(item.sourceOut())
            # Copy transform and effects if needed (omitted for brevity)
            # Add new clip to new track
            new_track.addClip(new_clip)

        log.info(f"Updated {len(items)} clips to new track '{new_track_name}'")

def update_to_latest_dialog(clip_items):
    """Wrapper to be called from UI. Uses create_new_track=True."""
    update_clips_to_latest(clip_items, create_new_track=True)
