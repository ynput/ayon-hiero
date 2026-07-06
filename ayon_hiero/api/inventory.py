# -*- coding: utf-8 -*-
"""Inventory management for Hiero."""

import hiero.core
from ayon_core.lib import Logger
from ayon_hiero.api import plugin

log = Logger.get_logger(__name__)


def update_to_latest(selected_items, create_new_track=True):
    """Update selected items to latest published version.

    If create_new_track is True, the updated version will be placed on a new
    video track (below the current track) and the original clip is kept.
    Otherwise, the clip is replaced in place.

    Args:
        selected_items (list): List of hiero.core.TrackItem.
        create_new_track (bool, optional): Whether to create a new track.
            Defaults to True.
    """
    for item in selected_items:
        # Determine the current version and track
        original_track = item.parent()
        if not original_track:
            log.warning("Item has no parent track, skipping.")
            continue
        seq = original_track.parent()
        if not seq:
            log.warning("Track has no parent sequence, skipping.")
            continue

        # Get the new version representation (placeholder for actual version lookup)
        new_version = _get_latest_version(item)
        if not new_version:
            log.warning("No new version found for %s", item.name())
            continue

        if create_new_track:
            # Create a new video track
            track_name = f"Updated - {original_track.name()}"
            new_track = hiero.core.VideoTrack(track_name)
            # Insert new track below the original track
            # Get index of original track
            tracks = list(seq.videoTracks())
            orig_index = tracks.index(original_track)
            seq.addTrack(new_track, position=orig_index + 1)

            # Create a new track item from the new version
            new_item = _create_track_item_from_version(new_version, item)
            new_track.addItem(new_item)
            log.info("Added updated version to new track '%s'", track_name)
        else:
            # Replace in place (original behavior)
            _replace_track_item(item, new_version)
            log.info("Replaced item on original track")


def _get_latest_version(item):
    """Placeholder: retrieve the latest version for the given track item.
    This should query the AYON database.
    """
    # TODO: Implement actual version lookup
    return None


def _create_track_item_from_version(version, source_item):
    """Create a new TrackItem from a version representation.

    Args:
        version: Version data.
        source_item (hiero.core.TrackItem): Original item to copy attributes.

    Returns:
        hiero.core.TrackItem: New track item.
    """
    # This is a simplified example - in reality you'd create a clip from the
    # version's media and set its timing to match the original.
    new_item = hiero.core.TrackItem(source_item.name() + "_updated")
    new_item.setTiming(source_item.timelineIn(),
                       source_item.timelineOut(),
                       source_item.sourceIn(),
                       source_item.sourceOut())
    # Copy any other relevant attributes (e.g., source, effects, etc.)
    return new_item


def _replace_track_item(item, version):
    """Replace the clip source of an existing track item with a new version.
    This is the standard update without creating a new track.
    """
    # TODO: Implement actual replacement
    pass


# Optional: expose a setting to control behavior
SETTINGS = {
    "create_new_track_on_update": True
}
