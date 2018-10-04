import pygame as pg
import json

from components.sprites import Sprite, Animated_Sprite

class Clickable:
    def __init__(self, manifest_path : str, event_manager: "Event Manager class"):
        self.event_manager = event_manager
        self._load_manifest(manifest_path)

    def clicked(self):
        self.event_manager.touch_input(self.id, "clicked")
    
    def _load_manifest(self, manifest_path):
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            self.id = manifest['name']


class SimpleButton(Sprite, Clickable):
    """ Simple button implements the Clickable method to turn a static sprite into a simple button """
    def __init__(self, sprite_path: str, manifest_path: str, event_manager: "Event Manager class"):
        """ Constructor

        Keyword arguments:
        sprite_path -- the sprite image path
        manifest_path -- the json manifest file describing the button
        event_manager -- the event manager
        """
        Sprite.__init__(self, sprite_path)
        Clickable.__init__(self, manifest_path, event_manager)


class State_Button(Animated_Sprite, Clickable):
    def __init__(self, sprite_path: str, manifest_path: str, event_manager):
        Animated_Sprite.__init__(self, sprite_path)
        Clickable.__init__(self, manifest_path, event_manager)
    
    def update(self):
        pass
    
    def clicked(self):
        self.curr_frame = (self.curr_frame + 1) % self.nb_frames
        self.image = self.frames[self.curr_frame]
        self.event_manager.touch_input(self.id, self.curr_frame)

class Switch_Button(State_Button):
    """ A button that alternate between two states, returns true or false when clicked. Default state is false"""
    def __init__(self, sprite_path: str, manifest_path: str, event_manager):
        super().__init__(sprite_path, manifest_path, event_manager)
    
    def clicked(self):
        self.curr_frame = not self.curr_frame
        self.image = self.frames[self.curr_frame]
        self.event_manager.touch_input(self.id, 'true' if self.curr_frame else 'false')

class Animated_Button(Animated_Sprite, Clickable):
    def __init__(self, sprite_path: str, manifest_path: str, event_manager):
        Animated_Sprite.__init__(self, sprite_path)
        Clickable.__init__(self, manifest_path, event_manager)

class Animated_Switch_Button(Animated_Sprite, Clickable):
    def __init__(self, sprite_path: str, manifest_path: str, event_manager):
        Animated_Sprite.__init__(self, sprite_path)
        Clickable.__init__(self, manifest_path, event_manager)
        self.updating = False
    
    def clicked(self):
        if self.updating:
            self.curr_frame = 0
            self.image = self.frames[self.curr_frame]
        self.updating = not self.updating
        self.event_manager.touch_input(self.id, 'true' if self.updating else 'false')
    
    def update(self):
        if self.updating:
            super().update()

def Button_Factory(manifest_path : str, target_surface : pg.Surface, event_manager : " Event Manager Class") -> Clickable:
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
        button_type = manifest['type']
        sprite_path = manifest_path.split('.')[0] + ".png"
        if button_type == 'single':
            button =  SimpleButton(sprite_path,manifest_path, event_manager)
        elif button_type == 'state':
            button =  State_Button(sprite_path, manifest_path, event_manager)
        elif button_type == 'animated':
            button =  Animated_Button(sprite_path, manifest_path, event_manager)
        elif button_type == 'switch':
            button =  Switch_Button(sprite_path, manifest_path, event_manager)
        elif button_type == 'animated_switch':
            button =  Animated_Switch_Button(sprite_path, manifest_path, event_manager)
        else:
            return None
        button.set_rect(target_surface, manifest['rect'], center=True)
        return button