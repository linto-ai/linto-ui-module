#!/usr/bin/env python3
# # -*- coding: utf-8 -*-
import time
import pygame as pg
import json
from typing import Union


"""  BUTTONS
The following classes describe sprites elements with different behaviors.
They inherits from the Sprite parent class that implements basics functions.
All sprite class must have an update() function aswell as a image(pygame.Surface) and a rect(pygame.Rect) values
sprites_dict dictionnary is the list of the different sprites used in the main program to associate manifest sprite mode with proper class
"""


class Sprite(pg.sprite.Sprite):
    def __init__(self, img_name: str):
        pg.sprite.Sprite.__init__(self)
        self.img_name = img_name
        self.original_image = pg.image.load("%s.png" % img_name)
        self.image = self.original_image
        self.rect = self.image.get_rect()
        self.angle = 0

    def set_pos(self, pos, center=False):
        offset_x = 0
        offset_y = 0
        if center:
            offset_x += self.rect.w/2
            offset_y += self.rect.h/2
        self.rect.x = pos[0] - offset_x
        self.rect.y = pos[1] - offset_y

    def update(self):
      pass

    def set_rect(self,screen, rect, center=False):
        screen_size = screen.get_rect().size
        new_rect = [v * rect[i] for i,v in enumerate(screen_size+screen_size)]
        self.set_size(new_rect[2:])
        self.set_pos(new_rect[:2], center=center)

    def rotate_center(self):
        self.image = pg.transform.rotozoom(self.image, self.angle, 1)
        self.rect = self.image.get_rect(center=self.rect.center)
 
    def set_size(self, new_size):
        self.image = pg.transform.scale(self.image, [int(v) for v in new_size])
        self.rect = self.image.get_rect()

    def scale(self, ratio):
        self.set_size([self.rect.w * ratio, self.rect.h * ratio])

class Static_Sprite(Sprite):
    def __init__(self, img_name: str):
        Sprite.__init__(self,img_name)
        
class Bouncing_Sprite(Sprite):
    def __init__(self, img_name: str, amplitude: int = 5):
        Sprite.__init__(self,img_name)
        self.max, self.min = amplitude,-amplitude
        self.curr_v, self.dir = 0, 1
        self.frame_skip = True

    def update(self):
        self.frame_skip = not self.frame_skip
        if self.frame_skip:
            if self.curr_v == self.max:
                self.dir *= -1
            if self.curr_v == self.min:
                self.dir *= -1
            self.curr_v += self.dir
            self.rect.y += self.dir

class Rotating_Ring(Sprite):
    def __init__(self, img_name, size):
        Sprite.__init__(self,img_name)
        self.image = pg.transform.scale(self.image, size)
        self.rect = self.image.get_rect()

    def update(self):
        self.angle = (self.angle + 3) % 360
        self.rotate_center()

class Animated_Sprite(Sprite):
    def __init__(self, img_name):
        Sprite.__init__(self, img_name)
        self.curr_frame = 0
        self.frame_counter = 0
        self._read_manifest()
        
    def _read_manifest(self):
        manifest_name = self.img_name + '.json'
        with open(manifest_name, 'r') as f:
            self.manifest = json.load(f)
        self.frames = []
        self.nb_frames = self.manifest['nb_frames']
        self.frame_duration = self.manifest['frame_duration']
        frame_width = self.manifest['frame_width']
        for i in range(self.nb_frames):
            frame = self.image.subsurface((i*frame_width, 0, frame_width, self.rect.h))
            self.frames.append(frame)
            self.rect = frame.get_rect()
        
        
    def set_rect(self,screen, rect, center=False):
        screen_size = screen.get_rect().size
        new_rect = [v * rect[i] for i,v in enumerate(screen_size+screen_size)]
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

    def update(self):
        self.frame_counter += 1
        if self.frame_counter >= self.frame_duration:
            self.frame_counter = 0
            self.curr_frame = (self.curr_frame + 1) % self.nb_frames
            self.image = self.frames[self.curr_frame]

sprites_dict = {'static' : Static_Sprite, 'bouncing': Bouncing_Sprite, 'animated': Animated_Sprite, 'none': None}

