import json
import re
import hiero

import ayon_api

from ayon_core.lib import Logger
from ayon_core.pipeline import get_current_project_name

from . import constants


log = Logger.get_logger(__name__)


def tag_data():
    return {
        "[Lenses]": {
            "Set lense here": {
                "editable": "1",
                "note": "Adjust parameters of your lense and then drop to clip. Remember! You can always overwrite on clip",  # noqa
                "icon": "lense.png",
                "metadata": {
                    "focalLengthMm": 57

                }
            }
        },
        # "NukeScript": {
        #     "editable": "1",
        #     "note": "Collecting track items to Nuke scripts.",
        #     "icon": "icons:TagNuke.png",
        #     "metadata": {
        #         "productType": "nukescript",
        #         "productName": "main"
        #     }
        # },
        "Comment": {
            "editable": "1",
            "note": "Comment on a shot.",
            "icon": "icons:TagComment.png",
            "metadata": {
                "productType": "comment",
                "productName": "main"
            }
        },
        "FrameMain": {
            "editable": "1",
            "note": "Publishing a frame product.",
            "icon": "z_layer_main.png",
            "metadata": {
                "productType": "frame",
                "productName": "main",
                "format": "png"
            }
        }
    }


def create_tag(key, data):
    """
    Creating Tag object.

    Args:
        key (str): name of tag
        data (dict): parameters of tag

    Returns:
        object: Tag object
    """
    tag = hiero.core.Tag(str(key))
    return update_tag(tag, data)


def update_tag(tag, data):
    """
    Fixing Tag object.

    Args:
        tag (obj): Tag object
        data (dict): parameters of tag
    """
    # set icon if any available in input data
    if data.get("icon"):
        tag.setIcon(str(data["icon"]))

    # get metadata of tag
    mtd = tag.metadata()
    # get metadata key from data
    data_mtd = data.get("metadata", {})

    mtd.setValue(
        f"tag.json_metadata",
        json.dumps(data_mtd)
    )
    # set note description of tag
    if "note" in data:
        tag.setNote(str(data["note"]))

    return tag


def get_tag_data(tag):
    """
    Args:
        tag (hiero.core.Tag): The tag to retrieve data from.

    Returns:
        dict. The tag data.
    """
    tag_data = dict(tag.metadata())

    try:
        json_data = tag_data["tag.json_metadata"]
        return json.loads(json_data)

    except (KeyError, json.JSONDecoderError):
        return {}


def get_or_create_workfile_tag(create=False):
    """
    Args:
        create (bool): Create the project tag if missing.

    Returns:
        hiero.core.Tag: The workfile tag or None
    """
    from .lib import get_current_project    
    current_project = get_current_project()

    # retrieve parent tag bin
    project_tag_bin = current_project.tagsBin()
    for tag_bin in project_tag_bin.bins():
        if tag_bin.name() == constants.AYON_WORKFILE_TAG_BIN:
            break
    else:
        if create:
            tag_bin = project_tag_bin.addItem(constants.AYON_WORKFILE_TAG_BIN)
        else:
            return None

    # retrieve tag
    for item in tag_bin.items():
        if (isinstance(item, hiero.core.Tag) and 
            item.name() == constants.AYON_WORKFILE_TAG_NAME):
            return item

    workfile_tag = hiero.core.Tag(constants.AYON_WORKFILE_TAG_NAME)
    tag_bin.addItem(workfile_tag)
    return workfile_tag


def add_tags_to_workfile():
    """
    Will create default tags from presets.
    """
    from .lib import get_current_project

    def add_tag_to_bin(root_bin, name, data):
        # for Tags to be created in root level Bin
        # at first check if any of input data tag is not already created
        done_tag = next((t for t in root_bin.items()
                        if str(name) in t.name()), None)

        if not done_tag:
            # create Tag
            tag = create_tag(name, data)
            tag.setName(str(name))

            log.debug("__ creating tag: {}".format(tag))
            # adding Tag to Root Bin
            root_bin.addItem(tag)
        else:
            # update only non hierarchy tags
            update_tag(done_tag, data)
            done_tag.setName(str(name))
            log.debug("__ updating tag: {}".format(done_tag))

    # get project and root bin object
    project = get_current_project()
    root_bin = project.tagsBin()

    if "Tag Presets" in project.name():
        return

    log.debug("Setting default tags on project: {}".format(project.name()))

    # get hiero tags.json
    nks_pres_tags = tag_data()

    # Get project task types.
    project_name = get_current_project_name()
    project_entity = ayon_api.get_project(project_name)
    task_types = project_entity["taskTypes"]
    nks_pres_tags["[Tasks]"] = {}
    log.debug("__ tasks: {}".format(task_types))
    for task_type in task_types:
        task_type_name = task_type["name"]
        nks_pres_tags["[Tasks]"][task_type_name.lower()] = {
            "editable": "1",
            "note": task_type_name,
            "icon": "icons:TagGood.png",
            "metadata": {
                "productType": "task",
                "type": task_type_name
            }
        }

    # loop through tag data dict and create deep tag structure
    for _k, _val in nks_pres_tags.items():
        # check if key is not decorated with [] so it is defined as bin
        bin_find = None
        pattern = re.compile(r"\[(.*)\]")
        _bin_finds = pattern.findall(_k)
        # if there is available any then pop it to string
        if _bin_finds:
            bin_find = _bin_finds.pop()

        # if bin was found then create or update
        if bin_find:
            root_add = False
            # first check if in root lever is not already created bins
            bins = [b for b in root_bin.items()
                    if b.name() in str(bin_find)]

            if bins:
                bin = bins.pop()
            else:
                root_add = True
                # create Bin object for processing
                bin = hiero.core.Bin(str(bin_find))

            # update or create tags in the bin
            for __k, __v in _val.items():
                add_tag_to_bin(bin, __k, __v)

            # finally add the Bin object to the root level Bin
            if root_add:
                # adding Tag to Root Bin
                root_bin.addItem(bin)
        else:
            add_tag_to_bin(root_bin, _k, _val)

    log.info("Default Tags were set...")
