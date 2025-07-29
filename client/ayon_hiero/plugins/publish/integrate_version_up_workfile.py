import os

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
        path = context.data["currentFile"]
        try:
            from ayon_core.pipeline.workfile import save_next_version
            from ayon_core.host.interfaces import SaveWorkfileOptionalData

            current_filename = os.path.basename(path)
            save_next_version(
                description=(
                    f"Incremented by publishing from {current_filename}"
                ),
                # Optimize the save by reducing needed queries for context
                prepared_data=SaveWorkfileOptionalData(
                    project_entity=context.data["projectEntity"],
                    project_settings=context.data["project_settings"],
                    anatomy=context.data["anatomy"],
                )
            )
        except ImportError:
            # Backwards compatibility before ayon-core 1.5.0
            new_path = version_up(path)

            if project:
                project.saveAs(new_path)

        self.log.info("Project workfile was versioned up")