""" BUTTONS
The following classes describes buttons classes with differents behaviors
"""
class Button(Sprite):
    def __init__(self, button_name, event_manager):
        Sprite.__init__(self,button_name)
        self.event_manager = event_manager
        self.id = button_name
        self.state = 0
        self.frame_counter = 0
        self._load_manifest()

    def _load_manifest(self):
        #TODO: Different classes ? 
        manifest_name = self.id + '.json'
        with open(manifest_name, 'r') as f:
            self.manifest = json.load(f)
        self.id = self.manifest['name']
        self.frame_width = self.manifest['frame_width']
        self.nb_frames = self.manifest['nb_frames']
        self.type = self.manifest['type']
        if self.type == 'single':
            return
        if self.type == 'state':
            self.values = self.manifest['state_values']
        if self.type == 'animated':
            self.frame_duration = self.manifest['frame_duration']
        self.frames = []
        for i in range(self.nb_frames):
            frame = self.image.subsurface((i*self.frame_width, 0, self.frame_width, self.rect.h))
            self.frames.append(frame)
        self.image = self.frames[self.state]

    def clicked(self):
        if self.type == 'on-off':
            self.state = not self.state
            self.image = self.frames[self.state]
            self.event_manager.touch_input(self.id, "on" if self.state else "off")
        elif self.type == 'value':
            self.state = (self.state + 1 ) % self.nb_frames
            self.image = self.frames[self.state]
            self.event_manager.touch_input(self.id, self.values[self.state])
        elif self.type in ['single', 'animated']:
            self.event_manager.touch_input(self.id, 'clicked')

    def update(self):
        if self.type == 'animated':
            self.frame_counter += 1
            if self.frame_counter == self.frame_duration:
                self.frame_counter = 0
                self.state = (self.state + 1) % self.nb_frames
                self.image = self.frames[self.state]

    def set_rect(self, screen, rect, center=True):
        screen_size = screen.get_rect().size
        new_rect = [v * rect[i] for i,v in enumerate(screen_size+screen_size)]
        self.rect = pg.Rect(new_rect)
        new_frames = []
        if self.type == "single":
            self.image = pg.transform.scale(self.image, [int(v) for v in new_rect[2:]])
            self.set_pos(new_rect[:2], center=center)
            offset_x = 0
            offset_y = 0
            if center:
                offset_x += self.image.get_rect().w/2
                offset_y += self.image.get_rect().h/2
            self.rect.x = new_rect[0] - offset_x
            self.rect.y = new_rect[1] - offset_y
            return

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

class Simple_Button(Button):
    """ A simple button that trigger an event when pressed
    Triggers 'clicked' when clicked is called (wow).
    """
    def __init__(self, button_name, event_manager):
        super().__init__(button_name, event_manager)

    def _load_frames(self):
        manifest_name = self.id + '.json'
        with open(manifest_name, 'r') as f:
            manifest = json.load(f)

    def clicked(self):
        self.event_manager.touch_input(self.id, 'clicked')

    def set_rect(self, screen, rect, center=True):
        screen_size = screen.get_rect().size
        new_rect = [v * rect[i] for i,v in enumerate(screen_size+screen_size)]
        self.rect = pg.Rect(new_rect)
        self.image = pg.transform.scale(self.image, [int(v) for v in new_rect[2:]])
        self.set_pos(new_rect[:2], center=center)
        offset_x = 0
        offset_y = 0
        if center:
            offset_x += self.image.get_rect().w/2
            offset_y += self.image.get_rect().h/2
        self.rect.x = new_rect[0] - offset_x
        self.rect.y = new_rect[1] - offset_y

class Switch_Button(Button):
    """ A switch button that alternate between two states
    Triggers either 'on' or 'off' when clicked. Default is off.
    """
    def __init__(self, sprite_name, event_manager):
        super().__init__(sprite_name, event_manager)
        self.state = False

    def clicked(self):
        self.state = not self.state
        self.image = self.frames[self.state]
        self.event_manager.touch_input(self.id, "on" if self.state else "off")

class Animated_Button(Simple_Button):
    """ A simple button that is animated
    Triggers 'clicked' when clicked is called (hummm)"""
    def __init__(self, sprite_name, event_manager):
        super().__init__(sprite_name, event_manager)

    pass

class Animated_Switch_Button(Animated_Button):
    def __init__(self, sprite_name, event_manager):
        super().__init__(sprite_name, event_manager)
        self.state = False
    
    def update(self):
        if self.state:
            pass

    def clicked(self):
        self.state = not self.state
        self.image = self.frames[0]
        self.event_manager.touch_input(self.id, "on" if self.state else "off")

class States_Button(Button):
    pass


""" TEXT
The following classes describe text display classes. 
"""
class TextBox(pg.sprite.Sprite):
    def __init__(self, text : str = "Text", 
                       pos  : tuple = (0,0), 
                       font_name : str = "Comic Sans MS",
                       font_size : int = 30,
                       color : tuple = (125,125,125)):
        super().__init__()
        self.text = text
        self.pos = pos
        self.font_name = font_name
        self.font = pg.font.SysFont(font_name, font_size)
        self.color = color
        self._create_surface()
        
    def _create_surface(self):
        self.image = self.font.render(self.text, False, self.color)
        self.rect = pg.Rect(self.pos[0], self.pos[1], self.image.get_rect().width, self.image.get_rect().height)

    def set_text(self, text):
        self.text = text
        self._create_surface()
    
    def set_font_size(self, font_size : int):
        self.font = pg.font.SysFont(self.font_name, font_size)
        self._create_surface()

    def set_color(self, color : tuple):
        self.color = color
        self._create_surface()

    def update(self):
        pass


class TextTimer(TextBox):
    def __init__(self, pos):
        super().__init__("00:00:00", pos)
        self.start_time = time.time()
    
    def start_timer(self, duration : "Duration in minutes"):
        self.start_time = time.time()
        self.end_time = self.start_time + duration * 60

    def update(self):
        remaining_time = self.end_time - time.time()
        sign = '-' if remaining_time >= 0 else '+'
        remaining_time = abs(remaining_time)
        minutes = remaining_time // 60
        hours = minutes // 60
        minutes -= 60 * hours
        remaining_time -= (hours * 3600 + minutes * 60)
        self.text = "{}{:02d}:{:02d}:{:02d}".format(sign, int(hours), int(minutes), int(remaining_time))
        self._create_surface()

