# ... (context before)

    def _get_frame_range(self, item):
        """Calculate and return the correct start and end frames."""
        source_in = item.sourceIn()
        source_out = item.sourceOut()
        duration = source_out - source_in + 1
        # Fix: end_frame should be start_frame + duration - 1
        start_frame = int(item.sourceIn())
        end_frame = start_frame + duration - 1
        return start_frame, end_frame

# ... (context after)