import time
import pygame as pg
import json
from typing import Union



class Sprite(pg.sprite.Sprite):
    """ Base Sprite class that load an image and offers methods to change position and size.
    """
    updated = False
    def __init__(self, sprite_path: str):
        """ Load sprite image.

        Keyword arguments:
        sprite_path -- the sprite image path
        """
        super().__init__()
        self.sprite_path = sprite_path
        self.fs_image = pg.image.load(sprite_path) # Fullscale image
        self.image = self.fs_image
        self.rect = self.image.get_rect()

    def set_pos(self, pos : Union[list, tuple], center: bool = False):
        """ Set image position on target surface.
        By default set the coordinate of sprite top-left corner. If center
        is set to true will set the sprite center to the given coordinates.


        Keyword arguments:\n
        pos -- list or tuple, distance from top-left corners [x, y] \n
        center -- match coordinate to sprite center (default false)
        """
        offset_x = 0
        offset_y = 0
        if center:
            offset_x += self.rect.w/2
            offset_y += self.rect.h/2
        self.rect.x = pos[0] - offset_x
        self.rect.y = pos[1] - offset_y
        self.updated = True

    def set_rect(self, surface : pg.Surface, rect : list, center=False):
        """ Set sprite rect. rect is size and position. Note that value are
        relative to target surface.

        Keyword arguments:
        surface -- target surface
        rect -- new position and size [x, y, width, height]
        center -- match coordinates to sprite center (default false)
        """
        surface_size = surface.get_rect().size
        new_rect = [v * rect[i] for i,v in enumerate(surface_size + surface_size)]
        self.set_size(new_rect[2:])
        self.set_pos(new_rect[:2], center=center)


    def set_size(self, new_size: list):
        """ Set absolute size of the sprite

        Keyword arguments:
        new_size -- the new size to be applied [width, height]
        """
        self.image = pg.transform.scale(self.image, [int(v) for v in new_size])
        self.rect = self.image.get_rect()
        self.updated = True


class Bouncing_Sprite(Sprite):
    """ A sprite that move up and down with a given Amplitude"""
    def __init__(self, sprite_path: str, amplitude: int = 5, speed : float = 0.5):
        """ Constructor.

        Keyword arguments:
        sprite_path -- image file path
        amplitude -- number of pixels to move up and down
        speed -- number of pixels to move at each frame
        """
        super().__init__(sprite_path)
        self.pos = self.rect.y
        self.curr_offset, self.direction = 0, True
        self.amplitude = amplitude
        self.speed =  speed

    def set_pos(self, pos : Union[list, tuple], center: bool = False):
        super().set_pos(pos, center)
        self.pos = self.rect.y

    def update(self):
        move = self.speed * (1 if self.direction else -1)
        self.curr_offset += move
        self.rect.y = int(self.pos + self.curr_offset)
        if abs(self.curr_offset) > self.amplitude:
            self.direction = not self.direction
        self.updated = True        

class Animated_Sprite(Sprite):
    """ An animated sprite."""
    def __init__(self, sprite_path: str):
        """ Constructor for a animated sprite need the presence of a json file describing animation parameters

        Keyword arguments:
        sprite_path -- image file path

        """
        super().__init__(sprite_path)
        self._read_manifest(".".join(sprite_path.split('.')[:-1]) + '.json')
        self.frame_counter = 0
        self.curr_frame = 0

    def _read_manifest(self, manifest_path):
        """ Read the animation manifest and extract animation parameters

        Keyword arguments:
        manifest_path -- the json manifest path
        """
        self.frames = []
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            self.nb_frames = manifest['nb_frames']
            if 'frame_duration' in manifest.keys():
                self.frame_duration = manifest['frame_duration']
            else:
                self.frame_duration = 1
            frame_width = manifest['frame_width']
            for i in range(self.nb_frames):
                frame = self.image.subsurface((i*frame_width, 0, frame_width, self.rect.h))
                self.frames.append(frame)
                self.rect = frame.get_rect()

    def set_rect(self,surface, rect, center=False):
        """ Adapt the set_rect parent function to multiple sprite elements"""
        surface_size = surface.get_rect().size
        new_rect = [v * rect[i] for i,v in enumerate(surface_size+surface_size)]
        self.rect = pg.Rect(new_rect)
        new_frames = []
        for f in self.frames:
            f = pg.transform.scale(f, [int(v) for v in new_rect[2:]])
            self.set_pos(new_rect[:2], center=center)
            offset_x = 0
            offset_y = 0
            if center:
                offset_x += f.get_rect().w/2
                offset_y += f.get_rect().h/2
            self.rect.x = new_rect[0] - offset_x
            self.rect.y = new_rect[1] - offset_y
            new_frames.append(f)
        self.frames = new_frames
        self.image = self.frames[0]
        self.updated = True

    def update(self):
        self.frame_counter += 1
        if self.frame_counter >= self.frame_duration:
            self.frame_counter = 0
            self.curr_frame = (self.curr_frame + 1) % self.nb_frames
            self.image = self.frames[self.curr_frame]
            self.updated = True


def SpriteFactory(sprite_path : str, mode : str, surface : pg.Surface, rect : list) -> Sprite :
    """ Returns the proper sprite class according to mode and set the proper size and coordinates

    Keyword arguments:
    sprite_path -- sprite location
    mode -- sprite mode, must be either static or bouncing
    surface -- surface hosting the sprite
    rect -- sprite target rect
    """
    if not sprite_path.endswith('.png'):
        sprite_path += '.png'
    if mode == "static":
        sprite = Sprite(sprite_path)
    elif mode == "bouncing":
        sprite = Bouncing_Sprite(sprite_path)
    elif mode == "animated":
        sprite = Animated_Sprite(sprite_path)
    sprite.set_rect(surface, rect, center=True)
    return sprite