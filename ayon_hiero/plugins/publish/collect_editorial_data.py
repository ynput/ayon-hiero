import hiero.core

def collect_editorial_data(clip, media_source, asset_name, **kwargs):
    """Collect editorial data for publish."""
    track_item = clip
    source = media_source
    
    # Get source in/out points
    source_in = track_item.sourceIn()
    source_out = track_item.sourceOut()
    
    # Calculate duration
    duration = source_out - source_in + 1
    
    # Get start frame from source media
    start_frame = source.sourceMediaIn()
    
    # FIX: Calculate end frame correctly (inclusive)
    # Original code had: end_frame = start_frame + duration
    # which resulted in end_frame being one frame too high.
    end_frame = start_frame + duration - 1
    
    return {
        "asset_name": asset_name,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "duration": duration,
        "source_in": source_in,
        "source_out": source_out,
        "source_fps": source.framerate()
    }
