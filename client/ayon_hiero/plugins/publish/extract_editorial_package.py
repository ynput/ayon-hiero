from __future__ import annotations

from typing import Any
import os
from copy import deepcopy
from pathlib import Path

import pyblish.api
import opentimelineio as otio

from ayon_core.pipeline import publish

from ayon_hiero.api import rendering
from ayon_hiero.api.otio import hiero_export


class ExtractEditorialPackage(publish.Extractor):
    """Extract and Render intermediate file for Editorial Package"""

    label = "Extract Editorial Package"
    order = pyblish.api.ExtractorOrder + 0.45
    families = ["editorial_pkg"]

    @staticmethod
    def _get_anticipated_publish_path(
            instance: pyblish.api.Instance,
            repre_data: dict[str, Any],
        ) -> str:
        anatomy = instance.context.data["anatomy"]
        template_data = deepcopy(instance.data["anatomyData"])
        template_data["root"] = anatomy.roots
        template_data["representation"] = repre_data["name"]
        template_data["ext"] = repre_data["ext"]
        template_data.pop("comment", None)

        template = anatomy.get_template_item("publish", "default", "path")
        template_filled = template.format_strict(template_data)
        file_path = Path(template_filled)
        return file_path.as_posix()

    @staticmethod
    def _remap_all_clips_to_media(
            otio_timeline: otio.schema.Timeline,
            media_path: str
        ):

        # Make new media reference to store in clips
        timeline_fps = otio_timeline.duration().rate
        timeline_duration = otio_timeline.duration().to_frames()
        timeline_start_frame = otio_timeline.global_start_time.to_frames()
        new_media_reference = otio.schema.ExternalReference(
            target_url=media_path,
            available_range=otio.opentime.TimeRange(
                start_time=otio.opentime.RationalTime(
                    value=timeline_start_frame,
                    rate=timeline_fps,
                ),
                duration=otio.opentime.RationalTime(
                    value=timeline_duration,
                    rate=timeline_fps,
                ),
            ),
        )

        # Remap all media clips from the timeline
        for track in otio_timeline.tracks:
            for clip in track:
                if (
                    not hasattr(clip, "media_reference")
                ):
                    # Skip non-media related clips
                    continue

                clip.media_reference = new_media_reference
                clip.source_range = otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(
                        value=(
                            timeline_start_frame
                            + clip.range_in_parent().start_time.value
                        ),
                        rate=timeline_fps,
                    ),
                    duration=clip.range_in_parent().duration,
                )

    def process(self, instance: pyblish.api.Instance):
        instance.data.setdefault("representations", [])

        temp_dir = self.staging_dir(instance)
        seq = instance.data["hiero_sequence"]

        # Export timeline as consolidated media
        output_video = os.path.join(
            temp_dir,
            f"{seq.guid()}_intermediate.mov"
        )
        rendering.render_sequence_as_quicktime(
            output_video,
            sequence=seq
        )
        intermediate_repre = {
            "name": "intermediate",
            "ext": "mov",
            "files": os.path.basename(output_video),
            "stagingDir": temp_dir,
            "tags": ["review"]
        }
        instance.data["representations"].append(intermediate_repre)
        published_path = self._get_anticipated_publish_path(
            instance,
            intermediate_repre
        )
        self.log.info(
            "Added intermediate file representation: "
            f"{intermediate_repre}"
        )

        # Export sequence as OTIO but remap to rendered consolidated media
        otio_timeline = hiero_export.create_otio_timeline(
            sequence=seq,
        )
        self._remap_all_clips_to_media(
            otio_timeline,
            published_path,
        )

        # Export resulting OTIO file and add as representation.
        remap_otio_file = os.path.join(
            temp_dir,
            f"{seq.guid()}_remap.otio"
        )
        otio.adapters.write_to_file(
            otio_timeline,
            remap_otio_file
        )
        representation_otio = {
            "name": "editorial_pkg",
            "ext": "otio",
            "files": os.path.basename(remap_otio_file),
            "stagingDir": temp_dir,
        }
        instance.data["representations"].append(representation_otio)

        self.log.info(
            "Added OTIO file representation: "
            f"{representation_otio}"
        )
