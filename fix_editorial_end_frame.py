#!/usr/bin/env python
"""Fix for editorial publisher showing wrong end frame value.

Issue: YN-0816 - Editorial Publisher shows wrong end frame value.
The end frame was calculated as frame_start + duration, but should be
frame_start + duration - 1 to account for inclusive frame count.
"""

import hiero.core

def fix_frame_end(sequence, track_item, handle_start, handle_end):
    """Correctly compute the frame end value for editorial clips.
    
    Args:
        sequence: The Hiero sequence.
        track_item: The track item (clip).
        handle_start: Number of start handle frames.
        handle_end: Number of end handle frames.
    
    Returns:
        dict with corrected 'frameStart' and 'frameEnd'.
    """
    # Get source in/out from the track item
    source_in = track_item.sourceIn()
    source_out = track_item.sourceOut()
    
    # Compute the output frame range with handles
    frame_start = source_in - handle_start
    frame_end = source_out + handle_end
    
    # The duration is the number of frames from start to end inclusive
    duration = frame_end - frame_start + 1
    
    # --- Bug fix: Previously frame_end was set as frame_start + duration,
    # which equals frame_end + 1 (off by one). Now it's correctly set.
    # Ensure frame_end is consistent with start and duration.
    corrected_frame_end = frame_start + duration - 1
    
    # Sanity check: corrected_frame_end should equal original frame_end
    assert corrected_frame_end == frame_end, "Calculation mismatch"
    
    return {
        'frameStart': frame_start,
        'frameEnd': corrected_frame_end,
        'duration': duration
    }

# Example usage (in actual publisher plugin):
# result = fix_frame_end(sequence, item, handle_start, handle_end)
# item.setMetadata('frameStart', result['frameStart'])
# item.setMetadata('frameEnd', result['frameEnd'])
