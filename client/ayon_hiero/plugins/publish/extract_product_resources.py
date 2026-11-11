import math
import os
from typing import Any, Dict, List, Optional, Tuple

import pyblish.api

from ayon_core.lib import filter_profiles
from ayon_core.pipeline import PublishError, publish
from ayon_hiero.api import render_progress, rendering


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

    With Hiero's UI the renders run in the export queue and a modal dialog
    shows which clip and output renders and how far the publish is, with
    a button to cancel it.

    The order is the one of the Flame and Resolve plugins: after the
    collectors, before ayon-core's `ExtractOTIOTrimmingVideo`
    (ExtractorOrder), which skips without a 'trim' tagged representation,
    and before `ExtractReview` (ExtractorOrder + 0.02), so a rendered
    output tagged 'review' becomes reviewable.
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
        product_base_type = self._get_product_base_type(instance)
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

        keep_original = bool(profile.get("keep_original_representation"))
        instance.data.setdefault("representations", [])
        if not keep_original:
            instance.data["representations"] = []

        # Check the names before anything is rendered
        names = [self._get_output_name(output) for output in outputs]
        taken = {repre["name"] for repre in instance.data["representations"]}
        for name in names:
            if name in taken:
                raise PublishError(
                    f"Representation name '{name}' of profile "
                    f"'{profile.get('name')}' is used twice.",
                    description=(
                        "Each output needs its own representation name, "
                        "different from the original media one "
                        f"('{name}') when it is kept. Set the "
                        "`Representation name` of the output in the Hiero "
                        "addon settings: `Publish plugins > Extract "
                        "Product Resources`."
                    ),
                )
            taken.add(name)

        dialog, clip_index, outputs_done = self._start_progress(instance)
        results = []
        try:
            for index, (output, name) in enumerate(zip(outputs, names)):
                if dialog is not None:
                    dialog.start_output(
                        clip_index,
                        instance.data.get("label")
                        or instance.data["productName"],
                        index + 1,
                        len(outputs),
                        f"{name} ({output['file_type']},"
                        f" {self.render_submission})",
                        outputs_done + index,
                    )
                results.append(
                    self._render_output(instance, output, name, dialog)
                )
        finally:
            if dialog is not None:
                dialog.finish()
        if not keep_original:
            self._update_handles(instance, results)

    @staticmethod
    def _get_product_base_type(instance) -> str:
        return (
            instance.data.get("productBaseType")
            or instance.data["productType"]
        )

    def _start_progress(self, instance):
        """Progress dialog for the instance's renders, without UI None.

        The clips and outputs to render are counted once per publish, from
        the instances this plugin processes and their profiles.

        Returns:
            tuple: The dialog, the position of the clip from 1 and the
                outputs of the publish rendered before the clip's.
        """
        if not render_progress.has_gui():
            return None, 0, 0

        context = instance.context
        plan = context.data.get("hieroProductResourcesRenders")
        if plan is None:
            plan = {}
            for other in pyblish.api.instances_by_plugin(context, type(self)):
                if not other.data.get("publish", True):
                    continue
                product_base_type = self._get_product_base_type(other)
                profile = self._get_profile(other, product_base_type)
                outputs = (profile or {}).get(product_base_type) or []
                if outputs:
                    plan[other.id] = len(outputs)
            context.data["hieroProductResourcesRenders"] = plan

        if instance.id not in plan:
            # Not counted, e.g. data changed since: render it on its own
            plan = {instance.id: 0}
        clip_ids = list(plan)
        position = clip_ids.index(instance.id)
        outputs_done = sum(plan[clip_id] for clip_id in clip_ids[:position])
        dialog = render_progress.RenderProgressDialog(
            clip_count=len(plan),
            output_count=max(sum(plan.values()), outputs_done + 1),
        )
        return dialog, position + 1, outputs_done

    @staticmethod
    def _get_output_name(output: Dict[str, Any]) -> str:
        """Representation name of an output, the file extension if empty."""
        if output.get("repre_name"):
            return output["repre_name"]
        try:
            return rendering.get_file_extension(output["file_type"])
        except rendering.RenderError as exc:
            raise PublishError(str(exc)) from exc

    def _update_handles(self, instance, results):
        """Make the version handles describe the rendered files.

        ayon-core sets the version handles for the original media. When
        the rendered outputs replace it, the handles of the first image
        sequence (or the first output) are the ones published.
        """
        sequences = [result for _, result in results if result.is_sequence]
        main = sequences[0] if sequences else results[0][1]
        handles = (main.handle_start, main.handle_end)
        for name, result in results:
            if (result.handle_start, result.handle_end) != handles:
                self.log.warning(
                    "Output '%s' has handles %s/%s, the version has %s/%s.",
                    name,
                    result.handle_start,
                    result.handle_end,
                    *handles,
                )
        version_data = instance.data.setdefault("versionData", {})
        version_data["handleStart"], version_data["handleEnd"] = handles
        instance.data["handleStart"], instance.data["handleEnd"] = handles

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
        # movie count from its first frame already. The available range
        # of a sequence starts at its timecode, not at its first file.
        if is_clip_from_media_sequence(otio_clip):
            offset = otio_clip.media_reference.start_frame
            media_in -= offset
            media_out -= offset
        return (
            (media_in, media_out),
            int(retimed["handleStart"]),
            int(retimed["handleEnd"]),
        )

    def _render_output(
        self,
        instance,
        output: Dict[str, Any],
        name: str,
        progress: Optional[rendering.RenderProgress] = None,
    ) -> Tuple[str, rendering.RenderResult]:
        track_item = instance.data["trackItem"]
        file_type = output["file_type"]
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
                progress=progress,
            )
        except rendering.RenderCancelled as exc:
            raise PublishError(
                f"Rendering '{name}' of '{track_item.name()}' was cancelled.",
                description="The render was cancelled in its progress dialog.",
            ) from exc
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
            # A single frame is a file name, not a one item sequence, which
            # the integrator rejects as "not proper sequence files"
            "files": filenames if len(filenames) > 1 else filenames[0],
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
        return name, result
