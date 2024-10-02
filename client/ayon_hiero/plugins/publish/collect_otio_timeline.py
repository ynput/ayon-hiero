import os

import pyblish.api

from ayon_core.pipeline import registered_host

from ayon_hiero.api import lib
from ayon_hiero.api.otio import hiero_export

import hiero


class CollectOTIOTimeline(pyblish.api.ContextPlugin):
    """Inject the otio timeline"""

    label = "Collect OTIO Timeline"
    hosts = ["hiero"]
    order = pyblish.api.CollectorOrder - 0.491

    def process(self, context):
        host = registered_host()
        current_file = host.get_current_workfile()

        otio_timeline = hiero_export.create_otio_timeline()

        active_timeline = hiero.ui.activeSequence()
        project = active_timeline.project()
        fps = active_timeline.framerate().toFloat()

        all_tracks = active_timeline.videoTracks()
        tracks_effect_items = self.collect_sub_track_items(all_tracks)

        context_data = {
            "activeProject": project,
            "activeTimeline": active_timeline,
            "currentFile": current_file,
            "otioTimeline": otio_timeline,
            "colorspace": self.get_colorspace(project),
            "fps": fps,
            "tracksEffectItems": tracks_effect_items,
        }
        context.data.update(context_data)

    def get_colorspace(self, project):
        # get workfile's colorspace properties
        return {
            "useOCIOEnvironmentOverride": project.useOCIOEnvironmentOverride(),
            "lutSetting16Bit": project.lutSetting16Bit(),
            "lutSetting8Bit": project.lutSetting8Bit(),
            "lutSettingFloat": project.lutSettingFloat(),
            "lutSettingLog": project.lutSettingLog(),
            "lutSettingViewer": project.lutSettingViewer(),
            "lutSettingWorkingSpace": project.lutSettingWorkingSpace(),
            "lutUseOCIOForExport": project.lutUseOCIOForExport(),
            "ocioConfigName": project.ocioConfigName(),
            "ocioConfigPath": project.ocioConfigPath()
        }

    @staticmethod
    def collect_sub_track_items(tracks):
        """
        Args:
            tracks (list): All of the video tracks.

        Returns:
            dict. Track index as key and list of subtracks
        """
        # collect all subtrack items
        sub_track_items = {}
        for track in tracks:
            effect_items = track.subTrackItems()

            # skip if no clips on track > need track with effect only
            if not effect_items:
                continue

            # skip all disabled tracks
            if not track.isEnabled():
                continue

            track_index = track.trackIndex()
            _sub_track_items = lib.flatten(effect_items)

            _sub_track_items = list(_sub_track_items)
            # continue only if any subtrack items are collected
            if not _sub_track_items:
                continue

            enabled_sti = []
            # loop all found subtrack items and check if they are enabled
            for _sti in _sub_track_items:
                # checking if not enabled
                if not _sti.isEnabled():
                    continue
                if isinstance(_sti, hiero.core.Annotation):
                    continue
                # collect the subtrack item
                enabled_sti.append(_sti)

            # continue only if any subtrack items are collected
            if not enabled_sti:
                continue

            # add collection of subtrackitems to dict
            sub_track_items[track_index] = enabled_sti

        return sub_track_items
