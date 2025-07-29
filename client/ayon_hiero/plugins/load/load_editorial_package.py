from typing import Dict, Any
from pathlib import Path
import os
import glob
from ayon_core.pipeline import (
    AYON_CONTAINER_ID,
    load,
    get_representation_path,
)

from ayon_hiero.api import lib, tags

import hiero.core


class LoadEditorialPackage(load.LoaderPlugin):
    """Load editorial package to timeline.
    """
    product_types = {"editorial_pkg"}

    representations = {"*"}
    extensions = {"otio"}

    label = "Load as Timeline"
    order = -10
    icon = "ei.align-left"
    color = "orange"

    @classmethod
    def _get_container_data(
            cls,
            context: Dict[str, Any],
            seq: hiero.core.Sequence
        ) -> Dict[str, str]:
        version_entity = context["version"]
        return {
            "schema": "ayon:container-3.0",
            "id": AYON_CONTAINER_ID,
            "loader": str(cls.__name__),
            "author": version_entity["data"]["author"],
            "representation": context["representation"]["id"],
            "version": version_entity["version"],
            "name": seq.guid(),
            "namespace": seq.name(),
            "objectName": seq.name(),
        }

    def load(self, context, name, namespace, data):
        files = get_representation_path(context["representation"])
        seq_bin = lib.create_bin(f"/{name}")

        # Load clip
        dirname = os.path.dirname(files)
        media_paths = glob.glob(Path(dirname,"*.mov").as_posix())
        conf_media_path = Path(media_paths[0]).as_posix()
        seq_bin.createClip(conf_media_path)

        # Load sequence from otio
        seq = seq_bin.importSequence(files)

        # Remap all clip to loaded clip
        # (for some reasons, Hiero does not link the media properly)
        for track in seq.items():
            for track_item in track.items():
                track_item.replaceClips(conf_media_path)

        # Set Tag for loaded instance
        edpkg_tag = tags.get_or_create_workfile_tag(
            f"{seq.guid()}_{name}",
            create=True
        )
        tag_data = {
            "metadata": self._get_container_data(context, seq),
            "note": "AYON editorial pkg data",
        }
        tags.update_tag(edpkg_tag, tag_data)

    def update(self, container, context):
        """Update the container with the latest version."""
        product_name = context["product"]["name"]
        seq_guid = container["name"]
        tags.remove_workfile_tag(f"{seq_guid}_{product_name}",)

        self.load(
            context,
            product_name,
            container["namespace"],
            container,
        )
