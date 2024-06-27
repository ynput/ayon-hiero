import os
from pprint import pformat
import re
from copy import deepcopy
import uuid

import hiero

from qtpy import QtWidgets, QtCore
import qargparse

from ayon_core.settings import get_current_project_settings
from ayon_core.lib import Logger
from ayon_core.pipeline import LoaderPlugin
from ayon_core.pipeline.load import get_representation_path_from_context
from . import lib
from ayon_core.pipeline import Creator
from ayon_core.lib import BoolDef

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
    """A basic SequenceLoader for Resolve

    This will implement the basic behavior for a loader to inherit from that
    will containerize the reference and will implement the `remove` and
    `update` logic.

    """

    options = [
        qargparse.Boolean(
            "handles",
            label="Include handles",
            default=0,
            help="Load with handles or without?"
        ),
        qargparse.Choice(
            "load_to",
            label="Where to load clips",
            items=[
                "Current timeline",
                "New timeline"
            ],
            default="Current timeline",
            help="Where do you want clips to be loaded?"
        ),
        qargparse.Choice(
            "load_how",
            label="How to load clips",
            items=[
                "Original timing",
                "Sequentially in order"
            ],
            default="Original timing",
            help="Would you like to place it at original timing?"
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

    def __init__(self, cls, context, path, **options):
        """ Initialize object

        Arguments:
            cls (avalon.api.Loader): plugin object
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
        self.clip_name_template = options.get(
            "clipNameTemplate") or "{asset}_{subset}_{representation}"
        assert self._populate_data(), str(
            "Cannot Load selected data, look into database "
            "or call your supervisor")

        # inject folder data to representation dict
        folder_entity = self.context["folder"]
        self.data["folderAttributes"] = folder_entity["attrib"]
        log.info("__init__ self.data: `{}`".format(pformat(self.data)))
        log.info("__init__ options: `{}`".format(pformat(options)))

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

        if options.get("track"):
            # if multiselection is set then use options track
            self.active_track = options["track"]
        else:
            self.active_track = lib.get_current_track(
                self.active_sequence, self.data["track_name"])

    def _populate_data(self):
        """ Gets context and convert it to self.data
        data structure:
            {
                "name": "assetName_productName_representationName"
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
        slate_on = "slate" in self.context["version"]["data"].get(
            "families", [])
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


class HieroCreator(Creator):
    """Creator class wrapper
    """
    clip_color = "Purple"
    rename_index = None

    def apply_settings(self, project_settings):
        hiero_create_settings = (
            project_settings.get("hiero", {}).get("create")
        )
        self.presets = hiero_create_settings.get(
            self.__class__.__name__, {}
        )

    def create(self, subset_name, instance_data, pre_create_data):
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

        # TODO: Add a way to store/imprint data

    def get_pre_create_attr_defs(self):
        return [
            BoolDef("use_selection",
                    label="Use selection",
                    default=True)
        ]


class PublishClip:
    """
    Convert a track item to publishable instance

    Args:
        track_item (hiero.core.TrackItem): hiero track item object
        kwargs (optional): additional data needed for rename=True (presets)

    Returns:
        hiero.core.TrackItem: hiero track item object with pype tag
    """
    types = {
        "shot": "shot",
        "folder": "folder",
        "episode": "episode",
        "sequence": "sequence",
        "track": "sequence",
    }

    # parents search pattern
    parents_search_pattern = r"\{([a-z]*?)\}"

    # default templates for non-ui use
    rename_default = False
    hierarchy_default = "{_folder_}/{_sequence_}/{_track_}"
    clip_name_default = "shot_{_trackIndex_:0>3}_{_clipIndex_:0>4}"
    base_product_name_default = "<track_name>"
    review_track_default = "< none >"
    product_type_default = "plate"
    count_from_default = 10
    count_steps_default = 10
    vertical_sync_default = False
    driving_layer_default = ""

    # Define which keys of the pre create data should also be 'tag data'
    tag_keys = {
        # renameHierarchy
        "hierarchy",
        # hierarchyData
        "folder", "episode", "sequence", "track", "shot",
        # publish settings
        "audio", "sourceResolution",
        # shot attributes
        "workfileFrameStart", "handleStart", "handleEnd"
    }

    def __init__(
            self,
            track_item,
            pre_create_data=None,
            avalon=None,
            rename_index=0):

        self.rename_index = rename_index
        self.vertical_clip_match = dict()
        self.tag_data = dict()

        # adding ui inputs if any
        self.pre_create_data = pre_create_data or {}

        # get main parent objects
        self.track_item = track_item
        sequence_name = lib.get_current_sequence().name()
        self.sequence_name = str(sequence_name).replace(" ", "_")

        # track item (clip) main attributes
        self.ti_name = track_item.name()
        self.ti_index = int(track_item.eventNumber())

        # get track name and index
        track_name = track_item.parent().name()
        self.track_name = str(track_name).replace(" ", "_")
        self.track_index = int(track_item.parent().trackIndex())

        # adding tag.family into tag
        if avalon:
            self.tag_data.update(avalon)

        # add publish attribute to tag data
        self.tag_data.update({"publish": True})

        # populate default data before we get other attributes
        self._populate_track_item_default_data()

        # use all populated default data to create all important attributes
        self._populate_attributes()

        # create parents with correct types
        self._create_parents()

    def convert(self):

        # solve track item data and add them to tag data
        self._convert_to_tag_data()

        # if track name is in review track name and also if driving track name
        # is not in review track name: skip tag creation
        if (self.track_name in self.review_layer) and (
                self.driving_layer not in self.review_layer):
            return

        # deal with clip name
        new_name = self.tag_data.pop("newClipName")

        if self.rename:
            # rename track item
            self.track_item.setName(new_name)
            self.tag_data["asset"] = new_name
        else:
            self.tag_data["asset"] = self.ti_name
            self.tag_data["hierarchyData"]["shot"] = self.ti_name

        if self.tag_data["heroTrack"] and self.review_layer:
            self.tag_data.update({"reviewTrack": self.review_layer})
        else:
            self.tag_data.update({"reviewTrack": None})

        # create pype tag on track_item and add data
        lib.imprint(self.track_item, self.tag_data)

        return self.track_item

    def _populate_track_item_default_data(self):
        """ Populate default formatting data from track item. """

        self.track_item_default_data = {
            "_folder_": "shots",
            "_sequence_": self.sequence_name,
            "_track_": self.track_name,
            "_clip_": self.ti_name,
            "_trackIndex_": self.track_index,
            "_clipIndex_": self.ti_index
        }

    def _populate_attributes(self):
        """ Populate main object attributes. """
        # track item frame range and parent track name for vertical sync check
        self.clip_in = int(self.track_item.timelineIn())
        self.clip_out = int(self.track_item.timelineOut())

        # define ui inputs if non gui mode was used
        self.shot_num = self.ti_index
        log.debug(
            "____ self.shot_num: {}".format(self.shot_num))

       # publisher ui attribute inputs or default values if gui was not used
        def get(key):
            """Shorthand access for code readability"""
            return self.pre_create_data.get(key)

        # ui_inputs data or default values if gui was not used
        self.rename = self.pre_create_data.get("clipRename", self.rename_default)
        self.clip_name = get("clipName") or self.clip_name_default
        self.hierarchy = get("hierarchy") or self.hierarchy_default
        self.count_from = get("countFrom") or self.count_from_default
        self.count_steps = get("countSteps") or self.count_steps_default
        self.subset_name = get("subsetName") or self.subset_name_default
        self.subset_family = get("subsetFamily") or self.subset_family_default
        self.vertical_sync = get("vSyncOn") or self.vertical_sync_default
        self.driving_layer = get("vSyncTrack") or self.driving_layer_default
        self.review_track = get("reviewTrack") or self.review_track_default
        self.audio = get("audio") or False

        self.hierarchy_data = {
            key: get(key) or self.track_item_default_data[key]
            for key in ["folder", "episode", "sequence", "track", "shot"]
        }

        # build product name from layer name
        if self.base_product_name == "<track_name>":
            self.base_product_name = self.track_name

        # create product for publishing
        self.product_name = (
            self.product_type + self.base_product_name.capitalize()
        )

    def _replace_hash_to_expression(self, name, text):
        """ Replace hash with number in correct padding. """
        _spl = text.split("#")
        _len = (len(_spl) - 1)
        _repl = "{{{0}:0>{1}}}".format(name, _len)
        return text.replace(("#" * _len), _repl)

    def _convert_to_tag_data(self):
        """ Convert internal data to tag data.

        Populating the tag data into internal variable self.tag_data
        """
        # define vertical sync attributes
        hero_track = True
        self.review_layer = ""
        if self.vertical_sync:
            # check if track name is not in driving layer
            if self.track_name not in self.driving_layer:
                # if it is not then define vertical sync as None
                hero_track = False

        # increasing steps by index of rename iteration
        self.count_steps *= self.rename_index

        hierarchy_formatting_data = dict()
        _data = self.track_item_default_data.copy()
        if self.pre_create_data:

            # adding tag metadata from ui
            for _key, _value in self.pre_create_data.items():
                if _key in self.tag_keys:
                    self.tag_data[_key] = _value

            # driving layer is set as positive match
            if hero_track or self.vertical_sync:
                # mark review layer
                if self.review_track and (
                        self.review_track not in self.review_track_default):
                    # if review layer is defined and not the same as default
                    self.review_layer = self.review_track
                # shot num calculate
                if self.rename_index == 0:
                    self.shot_num = self.count_from
                else:
                    self.shot_num = self.count_from + self.count_steps

            # clip name sequence number
            _data.update({"shot": self.shot_num})

            # solve # in test to pythonic expression
            for _key, _value in self.hierarchy_data.items():
                if "#" not in _value:
                    continue
                self.hierarchy_data[_key] = self._replace_hash_to_expression(
                    _key, _value
                )

            # fill up pythonic expresisons in hierarchy data
            for _key, _value in self.hierarchy_data.items():
                hierarchy_formatting_data[_key] = _value.format(**_data)
        else:
            # if no gui mode then just pass default data
            hierarchy_formatting_data = self.hierarchy_data

        tag_hierarchy_data = self._solve_tag_hierarchy_data(
            hierarchy_formatting_data
        )

        tag_hierarchy_data.update({"heroTrack": True})
        if hero_track and self.vertical_sync:
            self.vertical_clip_match.update({
                (self.clip_in, self.clip_out): tag_hierarchy_data
            })

        if not hero_track and self.vertical_sync:
            # driving layer is set as negative match
            for (_in, _out), hero_data in self.vertical_clip_match.items():
                hero_data.update({"heroTrack": False})
                if _in == self.clip_in and _out == self.clip_out:
                    data_product_name = hero_data["productName"]
                    # add track index in case duplicity of names in hero data
                    if self.product_name in data_product_name:
                        hero_data["productName"] = self.product_name + str(
                            self.track_index)
                    # in case track name and product name is the same then add
                    if self.base_product_name == self.track_name:
                        hero_data["productName"] = self.product_name
                    # assign data to return hierarchy data to tag
                    tag_hierarchy_data = hero_data

        # add data to return data dict
        self.tag_data.update(tag_hierarchy_data)

        # add uuid to tag data
        self.tag_data["uuid"] = str(uuid.uuid4())

        # add review track only to hero track
        if hero_track and self.review_layer:
            self.tag_data.update({"reviewTrack": self.review_layer})
        else:
            self.tag_data.update({"reviewTrack": None})

    def _solve_tag_hierarchy_data(self, hierarchy_formatting_data):
        """ Solve tag data from hierarchy data and templates. """
        # fill up clip name and hierarchy keys
        hierarchy_filled = self.hierarchy.format(**hierarchy_formatting_data)
        clip_name_filled = self.clip_name.format(**hierarchy_formatting_data)

        # remove shot from hierarchy data: is not needed anymore
        hierarchy_formatting_data.pop("shot")

        return {
            "newClipName": clip_name_filled,
            "hierarchy": hierarchy_filled,
            "parents": self.parents,
            "hierarchyData": hierarchy_formatting_data,
            "productName": self.product_name,
            "productType": self.product_type,
            "families": [self.product_type, self.data["productType"]]
        }

    def _convert_to_entity(self, src_type, template):
        """ Converting input key to key with type. """
        # convert to entity type
        folder_type = self.types.get(src_type, None)

        assert folder_type, "Missing folder type for `{}`".format(
            src_type
        )
        formatting_data = {}
        for _k, _v in self.hierarchy_data.items():
            value = _v["value"].format(
                **self.track_item_default_data)
            formatting_data[_k] = value

        return {
            "entity_type": folder_type,
            "folder_type": folder_type,
            "entity_name": template.format(**formatting_data)
        }

    def _create_parents(self):
        """ Create parents and return it in list. """
        self.parents = []

        pattern = re.compile(self.parents_search_pattern)

        par_split = [(pattern.findall(t).pop(), t)
                     for t in self.hierarchy.split("/")]

        for type, template in par_split:
            parent = self._convert_to_entity(type, template)
            self.parents.append(parent)