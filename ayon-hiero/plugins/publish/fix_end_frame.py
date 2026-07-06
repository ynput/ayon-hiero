def collect_editorial_clip(instance):
    """Fix end frame calculation: use inclusive end frame."""
    import hiero.core
    clip = instance.data["item"]
    source = clip.source()
    if source:
        # Get clip attributes
        handle_start = instance.data.get("handleStart", 0)
        handle_end = instance.data.get("handleEnd", 0)
        
        # Original problematic calculation (exclusive end):
        # frame_start = clip.sourceIn() - handle_start
        # frame_end = clip.sourceIn() + source.duration() + handle_end
        
        # Fixed calculation (inclusive end):
        frame_start = clip.sourceIn() - handle_start
        # source.duration() returns total frames, but sourceOut() is inclusive last frame.
        # Use sourceOut() and add handle_end.
        frame_end = clip.sourceOut() + handle_end
        # Ensure frame_end is not beyond source duration
        max_end = clip.sourceIn() + source.duration() - 1 + handle_end
        if frame_end > max_end:
            frame_end = max_end
        
        instance.data["frameStart"] = frame_start
        instance.data["frameEnd"] = frame_end
        
        # Also set standard publish data
        instance.data["fps"] = float(source.framerate())
        instance.data["resolutionWidth"] = source.width()
        instance.data["resolutionHeight"] = source.height()
    return instance