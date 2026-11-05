import os
import re

import hiero

from qtpy import QtWidgets, QtCore

from ayon_core.lib import Logger, BoolDef, EnumDef
from ayon_core.pipeline import (
    Creator,
    HiddenCreator,
    LoaderPlugin,
)
from ayon_core.pipeline.load import get_representation_path_from_context

from ayon_editorial.shots.clip import ClipInfo
from ayon_editorial.shots.hierarchy import sanitize_name

from . import lib


log = Logger.get_logger(__name__)


def load_stylesheet():
    path = os.path.join(os.path.dirname(__file__), "style.css")
    if not os.path.exists(path):
        log.warning("Unable to load stylesheet, file not found in resources")
        return ""

    with open(path, "r") as file_stream:
        stylesheet = file_stream.read()
    return stylesheet


class CreatorWidget(QtWidgets.QDialog):

    # output items
    items = {}

    def __init__(self, name, info, ui_inputs, parent=None):
        super(CreatorWidget, self).__init__(parent)

        self.setObjectName(name)

        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.CustomizeWindowHint
            | QtCore.Qt.WindowTitleHint
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowStaysOnTopHint
        )
        self.setWindowTitle(name or "AYON Creator Input")
        self.resize(500, 700)

        # Where inputs and labels are set
        self.content_widget = [QtWidgets.QWidget(self)]
        top_layout = QtWidgets.QFormLayout(self.content_widget[0])
        top_layout.setObjectName("ContentLayout")
        top_layout.addWidget(Spacer(5, self))

        # first add widget tag line
        top_layout.addWidget(QtWidgets.QLabel(info))

        # main dynamic layout
        self.scroll_area = QtWidgets.QScrollArea(self, widgetResizable=True)
        self.scroll_area.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)

        self.content_widget.append(self.scroll_area)

        scroll_widget = QtWidgets.QWidget(self)
        in_scroll_area = QtWidgets.QVBoxLayout(scroll_widget)
        self.content_layout = [in_scroll_area]

        # add preset data into input widget layout
        self.items = self.populate_widgets(ui_inputs)
        self.scroll_area.setWidget(scroll_widget)

        # Confirmation buttons
        btns_widget = QtWidgets.QWidget(self)
        btns_layout = QtWidgets.QHBoxLayout(btns_widget)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        btns_layout.addWidget(cancel_btn)

        ok_btn = QtWidgets.QPushButton("Ok")
        btns_layout.addWidget(ok_btn)

        # Main layout of the dialog
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)

        # adding content widget
        for w in self.content_widget:
            main_layout.addWidget(w)

        main_layout.addWidget(btns_widget)

        ok_btn.clicked.connect(self._on_ok_clicked)
        cancel_btn.clicked.connect(self._on_cancel_clicked)

        stylesheet = load_stylesheet()
        self.setStyleSheet(stylesheet)

    def _on_ok_clicked(self):
        self.result = self.value(self.items)
        self.close()

    def _on_cancel_clicked(self):
        self.result = None
        self.close()

    def value(self, data, new_data=None):
        new_data = new_data or dict()
        for k, v in data.items():
            new_data[k] = {
                "target": None,
                "value": None
            }
            if v["type"] == "dict":
                new_data[k]["target"] = v["target"]
                new_data[k]["value"] = self.value(v["value"])
            if v["type"] == "section":
                new_data.pop(k)
                new_data = self.value(v["value"], new_data)
            elif getattr(v["value"], "currentText", None):
                new_data[k]["target"] = v["target"]
                new_data[k]["value"] = v["value"].currentText()
            elif getattr(v["value"], "isChecked", None):
                new_data[k]["target"] = v["target"]
                new_data[k]["value"] = v["value"].isChecked()
            elif getattr(v["value"], "value", None):
                new_data[k]["target"] = v["target"]
                new_data[k]["value"] = v["value"].value()
            elif getattr(v["value"], "text", None):
                new_data[k]["target"] = v["target"]
                new_data[k]["value"] = v["value"].text()

        return new_data

    def camel_case_split(self, text):
        matches = re.finditer(
            '.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', text)
        return " ".join([str(m.group(0)).capitalize() for m in matches])

    def create_row(self, layout, type, text, **kwargs):
        value_keys = ["setText", "setCheckState", "setValue", "setChecked"]

        # get type attribute from qwidgets
        attr = getattr(QtWidgets, type)

        # convert label text to normal capitalized text with spaces
        label_text = self.camel_case_split(text)

        # assign the new text to label widget
        label = QtWidgets.QLabel(label_text)
        label.setObjectName("LineLabel")

        # create attribute name text strip of spaces
        attr_name = text.replace(" ", "")

        # create attribute and assign default values
        setattr(
            self,
            attr_name,
            attr(parent=self))

        # assign the created attribute to variable
        item = getattr(self, attr_name)

        # set attributes to item which are not values
        for func, val in kwargs.items():
            if func in value_keys:
                continue

            if getattr(item, func):
                log.debug("Setting {} to {}".format(func, val))
                func_attr = getattr(item, func)
                if isinstance(val, tuple):
                    func_attr(*val)
                else:
                    func_attr(val)

        # set values to item
        for value_item in value_keys:
            if value_item not in kwargs:
                continue
            if getattr(item, value_item):
                getattr(item, value_item)(kwargs[value_item])

        # add to layout
        layout.addRow(label, item)

        return item

    def populate_widgets(self, data, content_layout=None):
        """
        Populate widget from input dict.

        Each plugin has its own set of widget rows defined in dictionary
        each row values should have following keys: `type`, `target`,
        `label`, `order`, `value` and optionally also `toolTip`.

        Args:
            data (dict): widget rows or organized groups defined
                         by types `dict` or `section`
            content_layout (QtWidgets.QFormLayout)[optional]: used when nesting

        Returns:
            dict: redefined data dict updated with created widgets

        """

        content_layout = content_layout or self.content_layout[-1]
        # fix order of process by defined order value
        ordered_keys = list(data.keys())
        for k, v in data.items():
            try:
                # try removing a key from index which should
                # be filled with new
                ordered_keys.pop(v["order"])
            except IndexError:
                pass
            # add key into correct order
            ordered_keys.insert(v["order"], k)

        # process ordered
        for k in ordered_keys:
            v = data[k]
            tool_tip = v.get("toolTip", "")
            if v["type"] == "dict":
                # adding spacer between sections
                self.content_layout.append(QtWidgets.QWidget(self))
                content_layout.addWidget(self.content_layout[-1])
                self.content_layout[-1].setObjectName("sectionHeadline")

                headline = QtWidgets.QVBoxLayout(self.content_layout[-1])
                headline.addWidget(Spacer(20, self))
                headline.addWidget(QtWidgets.QLabel(v["label"]))

                # adding nested layout with label
                self.content_layout.append(QtWidgets.QWidget(self))
                self.content_layout[-1].setObjectName("sectionContent")

                nested_content_layout = QtWidgets.QFormLayout(
                    self.content_layout[-1])
                nested_content_layout.setObjectName("NestedContentLayout")
                content_layout.addWidget(self.content_layout[-1])

                # add nested key as label
                data[k]["value"] = self.populate_widgets(
                    v["value"], nested_content_layout)

            if v["type"] == "section":
                # adding spacer between sections
                self.content_layout.append(QtWidgets.QWidget(self))
                content_layout.addWidget(self.content_layout[-1])
                self.content_layout[-1].setObjectName("sectionHeadline")

                headline = QtWidgets.QVBoxLayout(self.content_layout[-1])
                headline.addWidget(Spacer(20, self))
                headline.addWidget(QtWidgets.QLabel(v["label"]))

                # adding nested layout with label
                self.content_layout.append(QtWidgets.QWidget(self))
                self.content_layout[-1].setObjectName("sectionContent")

                nested_content_layout = QtWidgets.QFormLayout(
                    self.content_layout[-1])
                nested_content_layout.setObjectName("NestedContentLayout")
                content_layout.addWidget(self.content_layout[-1])

                # add nested key as label
                data[k]["value"] = self.populate_widgets(
                    v["value"], nested_content_layout)

            elif v["type"] == "QLineEdit":
                data[k]["value"] = self.create_row(
                    content_layout, "QLineEdit", v["label"],
                    setText=v["value"], setToolTip=tool_tip)
            elif v["type"] == "QComboBox":
                data[k]["value"] = self.create_row(
                    content_layout, "QComboBox", v["label"],
                    addItems=v["value"], setToolTip=tool_tip)
            elif v["type"] == "QCheckBox":
                data[k]["value"] = self.create_row(
                    content_layout, "QCheckBox", v["label"],
                    setChecked=v["value"], setToolTip=tool_tip)
            elif v["type"] == "QSpinBox":
                data[k]["value"] = self.create_row(
                    content_layout, "QSpinBox", v["label"],
                    setValue=v["value"],
                    setDisplayIntegerBase=10000,
                    setRange=(0, 99999), setMinimum=0,
                    setMaximum=100000, setToolTip=tool_tip)

        return data


