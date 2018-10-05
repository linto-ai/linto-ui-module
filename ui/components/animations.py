import os
import logging
import json

import pygame as pg
from ui.components.sprites import SpriteFactory
from ui.components import ROOT_PATH


class Animation(pg.sprite.OrderedUpdates):
    def __init__(self, screen, manifest, render_group):
        pg.sprite.OrderedUpdates.__init__(self)
        self.screen = screen
        self.render_group = render_group
        self.duration = None
        self.manifest = manifest
        self.load_manifest()
    def load_manifest(self):
        print("ICI2", os.path.join(ROOT_PATH, "placeholders.json"))
        try:
            placeholder_man = json.load(open(os.path.join(ROOT_PATH, "placeholders.json"), 'r'))
            draw_order = placeholder_man["draw_order"]
            placeholder_man = placeholder_man['placeholders']
            self.id = self.manifest['id']
            logging.debug("Loading %s animation" % self.id)
        except FileNotFoundError:
            logging.error("Could not load placeholder manifest file")
            return

        # Check or create sprites for each placeholder
        for sprite_ph in draw_order:
            if sprite_ph not in self.manifest['sprites'].keys():
                continue
            sprite_info = self.manifest['sprites'][sprite_ph]
            sprite_mode = sprite_info['mode']
            if sprite_mode in [None, 'none', 'None']:
                continue
            sprite_name = sprite_info['sprite_name']
            #logging.debug("Adding sprite {}".format(sprite_name))
            self.add(SpriteFactory(os.path.join(ROOT_PATH, "sprites", sprite_name), sprite_mode, self.screen, placeholder_man[sprite_ph]))

    def __str__(self):
        return "<Animation: {} ({})>".format(self.id, self.sprites)


class Timed_Animation(Animation):
    def __init__(self, screen, manifest, render_group):
        Animation.__init__(self, screen, manifest, render_group)
        self.type = manifest['type']
        if self.type == 'timed':
            self.duration = manifest['duration'] # Duration in frames
        else:
            logging.error("Unsupported animation type for {}".format(self.id))
            exit()