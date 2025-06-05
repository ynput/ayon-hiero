# nukeStyleKeyboardShortcuts, v1, 30/07/2012, Ant Nasce.
# A few Nuke-Style File menu shortcuts for those whose muscle memory has set in...
# Usage: Copy this file to ~/.hiero/Python/StartupUI/

import hiero.ui
from qtpy.QtGui import QKeySequence

#----------------------------------------------
a = hiero.ui.findMenuAction('Import File(s)...')
# Note: You probably best to make this 'Ctrl+R' - currently conflicts with "Red" in the Viewer!
a.setShortcut(QKeySequence("R"))
#----------------------------------------------
a = hiero.ui.findMenuAction('Import Folder(s)...')
a.setShortcut(QKeySequence('Shift+R'))
#----------------------------------------------
a = hiero.ui.findMenuAction("Import EDL/XML/AAF...")
a.setShortcut(QKeySequence('Ctrl+Shift+O'))
#----------------------------------------------
a = hiero.ui.findMenuAction("Metadata View")
a.setShortcut(QKeySequence("I"))
#----------------------------------------------
a = hiero.ui.findMenuAction("Edit Settings")
a.setShortcut(QKeySequence("S"))
#----------------------------------------------
a = hiero.ui.findMenuAction("Monitor Output")
if a:
    a.setShortcut(QKeySequence('Ctrl+U'))
#----------------------------------------------
