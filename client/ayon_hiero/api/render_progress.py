"""Progress dialog of the renders of a publish.

The dialog is application modal: the timeline and the publisher can not be
changed while a clip renders, but they keep painting. It implements
`rendering.RenderProgress`, so it is passed to `render_track_item`.
"""

import time
from typing import Optional

from qtpy import QtCore, QtWidgets


def has_gui() -> bool:
    """Whether Hiero runs with its UI, so a dialog can be shown."""
    return isinstance(
        QtWidgets.QApplication.instance(), QtWidgets.QApplication
    )


def _format_seconds(seconds: float) -> str:
    minutes, seconds = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class RenderProgressDialog(QtWidgets.QDialog):
    """Shows which clip and output renders and how far the publish is.

    Args:
        clip_count: Clips the publish renders.
        output_count: Outputs of all those clips.
        parent: Window to center on, the active one by default.
    """

    def __init__(
        self,
        clip_count: int,
        output_count: int,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent or QtWidgets.QApplication.activeWindow())
        self.setWindowTitle("Rendering product resources")
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setMinimumWidth(460)

        self._clip_count = max(1, clip_count)
        self._output_count = max(1, output_count)
        self._outputs_done = 0
        self._output_started = time.time()
        self._cancelled = False

        self._clip_label = QtWidgets.QLabel(self)
        self._output_label = QtWidgets.QLabel(self)
        self._frames_label = QtWidgets.QLabel(self)
        self._output_bar = QtWidgets.QProgressBar(self)
        self._output_bar.setRange(0, 1000)
        self._total_label = QtWidgets.QLabel(self)
        self._total_bar = QtWidgets.QProgressBar(self)
        self._total_bar.setRange(0, 1000)
        self._cancel_button = QtWidgets.QPushButton("Cancel", self)
        self._cancel_button.clicked.connect(self.cancel)

        for label in (self._clip_label, self._output_label):
            label.setTextFormat(QtCore.Qt.PlainText)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._cancel_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._clip_label)
        layout.addWidget(self._output_label)
        layout.addWidget(self._output_bar)
        layout.addWidget(self._frames_label)
        layout.addSpacing(8)
        layout.addWidget(self._total_label)
        layout.addWidget(self._total_bar)
        layout.addLayout(buttons)

    def start_output(
        self,
        clip_index: int,
        clip_name: str,
        output_index: int,
        output_total: int,
        output_name: str,
        outputs_done: int,
    ):
        """Show the output that starts rendering.

        Args:
            clip_index: Position of the clip, from 1.
            clip_name: Name of the clip, e.g. its track item and product.
            output_index: Position of the output in the clip's, from 1.
            output_total: Outputs of the clip.
            output_name: Name of the output, e.g. its representation.
            outputs_done: Outputs of the publish rendered before this one.
        """
        self._outputs_done = outputs_done
        self._output_started = time.time()
        self._clip_label.setText(
            f"Clip {clip_index} of {self._clip_count}: {clip_name}"
        )
        self._output_label.setText(
            f"Output {output_index} of {output_total}: {output_name}"
        )
        self.set_progress(0.0, 0)
        if not self.isVisible():
            self.show()
        self.raise_()

    def set_progress(self, progress: float, frame_count: int) -> None:
        """Show the rendered part of the current output, 0 to 1."""
        progress = max(0.0, min(1.0, progress))
        elapsed = time.time() - self._output_started
        if progress <= 0:
            frames = "Starting the render…"
        else:
            frames = (
                f"Frame {round(progress * frame_count)} of {frame_count}"
                f" · {_format_seconds(elapsed)} elapsed"
            )
            if progress < 1:
                left = elapsed * (1 - progress) / progress
                frames += f" · about {_format_seconds(left)} left"
        if self._cancelled:
            frames = "Cancelling…"
        self._frames_label.setText(frames)
        self._output_bar.setValue(int(progress * 1000))

        total = (self._outputs_done + progress) / self._output_count
        self._total_label.setText(
            f"Publish: {self._outputs_done} of {self._output_count}"
            " outputs rendered"
        )
        self._total_bar.setValue(int(total * 1000))

    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self):
        self._cancelled = True
        self._cancel_button.setEnabled(False)
        self._frames_label.setText("Cancelling…")

    def reject(self):
        # Escape and the close button cancel the render, the dialog closes
        # once the render has stopped
        self.cancel()

    def closeEvent(self, event):
        event.ignore()
        self.cancel()

    def finish(self):
        """Hide the dialog when the renders are done or failed."""
        self.hide()
        self.deleteLater()
