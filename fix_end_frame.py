# Fix for YN-0816: Editorial publisher shows wrong end frame value
# The issue is an off-by-one error in end frame calculation.
# Typical pattern: end_frame = start_frame + duration - 1

import ayon_hiero.api.editorial as editorial

def patched_get_frame_range(sequence):
    """Return correct start and end frames for a sequence."""
    fps = sequence.framerate()
    start = sequence.timecodeStart()
    end = sequence.timecodeEnd()
    # Convert timecode to frames
    tc_start = editorial.timecode_to_frames(start, fps)
    tc_end = editorial.timecode_to_frames(end, fps)
    # Ensure end is correct (not +1 extra)
    # If sequence duration is n frames, end should be start + n - 1
    duration = sequence.duration()
    expected_end = tc_start + duration - 1
    if tc_end != expected_end:
        # Force correction
        tc_end = expected_end
    return tc_start, tc_end

# Apply patch
editorial.get_frame_range = patched_get_frame_range
