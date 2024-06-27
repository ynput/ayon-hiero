import os
import sys

import hiero.core
from hiero.ui import findMenuAction

from qtpy import QtGui

from ayon_core.lib import Logger, is_dev_mode_enabled
from ayon_core.tools.utils import host_tools
from ayon_core.settings import get_project_settings
from ayon_core.pipeline import (
    get_current_project_name,
    get_current_folder_path,
    get_current_task_name
)

from . import tags

log = Logger.get_logger(__name__)

self = sys.modules[__name__]
self._change_context_menu = None


def get_context_label():
    return "{}, {}".format(
        get_current_folder_path(),
        get_current_task_name()
    )


def update_menu_task_label():
    """Update the task label in Avalon menu to current session"""

    object_name = self._change_context_menu
    found_menu = findMenuAction(object_name)

    if not found_menu:
        log.warning("Can't find menuItem: {}".format(object_name))
        return

    label = get_context_label()

    menu = found_menu.menu()
    self._change_context_menu = label
    menu.setTitle(label)


def menu_install():
    """
    Installing menu into Hiero

    """

    from . import (
        publish, launch_workfiles_app, reload_config,
        apply_colorspace_project, apply_colorspace_clips
    )
    from .lib import get_main_window

    main_window = get_main_window()

    # here is the best place to add menu

    menu_name = os.environ['AYON_MENU_LABEL']

    context_label = get_context_label()

    self._change_context_menu = context_label

    try:
        check_made_menu = findMenuAction(menu_name)
    except Exception:
        check_made_menu = None

    if not check_made_menu:
        # Grab Hiero's MenuBar
        menu = hiero.ui.menuBar().addMenu(menu_name)
    else:
        menu = check_made_menu.menu()

    context_label_action = menu.addAction(context_label)
    context_label_action.setEnabled(False)

    menu.addSeparator()

    workfiles_action = menu.addAction("Work Files...")
    workfiles_action.setIcon(QtGui.QIcon("icons:Position.png"))
    workfiles_action.triggered.connect(launch_workfiles_app)

    default_tags_action = menu.addAction("Create Default Tags")
    default_tags_action.setIcon(QtGui.QIcon("icons:Position.png"))
    default_tags_action.triggered.connect(tags.add_tags_to_workfile)

    menu.addSeparator()

    creator_action = menu.addAction("Create...")
    creator_action.setIcon(QtGui.QIcon("icons:CopyRectangle.png"))
    creator_action.triggered.connect(
        lambda: host_tools.show_publisher(tab="create")
    )

    publish_action = menu.addAction("Publish...")
    publish_action.setIcon(QtGui.QIcon("icons:Output.png"))
    publish_action.triggered.connect(
        lambda *args: host_tools.show_publisher(tab="publish")
    )

    loader_action = menu.addAction("Load...")
    loader_action.setIcon(QtGui.QIcon("icons:CopyRectangle.png"))
    loader_action.triggered.connect(
        lambda: host_tools.show_loader(parent=main_window)
    )

    sceneinventory_action = menu.addAction("Manage...")
    sceneinventory_action.setIcon(QtGui.QIcon("icons:CopyRectangle.png"))
    sceneinventory_action.triggered.connect(
        lambda: host_tools.show_scene_inventory(parent=main_window)
    )

    library_action = menu.addAction("Library...")
    library_action.setIcon(QtGui.QIcon("icons:CopyRectangle.png"))
    library_action.triggered.connect(
        lambda: host_tools.show_library_loader(parent=main_window)
    )

    if is_dev_mode_enabled():
        menu.addSeparator()
        reload_action = menu.addAction("Reload pipeline")
        reload_action.setIcon(QtGui.QIcon("icons:ColorAdd.png"))
        reload_action.triggered.connect(reload_config)

    menu.addSeparator()
    apply_colorspace_p_action = menu.addAction("Apply Colorspace Project")
    apply_colorspace_p_action.setIcon(QtGui.QIcon("icons:ColorAdd.png"))
    apply_colorspace_p_action.triggered.connect(apply_colorspace_project)

    apply_colorspace_c_action = menu.addAction("Apply Colorspace Clips")
    apply_colorspace_c_action.setIcon(QtGui.QIcon("icons:ColorAdd.png"))
    apply_colorspace_c_action.triggered.connect(apply_colorspace_clips)

    menu.addSeparator()

    exeprimental_action = menu.addAction("Experimental tools...")
    exeprimental_action.triggered.connect(
        lambda: host_tools.show_experimental_tools_dialog(parent=main_window)
    )


def add_scripts_menu():
    try:
        from . import launchforhiero
    except ImportError:

        log.warning(
            "Skipping studio.menu install, because "
            "'scriptsmenu' module seems unavailable."
        )
        return

    # load configuration of custom menu
    project_settings = get_project_settings(get_current_project_name())
    config = project_settings["hiero"]["scriptsmenu"]["definition"]
    _menu = project_settings["hiero"]["scriptsmenu"]["name"]

    if not config:
        log.warning("Skipping studio menu, no definition found.")
        return

    # run the launcher for Hiero menu
    studio_menu = launchforhiero.main(title=_menu.title())

    # apply configuration
    studio_menu.build_from_configuration(studio_menu, config)
