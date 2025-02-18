import re

import pyblish.api


class CollectClipEffects(pyblish.api.InstancePlugin):
    """Collect soft effects instances."""

    order = pyblish.api.CollectorOrder - 0.078
    label = "Collect Clip Effects Instances"
    families = ["clip"]
    settings_category = "hiero"

    effect_categories = []
    effect_tracks = []

    def process(self, instance):
        product_type = "effect"
        effects = {}
        review = instance.data.get("review")
        review_track_index = instance.context.data.get("reviewTrackIndex")
        item = instance.data["item"]
        product_name = instance.data.get("productName")

        if not instance.data["creator_attributes"]["publish_effects"]:
            self.log.debug(
                "Effects collection/publish is disabled for %s",
                product_name,
            )
            return

        if "audio" in instance.data["productType"]:
            return

        # frame range
        self.handle_start = instance.data["handleStart"]
        self.handle_end = instance.data["handleEnd"]
        self.clip_in = int(item.timelineIn())
        self.clip_out = int(item.timelineOut())
        self.clip_in_h = self.clip_in - self.handle_start
        self.clip_out_h = self.clip_out + self.handle_end

        track_item = instance.data["item"]
        track = track_item.parent()
        track_index = track.trackIndex()
        tracks_effect_items = instance.context.data.get("tracksEffectItems")
        clip_effect_items = instance.data.get("clipEffectItems")

        # add clips effects to track's:
        if clip_effect_items:
            tracks_effect_items[track_index] = clip_effect_items

        # process all effects and divide them to instance
        for _track_index, sub_track_items in tracks_effect_items.items():
            # skip if track index is the same as review track index
            if review and review_track_index == _track_index:
                continue
            for sitem in sub_track_items:
                # make sure this subtrack item is relative of track item
                if ((track_item not in sitem.linkedItems())
                        and (len(sitem.linkedItems()) > 0)):
                    continue

                if not (track_index <= _track_index):
                    continue

                effect = self.add_effect(_track_index, sitem)
                if effect:
                    effects.update(effect)

        # skip any without effects
        if not effects:
            return

        effects.update({"assignTo": product_name})

        product_name_split = re.findall(r'[A-Z][^A-Z]*', product_name)

        if len(product_name_split) > 0:
            root_name = product_name.replace(product_name_split[0], "")
            product_name_split.insert(0, root_name.capitalize())

        product_name_split.insert(0, "effect")

        # Categorize effects by class.
        effect_categories = {
            x["name"]: x["effect_classes"] for x in self.effect_categories
        }

        category_by_effect = {"": ""}
        for key, values in effect_categories.items():
            for cls in values:
                category_by_effect[cls] = key

        effects_categorized = {k: {} for k in effect_categories.keys()}
        for key, value in effects.items():
            if key == "assignTo":
                continue

            # Some classes can have a number in them. Like Text2.
            found_cls = ""
            for cls in category_by_effect.keys():
                if cls in value["class"]:
                    found_cls = cls

            if not found_cls:
                continue

            effects_categorized[category_by_effect[found_cls]][key] = value

        # Categorize effects by track name.
        track_names_by_category = {
            x["name"]: x["track_names"] for x in self.effect_tracks
        }
        for category, track_names in track_names_by_category.items():
            for key, value in effects.items():
                if key == "assignTo":
                    continue

                if value["track"] not in track_names:
                    continue

                if category in effects_categorized:
                    effects_categorized[category][key] = value
                else:
                    effects_categorized[category] = {key: value}

        # Ensure required `assignTo` data member exists.
        categories = list(effects_categorized.keys())
        for category in categories:
            if not effects_categorized[category]:
                effects_categorized.pop(category)
                continue

            effects_categorized[category]["assignTo"] = effects["assignTo"]

        # If no effects have been categorized, publish all effects together.
        if not effects_categorized:
            effects_categorized[""] = effects

        for category, effects in effects_categorized.items():
            product_name = "".join(product_name_split)
            product_name += category.capitalize()

            # create new instance and inherit data
            data = {}
            for key, value in instance.data.items():
                if "clipEffectItems" in key:
                    continue
                data[key] = value

            data.update({
                "productName": product_name,
                "productType": product_type,
                "family": product_type,
                "families": [product_type],
                "name": product_name + "_" + data["folderPath"],
                "label": "{} - {}".format(
                    data["folderPath"], product_name
                ),
                "effects": effects,
            })

            # create new instance
            _instance = instance.context.create_instance(**data)
            self.log.info("Created instance `{}`".format(_instance))
            self.log.debug("instance.data `{}`".format(_instance.data))

    def test_overlap(self, effect_t_in, effect_t_out):
        covering_exp = bool(
            (effect_t_in <= self.clip_in)
            and (effect_t_out >= self.clip_out)
        )
        overlaying_right_exp = bool(
            (effect_t_in < self.clip_out)
            and (effect_t_out >= self.clip_out)
        )
        overlaying_left_exp = bool(
            (effect_t_out > self.clip_in)
            and (effect_t_in <= self.clip_in)
        )

        return any((
            covering_exp,
            overlaying_right_exp,
            overlaying_left_exp
        ))

    def add_effect(self, track_index, sitem):
        track = sitem.parentTrack().name()
        # node serialization
        node = sitem.node()
        node_serialized = self.node_serialization(node)
        node_name = sitem.name()
        node_class = node.Class()

        # collect timelineIn/Out
        effect_t_in = int(sitem.timelineIn())
        effect_t_out = int(sitem.timelineOut())

        if not self.test_overlap(effect_t_in, effect_t_out):
            return

        self.log.debug("node_name: `{}`".format(node_name))
        self.log.debug("node_class: `{}`".format(node_class))

        return {node_name: {
            "class": node_class,
            "timelineIn": effect_t_in,
            "timelineOut": effect_t_out,
            "subTrackIndex": sitem.subTrackIndex(),
            "trackIndex": track_index,
            "track": track,
            "node": node_serialized
        }}

    def node_serialization(self, node):
        node_serialized = {}

        # adding ignoring knob keys
        _ignoring_keys = ['invert_mask', 'help', 'mask',
                          'xpos', 'ypos', 'layer', 'process_mask', 'channel',
                          'channels', 'maskChannelMask', 'maskChannelInput',
                          'note_font', 'note_font_size', 'unpremult',
                          'postage_stamp_frame', 'maskChannel', 'export_cc',
                          'select_cccid', 'mix', 'version', 'matrix']

        # loop through all knobs and collect not ignored
        # and any with any value
        for knob in node.knobs().keys():
            # skip nodes in ignore keys
            if knob in _ignoring_keys:
                continue

            # Hiero 15.1v3
            # This seems to be a bug. The "file" knob
            # is always returned as animated by the API.
            # (even tho it's not even possible
            # to set this knob as animated from the UI).
            is_file_knob = knob == "file"

            # get animation if node is animated
            if not is_file_knob and node[knob].isAnimated():
                # grab animation including handles
                knob_anim = [node[knob].getValueAt(i)
                             for i in range(
                             self.clip_in_h, self.clip_out_h + 1)]

                node_serialized[knob] = knob_anim
            else:
                node_serialized[knob] = node[knob].value()

        return node_serialized
