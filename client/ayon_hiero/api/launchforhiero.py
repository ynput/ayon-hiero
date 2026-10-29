import logging

import hiero.ui
from scriptsmenu import scriptsmenu


log = logging.getLogger(__name__)


def _hiero_main_menubar():
    """Retrieve the main menubar of Hiero

    On macOS (Hiero 17) the main window's `menuBar()` is not the menubar that
    `hiero.ui.menuBar()` returns and the AYON menu lives in, so a menu added
    to the first ended up next to the AYON menu in the native menubar.
    """
    return hiero.ui.menuBar()


def find_scripts_menu(title, parent):
    """
    Check if the menu exists with the given title in the parent

    Args:
        title (str): the title name of the scripts menu

        parent (QtWidgets.QMenuBar): the menubar to check

    Returns:
        QtWidgets.QMenu or None

    """

    menu = None
    search = [i for i in parent.children() if
              isinstance(i, scriptsmenu.ScriptsMenu)
              and i.title() == title]
    if search:
        assert len(search) < 2, ("Multiple instances of menu '{}' "
                                 "in menu bar".format(title))
        menu = search[0]

    return menu


def main(title="Scripts", parent=None, objectName=None):
    """Build the main scripts menu in Hiero

    Args:
        title (str): name of the menu in the application

        parent (QtWidgets.QtMenuBar): the parent object for the menu

        objectName (str): custom objectName for scripts menu

    Returns:
        scriptsmenu.ScriptsMenu instance

    """
    hieromainbar = parent or _hiero_main_menubar()
    try:
        # check menu already exists
        menu = find_scripts_menu(title, hieromainbar)
        if not menu:
            log.info("Attempting to build menu ...")
            object_name = objectName or title.lower()
            menu = scriptsmenu.ScriptsMenu(title=title,
                                           parent=hieromainbar,
                                           objectName=object_name)
    except Exception as e:
        log.error(e)
        return

    return menu
