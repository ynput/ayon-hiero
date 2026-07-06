# Update to New Track Action for AYON-Hiero

This action updates selected timeline clips to their latest version
but places the new version on a newly created track, preserving the
original clip for comparison.

## Installation
Place `update_to_new_track.py` in the AYON Hiero actions directory
(e.g., `~/.ayon/hiero/actions/`).

## Usage
1. Select one or more clips in the timeline.
2. From the AYON menu or using `Ctrl+Shift+U`, run "Update to New Track".
3. A new video track named "Updated v<version>" is created and the
   latest version clip is placed at the same timeline position.

## Requirements
- AYON Python API (`ayon_api`)
- Hiero 10.0+