class Spacer(QtWidgets.QWidget):
    def __init__(self, height, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        self.setFixedHeight(height)

        real_spacer = QtWidgets.QWidget(self)
        real_spacer.setObjectName("Spacer")
        real_spacer.setFixedHeight(height)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(real_spacer)

        self.setLayout(layout)


class SequenceLoader(LoaderPlugin):
    """A basic SequenceLoader for Hiero

    This will implement the basic behavior for a loader to inherit from that
    will containerize the reference and will implement the `remove` and
    `update` logic.

    """

    options = [
        BoolDef(
            "handles",
            label="Include handles",
            default=False,
            tooltip="Load with handles or without?"
        ),
        EnumDef(
            "load_to",
            label="Where to load clips",
            items=[
                "Current timeline",
                "New timeline"
            ],
            default="Current timeline",
            tooltip="Where do you want clips to be loaded?"
        ),
        EnumDef(
            "load_how",
            label="How to load clips",
            items=[
                "Original timing",
                "Sequentially in order"
            ],
            default="Original timing",
            tooltip="Would you like to place it at original timing?"
        )
    ]

    def load(
        self,
        context,
        name=None,
        namespace=None,
        options=None
    ):
        pass

    def update(self, container, context):
        """Update an existing `container`
        """
        pass

    def remove(self, container):
        """Remove an existing `container`
        """
        pass


class ClipLoader:

    active_bin = None
    data = dict()
    active_track = None

    def __init__(self, cls, context, path, **options):
        """ Initialize object

        Arguments:
            cls (ayon_core.api.Loader): plugin object
            context (dict): loader plugin context
            options (dict)[optional]: possible keys:
                projectBinPath: "path/to/binItem"

        """
        self.__dict__.update(cls.__dict__)
        self.context = context
        self.active_project = lib.get_current_project()
        self.fname = path

        # try to get value from options or evaluate key value for `handles`
        self.with_handles = options.get("handles") or bool(
            options.get("handles") is True)
        # try to get value from options or evaluate key value for `load_how`
        self.sequencial_load = options.get("sequentially") or bool(
            "Sequentially in order" in options.get("load_how", ""))
        # try to get value from options or evaluate key value for `load_to`
        self.new_sequence = options.get("newSequence") or bool(
            "New timeline" in options.get("load_to", ""))
        self.clip_name_template = (
            options.get("clipNameTemplate")
            or "{folder[name]}_{product[name]}_{representation}"
        )
        assert self._populate_data(), str(
            "Cannot Load selected data, look into database "
            "or call your supervisor")

        # inject folder data to representation dict
        folder_entity = self.context["folder"]
        self.data["folderAttributes"] = folder_entity["attrib"]

        # add active components to class
        if self.new_sequence:
            if options.get("sequence"):
                # if multiselection is set then use options sequence
                self.active_sequence = options["sequence"]
            else:
                # create new sequence
                self.active_sequence = lib.get_current_sequence(new=True)
                self.active_sequence.setFramerate(
                    hiero.core.TimeBase.fromString(
                        str(self.data["folderAttributes"]["fps"])))
        else:
            self.active_sequence = lib.get_current_sequence()

        # check if track already exists
        matching_track = None
        for _track in self.active_sequence.videoTracks():
            if _track.name() == self.data["track_name"]:
                matching_track = _track

        # if multiselection is set then use options track
        # in case it is existing track
        if options.get("track") and matching_track:
            self.active_track = matching_track
        else:
            self.active_track = lib.get_current_track(
                self.active_sequence, self.data["track_name"])

    def _populate_data(self):
        """ Gets context and convert it to self.data
        data structure:
            {
                "name": "folderName_productName_representationName"
                "path": "path/to/file/created/by/get_repr..",
                "binPath": "projectBinPath",
            }
        """
        # create name
        repr = self.context["representation"]
        repr_cntx = repr["context"]
        folder_path = self.context["folder"]["path"]
        product_name = self.context["product"]["name"]
        representation = repr["name"]
        self.data["clip_name"] = self.clip_name_template.format(**repr_cntx)
        self.data["track_name"] = "_".join([product_name, representation])
        self.data["versionAttributes"] = self.context["version"]["attrib"]
        # gets file path
        file = get_representation_path_from_context(self.context)
        if not file:
            repr_id = repr["id"]
            log.warning(
                "Representation id `{}` is failing to load".format(repr_id))
            return None
        self.data["path"] = file.replace("\\", "/")

        # convert to hashed path
        if repr_cntx.get("frame"):
            self._fix_path_hashes()

        # solve project bin structure path
        hierarchy = "Loader{}".format(folder_path)

        self.data["binPath"] = hierarchy

        return True

    def _fix_path_hashes(self):
        """ Convert file path where it is needed padding with hashes
        """
        file = self.data["path"]
        if "#" not in file:
            frame = self.context["representation"]["context"].get("frame")
            padding = len(frame)
            file = file.replace(frame, "#" * padding)
        self.data["path"] = file

    def _make_track_item(self, source_bin_item, audio=False):
        """ Create track item with """

        clip = source_bin_item.activeItem()

        # add to track as clip item
        if not audio:
            track_item = hiero.core.TrackItem(
                self.data["clip_name"], hiero.core.TrackItem.kVideo)
        else:
            track_item = hiero.core.TrackItem(
                self.data["clip_name"], hiero.core.TrackItem.kAudio)

        track_item.setSource(clip)
        track_item.setSourceIn(self.handle_start)
        track_item.setTimelineIn(self.timeline_in)
        track_item.setSourceOut((self.media_duration) - self.handle_end)
        track_item.setTimelineOut(self.timeline_out)
        track_item.setPlaybackSpeed(1)
        self.active_track.addTrackItem(track_item)

        return track_item

    def load(self):
        # create project bin for the media to be imported into
        self.active_bin = lib.create_bin(self.data["binPath"])

        # create mediaItem in active project bin
        # create clip media
        self.media = hiero.core.MediaSource(self.data["path"])
        self.media_duration = int(self.media.duration())

        # get handles
        version_attributes = self.data["versionAttributes"]
        self.handle_start = version_attributes.get("handleStart")
        self.handle_end = version_attributes.get("handleEnd")
        if self.handle_start is None:
            self.handle_start = self.data["folderAttributes"]["handleStart"]
        if self.handle_end is None:
            self.handle_end = self.data["folderAttributes"]["handleEnd"]

        self.handle_start = int(self.handle_start)
        self.handle_end = int(self.handle_end)

        if self.sequencial_load:
            last_track_item = lib.get_track_items(
                sequence_name=self.active_sequence.name(),
                track_name=self.active_track.name()
            )
            if len(last_track_item) == 0:
                last_timeline_out = 0
            else:
                last_track_item = last_track_item[-1]
                last_timeline_out = int(last_track_item.timelineOut()) + 1
            self.timeline_in = last_timeline_out
            self.timeline_out = last_timeline_out + int(
                self.data["folderAttributes"]["clipOut"]
                - self.data["folderAttributes"]["clipIn"])
        else:
            self.timeline_in = int(self.data["folderAttributes"]["clipIn"])
            self.timeline_out = int(self.data["folderAttributes"]["clipOut"])

        log.debug("__ self.timeline_in: {}".format(self.timeline_in))
        log.debug("__ self.timeline_out: {}".format(self.timeline_out))

        # check if slate is included
        slate_on = "slate" in version_attributes.get("families", [])
        log.debug("__ slate_on: {}".format(slate_on))

        # if slate is on then remove the slate frame from beginning
        if slate_on:
            self.media_duration -= 1
            self.handle_start += 1

        # create Clip from Media
        clip = hiero.core.Clip(self.media)
        clip.setName(self.data["clip_name"])

        # add Clip to bin if not there yet
        if self.data["clip_name"] not in [
                b.name() for b in self.active_bin.items()]:
            bin_item = hiero.core.BinItem(clip)
            self.active_bin.addItem(bin_item)

        # just make sure the clip is created
        # there were some cases were hiero was not creating it
        source_bin_item = None
        for item in self.active_bin.items():
            if self.data["clip_name"] == item.name():
                source_bin_item = item
        if not source_bin_item:
            log.warning("Problem with created Source clip: `{}`".format(
                self.data["clip_name"]))

        # include handles
        if self.with_handles:
            self.timeline_in -= self.handle_start
            self.timeline_out += self.handle_end
            self.handle_start = 0
            self.handle_end = 0

        # make track item from source in bin as item
        track_item = self._make_track_item(source_bin_item)

        log.info("Loading clips: `{}`".format(self.data["clip_name"]))
        return track_item


class HiddenHieroCreator(HiddenCreator):
    """HiddenCreator class wrapper
    """
    settings_category = "hiero"
    skip_discovery = True

    def collect_instances(self):
        pass

    def update_instances(self, update_list):
        pass

    def remove_instances(self, instances):
        pass


class HieroCreator(Creator):
    """Creator class wrapper
    """
    settings_category = "hiero"
    skip_discovery = True

    def create(self, product_name, instance_data, pre_create_data):
        """Prepare data for new instance creation.

        Args:
            product_name(str): Product name of created instance.
            instance_data(dict): Base data for instance.
            pre_create_data(dict): Data based on pre creation attributes.
                Those may affect how creator works.
        """
        # adding basic current context resolve objects
        self.project = lib.get_current_project()
        self.sequence = lib.get_current_sequence()

        if pre_create_data.get("use_selection", False):
            timeline_selection = lib.get_timeline_selection()
            self.selected = lib.get_track_items(
                selection=timeline_selection
            )
        else:
            self.selected = lib.get_track_items()


def clip_info_from_track_item(track_item, sequence) -> ClipInfo:
    """Read a track item into the plain clip data of the shot solver.

    Args:
        track_item (hiero.core.TrackItem): The clip.
        sequence (hiero.core.Sequence): The sequence the clip is on.

    Returns:
        ClipInfo: Clip data. Clip and sequence names are sanitised with
            Hiero's rule (`[ -.,]` to `_`), the track name is raw (the
            solver cleans it).
    """
    track = track_item.parent()
    return ClipInfo(
        uid=track_item.guid(),
        name=sanitize_name(track_item.name()),
        index=int(track_item.eventNumber()),
        track_name=track.name(),
        track_index=int(track.trackIndex()),
        sequence_name=sanitize_name(sequence.name()),
        timeline_in=int(track_item.timelineIn()),
        timeline_out=int(track_item.timelineOut()),
        source_in=track_item.sourceIn(),
        source_out=track_item.sourceOut(),
    )
