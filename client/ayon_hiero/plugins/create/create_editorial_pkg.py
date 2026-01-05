from typing import Dict, List, Any

from ayon_core.pipeline.create import CreatedInstance, CreatorError
from ayon_core.lib import BoolDef, AbstractAttrDef

from ayon_hiero.api import plugin, tags, lib, constants

import hiero


_CREATE_ATTR_DEFS = [
    BoolDef(
        "review",
        label="Make intermediate media reviewable",
        tooltip="Make editorial package intermediate media reviewable.",
        default=False,
    )
]


class CreateEditorialPackage(plugin.HieroCreator):
    """Create Editorial Package."""

    identifier = "io.ayon.creators.hiero.editorial_pkg"
    label = "Editorial Package"
    product_type = "editorial_pkg"
    product_base_type = "editorial_pkg"
    icon = "camera"
    defaults = ["Main"]

    # Editorial_Pkg export relies on QuickExport feature
    # that is only available since 16.0.
    # https://learn.foundry.com/hiero/developers/16.0/HieroPythonDevGuide/quick_export.html
    enabled = hiero.core.env.get("VersionMajor", 0) >= 16

    def get_pre_create_attr_defs(self) -> List[AbstractAttrDef]:
        return _CREATE_ATTR_DEFS

    def get_attr_defs_for_instance(
            self,
            instance: CreatedInstance
        ) -> List[AbstractAttrDef]:
        return _CREATE_ATTR_DEFS

    @classmethod
    def _get_edl_tag_name(cls, guid: str) -> str:
        return f"{guid}_{cls.product_type}"

    @classmethod
    def dump_instance_data(
            cls,
            guid: str,
            data: Dict,
        ):
        edpkg_tag = tags.get_or_create_workfile_tag(
            cls._get_edl_tag_name(guid),
            create=True
        )
        tag_data = {
            "metadata": data,
            "note": "AYON editorial pkg data",
        }
        tags.update_tag(edpkg_tag, tag_data)

    def create(
            self,
            product_name: str,
            instance_data: Dict[str, Any],
            pre_create_data: Dict[str, Any]
        ):
        super().create(
            product_name,
            instance_data,
            pre_create_data
        )

        current_sequence = lib.get_current_sequence()
        if current_sequence is None:
            raise CreatorError("No active sequence.")

        instance_data["guid"] = current_sequence.guid()
        instance_data["label"] = f"{product_name} ({current_sequence.name()})"
        instance_data["creator_attributes"] = {
            "review": pre_create_data["review"]
        }

        new_instance = CreatedInstance(
            self.product_type,
            product_name,
            instance_data,
            self
        )
        self._add_instance_to_context(new_instance)

    def collect_instances(self):
        current_project = lib.get_current_project()
        project_tag_bin = current_project.tagsBin()
        for tag_bin in project_tag_bin.bins():
            if tag_bin.name() != constants.AYON_WORKFILE_TAG_BIN:
                continue

            for item in tag_bin.items():
                if (
                    not isinstance(item, hiero.core.Tag)
                    or not item.name().endswith(self.product_type)
                ):
                    continue

                instance_data = tags.get_tag_data(item)
                instance = CreatedInstance(
                    self.product_type,
                    instance_data["productName"],
                    instance_data,
                    self
                )
                self._add_instance_to_context(instance)

    def update_instances(self, update_list: List[CreatedInstance]):
        for created_inst, _ in update_list:
            data = created_inst.data_to_store()
            guid = created_inst.data["guid"]
            self.dump_instance_data(guid, data)

    def remove_instances(self, instances: List[CreatedInstance]):
        for inst in instances:
            guid = inst.data["guid"]
            tag_name = self._get_edl_tag_name(guid)
            tags.remove_workfile_tag(tag_name)
            self._remove_instance_from_context(inst)
