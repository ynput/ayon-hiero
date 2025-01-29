from pyblish import api

from ayon_core.lib import version_up
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
)


class IntegrateVersionUpWorkfile(api.ContextPlugin,
                                 OptionalPyblishPluginMixin):
    """Save as new workfile version"""

    order = api.IntegratorOrder + 10.1
    label = "Version-up Workfile"
    hosts = ["hiero"]

    optional = True
    active = True

    def process(self, context):
        if not self.is_active(context.data):
            self.log.debug("Project workfile version up was skipped")
            return

        project = context.data["activeProject"]
        path = context.data.get("currentFile")
        new_path = version_up(path)

        if project:
            project.saveAs(new_path)

        self.log.info("Project workfile was versioned up")
