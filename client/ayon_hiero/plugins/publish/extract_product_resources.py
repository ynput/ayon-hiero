import math
import os
from typing import Any, Dict, List, Optional, Tuple

import pyblish.api

from ayon_core.lib import filter_profiles
from ayon_core.pipeline import PublishError, publish
from ayon_hiero.api import rendering


class ExtractProductResources(
    publish.Extractor,
    publish.ColormanagedPyblishPluginMixin,
):
    """Render additional representations of a clip product.

    Profiles from `hiero/publish/ExtractProductResources/profiles` match
    the publishing task and the product base type. Each output of the
    matching profile is rendered from the clip's source range with
    Hiero's exporter, retimes are not baked.

    Without a matching profile nothing is rendered and the clip's original
    media, collected by ayon-core's `CollectOTIOProductResources`, is
    published. With a profile the original media representation is
    replaced, unless `keep_original_representation` is enabled.
    """

    label = "Extract Product Resources"
    order = pyblish.api.ExtractorOrder - 0.45
    families = ["clip"]
    hosts = ["hiero"]

    settings_category = "hiero"

    # settings
    render_submission = rendering.DEFAULT_SUBMISSION
    profiles: List[Dict[str, Any]] = []

    def process(self, instance):
        product_base_type = (
            instance.data.get("productBaseType")
            or instance.data["productType"]
        )
        profile = self._get_profile(instance, product_base_type)
        if not profile:
            return

        outputs = profile.get(product_base_type) or []
        if not outputs:
            raise PublishError(
                f"Profile '{profile.get('name')}' of 'Extract Product "
                "Resources' has no output definitions.",
                description=(
                    "Add at least one output definition to the profile in "
                    "the Hiero addon settings: `Publish plugins > Extract "
                    "Product Resources`."
                ),
            )

        instance.data.setdefault("representations", [])
        if not profile.get("keep_original_representation"):
            instance.data["representations"] = []

        for output in outputs:
            self._render_output(instance, output)

    def _get_profile(
        self, instance, product_base_type: str
    ) -> Optional[Dict[str, Any]]:
        task = instance.data.get("anatomyData", {}).get("task") or {}
        profile = filter_profiles(
            self.profiles,
            {
                "task_types": task.get("type"),
                "task_names": task.get("name"),
                "product_base_type": product_base_type,
            },
            logger=self.log,
        )
        if not profile:
            self.log.debug(
                "No profile for task type '%s', task '%s' and product base "
                "type '%s', the clip's original media is published.",
                task.get("type"),
                task.get("name"),
                product_base_type,
            )
        return profile

    def _get_source_range(
        self, instance
    ) -> Tuple[Optional[Tuple[int, int]], int, int]:
        """Source range of the cut and handles, as ayon-core computes them.

        The original media representation of `CollectOTIOProductResources`
        uses this range, retimes and handles scaled by the speed included,
        so the rendered files get the same frames.

        Returns:
            tuple: First and last source frame relative to the clip start
                (None without an OTIO clip), handle start, handle end.
        """
        handle_start = instance.data["handleStart"]
        handle_end = instance.data["handleEnd"]
        otio_clip = instance.data.get("otioClip")
        if otio_clip is None:
            return None, handle_start, handle_end

        from ayon_core.pipeline.editorial import (
            get_media_range_with_retimes,
            is_clip_from_media_sequence,
        )

        retimed = get_media_range_with_retimes(
            otio_clip, handle_start, handle_end
        )
        # The same rounding as 'CollectOTIOProductResources'
        media_in = math.floor(retimed["mediaIn"])
        media_out = math.ceil(retimed["mediaOut"])
        # Frames of a sequence are its file frame numbers, frames of a
        # movie count from its first frame already.
        if is_clip_from_media_sequence(otio_clip):
            offset = otio_clip.available_range().start_time.to_frames()
            media_in -= offset
            media_out -= offset
        return (
            (media_in, media_out),
            int(retimed["handleStart"]),
            int(retimed["handleEnd"]),
        )

    def _render_output(self, instance, output: Dict[str, Any]):
        track_item = instance.data["trackItem"]
        file_type = output["file_type"]
        name = output.get("repre_name") or file_type
        tags = list(output.get("tags") or [])

        # ayon-core's 'CollectOTIOProductResources' sets the version frame
        # range, so it wins over the instance's.
        version_data = instance.data.get("versionData") or {}
        frame_start = version_data.get(
            "frameStart", instance.data["frameStart"]
        )
        source_range, handle_start, handle_end = self._get_source_range(
            instance
        )
        if not output.get("with_handles", True):
            handle_start = handle_end = 0

        codec_properties = {
            item["name"]: item["value"]
            for item in output.get("codec_properties") or []
            if item.get("name")
        }
        output_dir = os.path.join(self.staging_dir(instance), name)
        self.log.info(
            "Rendering '%s' of '%s' as %s into '%s'",
            name,
            track_item.name(),
            file_type,
            output_dir,
        )
        try:
            result = rendering.render_track_item(
                track_item,
                output_dir,
                name=name,
                file_type=file_type,
                codec_properties=codec_properties,
                colorspace=output.get("colorspace") or None,
                frame_start=frame_start,
                handle_start=handle_start,
                handle_end=handle_end,
                include_effects=output.get("include_effects", False),
                submission=self.render_submission,
                source_range=source_range,
            )
        except rendering.RenderError as exc:
            raise PublishError(
                f"Rendering '{name}' of '{track_item.name()}' failed: {exc}",
                description=(
                    "Check the clip's media and the output definition "
                    f"'{name}' in the Hiero addon settings: `Publish "
                    "plugins > Extract Product Resources`."
                ),
            ) from exc

        filenames = [os.path.basename(path) for path in result.files]
        representation = {
            "name": name,
            "outputName": name,
            "ext": os.path.splitext(filenames[0])[1].lstrip("."),
            "files": filenames if result.is_sequence else filenames[0],
            "stagingDir": output_dir,
            "tags": tags,
            "custom_tags": list(output.get("custom_tags") or []),
        }
        if result.is_sequence:
            representation["frameStart"] = result.frame_start
            representation["frameEnd"] = result.frame_end

        self.set_representation_colorspace(
            representation, instance.context, colorspace=result.colorspace
        )
        instance.data["representations"].append(representation)

        if "review" in tags and "review" not in instance.data["families"]:
            instance.data["families"].append("review")
        self.log.debug("Added representation: %s", representation)
