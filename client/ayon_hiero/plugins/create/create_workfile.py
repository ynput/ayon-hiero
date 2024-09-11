# -*- coding: utf-8 -*-
"""Creator plugin for creating workfiles."""
import json

import hiero.core

import ayon_api

from ayon_core.pipeline.create import CreatedInstance, AutoCreator

from ayon_hiero.api import lib


class CreateWorkfile(AutoCreator):
    """Workfile auto-creator."""
    settings_category = "hiero"

    identifier = "io.ayon.creators.hiero.workfile"
    label = "Workfile"
    product_type = "workfile"
    icon = "fa5.file"

    default_variant = "Main"

    AYON_DATA_TAG_BIN = "AyonData"
    AYON_DATA_TAG_NAME = "workfile"

    @classmethod
    def _get_or_create_workfile_tag(cls, create=False):
        """
        Args:
            create (bool): Create the project tag if missing.

        Returns:
            hiero.core.Tag: The workfile tag or None
        """
        current_project = lib.get_current_project()

        # retrieve parent tag bin
        project_tag_bin = current_project.tagsBin()
        for tag_bin in project_tag_bin.bins():
            if tag_bin.name() == cls.AYON_DATA_TAG_BIN:
                break
        else:
            if create:
                tag_bin = project_tag_bin.addItem(cls.AYON_DATA_TAG_BIN)
            else:
                return None

        # retrieve tag
        for item in tag_bin.items():
            if (isinstance(item, hiero.core.Tag) and 
                item.name() == cls.AYON_DATA_TAG_NAME):
                return item

        workfile_tag = hiero.core.Tag(cls.AYON_DATA_TAG_NAME)
        tag_bin.addItem(workfile_tag)
        return workfile_tag

    @classmethod
    def dump_instance_data(cls, data):
        """ Dump instance data into AyonData project tag.

        Args:
            data (dict): The data to push to the project tag.
        """
        project_tag = cls._get_or_create_workfile_tag(create=True)
        metadata = project_tag.metadata()
        metadata.setValue(
            cls.identifier,
            json.dumps(data),
        )

    def load_instance_data(cls):
        """ Returns the data stored in AyonData project tag if any.

        Returns:
            dict. The project data.
        """
        project_tag = cls._get_or_create_workfile_tag()
        if project_tag is None:
            return {}

        metadata = project_tag.metadata()
        try:
            raw_data = dict(metadata)[cls.identifier]
            instance_data = json.loads(raw_data)

        except (KeyError, json.JSONDecodeError):  # missing or invalid data
            instance_data = {}

        return instance_data

    def _create_new_instance(self):
        """Create a new workfile instance.

        Returns:
            dict. The data of the instance to be created.
        """
        project_name = self.create_context.get_current_project_name()
        folder_path = self.create_context.get_current_folder_path()
        task_name = self.create_context.get_current_task_name()
        host_name = self.create_context.host_name
        variant = self.default_variant

        folder_entity = ayon_api.get_folder_by_path(
            project_name, folder_path
        )
        task_entity = ayon_api.get_task_by_name(
            project_name, folder_entity["id"], task_name
        )
        product_name = self.get_product_name(
            project_name,
            folder_entity,
            task_entity,
            variant,
            host_name,
        )

        instance_data = {
            "folderPath": folder_path,
            "task": task_name,
            "variant": variant,
            "productName": product_name,
        }
        instance_data.update(self.get_dynamic_data(
            variant,
            task_name,
            folder_entity,
            project_name,
            host_name,
            False,
        ))

        return instance_data

    def create(self, options=None):
        """Auto-create an instance by default."""
        instance_data = self.load_instance_data()
        if instance_data:
            return

        self.log.info("Auto-creating workfile instance...")
        data = self._create_new_instance()
        current_instance = CreatedInstance(
            self.product_type, data["productName"], data, self)
        self._add_instance_to_context(current_instance)

    def collect_instances(self):
        """Collect from timeline marker or create a new one."""
        data = self.load_instance_data()
        if not data:
            return

        instance = CreatedInstance(
            self.product_type, data["productName"], data, self
        )
        self._add_instance_to_context(instance)

    def update_instances(self, update_list):
        """Store changes in project metadata so they can be recollected.

        Args:
            update_list(List[UpdateData]): Gets list of tuples. Each item
                contain changed instance and its changes.
        """        
        for created_inst, _ in update_list:
            data = created_inst.data_to_store()
            self.dump_instance_data(data)
