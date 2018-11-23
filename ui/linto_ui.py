#!/usr/bin/env python3

import argparse
import configparser
import datetime
import json
import logging
import os
import sys
import threading
import time
from enum import Enum
from typing import Union

import pygame as pg
from pygame.locals import *

import wave
import pyaudio

from ui.components.animations import Animation, Timed_Animation
from ui.components.buttons import Button_Factory
from ui.components.eventmanager import Event_Manager
from ui.components.states import Mode, State
from ui.components.texts import DateTime, MessageFrame, TextBox, MeetingTimer

FILE_PATH = os.path.dirname(os.path.abspath(__file__))
BACKGROUND_COLOR = (200,200,200)
FPS = 30

class Linto_UI:
    def __init__(self, args, config):
        self.config = config
        pg.display.init()
        pg.font.init()

        # Init display
        self.screen_size = args.resolution
        self.screen = self.init_gui(self.screen_size, args.fullscreen)
        self.background = pg.Surface(self.screen_size, flags=pg.HWSURFACE)

        #Background image
        self.background.blit(pg.image.load(os.path.join(FILE_PATH, "sprites", "back.jpg")), [0,0])
        
        self.screen.blit(self.background, [0,0])
        pg.display.update()
        self.center_pos = [v//2 for v in self.screen_size]
            
        self.render_sprites = pg.sprite.OrderedUpdates()
        self.overlay_sprites = pg.sprite.OrderedUpdates()
        if self.config['time'] and not args.notime:
            self.overlay_sprites.add(DateTime([10,10]))
        self.updated_rects = []

        #Animations
        self.animations = dict()
        self.load_animations('animations')

        #Event_Manager
        self.event_manager = Event_Manager(self, config)

        #Buttons
        self.buttons = pg.sprite.Group()
        self.buttons_visible = pg.sprite.OrderedUpdates()
        self.load_buttons()
        
        #States
        self.states = {}
        self.load_states('states')
        self.current_state = None
        
        #Modes
        self.modes = {}
        self.load_modes('modes')
        self.current_mode = None
        
        self.set_mode('command')
        self.event_manager.start()

        # Sound init
        self.audio = pyaudio.PyAudio()
        
    def init_gui(self,resolution, fullscreen: bool):
        """ Init pygame modules and set the display surface
        
        Keyword arguments:
        resolution -- set the display resolution [width, heigth]
        fullscreen -- (boolean) Set display to fullscreen
        """
        
        if not self.config['debug'] == 'true':
            pg.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))
        display = pg.display.Info()
        self.display_width = display.current_w
        self.display_height = display.current_h 
        logging.debug("Using resolution ({},{})".format(self.display_width, self.display_height))
        return pg.display.set_mode(resolution,pg.FULLSCREEN|pg.HWSURFACE if fullscreen else pg.NOFRAME|pg.HWACCEL)
        
    def load_animations(self, folder: 'animation folder'):
        """Load all the .json file in a specified folder as animations.
        
        Keyword arguments:
        folder -- An absolute path to a folder containing .json animation manifests
        """
        self.animations = dict()
        logging.debug("Loading animations")
        for file_name in os.listdir(os.path.join(FILE_PATH, folder)):
            file_path = os.path.join(FILE_PATH, folder, file_name)
            if file_path.endswith(".json"):
                with open(file_path, 'r') as f:
                    manifest = json.load(f)
                    if manifest['type'] in ['timed']:
                        anim = Timed_Animation(self.screen, manifest, self.render_sprites)
                    else:
                        anim = Animation(self.screen, manifest, self.render_sprites)
                    self.animations[anim.id] = anim
    
    def load_states(self, folder : str='states'):
        """Load all the .json file in a specified folder as states.
        
        Keyword arguments:
        folder -- An absolute path to a folder containing .json state manifests
        """
        for file_name in os.listdir(os.path.join(FILE_PATH,folder)):
            file_path = os.path.join(FILE_PATH, folder, file_name)
            if file_path.endswith('.json'):
                with open(file_path) as f:
                    manifest = json.load(f)
                    self.states[manifest['state_name']] = State(manifest, self)
    
    def load_modes(self, folder: str='modes'):
        """Load all the .json file in a specified folder as modes.
        
        Keyword arguments:
        folder -- An absolute path to a folder containing .json mode manifests
        """
        for file_name in os.listdir(os.path.join(FILE_PATH, folder)):
            file_path = os.path.join(FILE_PATH, folder, file_name)
            if file_path.endswith('.json'):
                with open(file_path) as f:
                    manifest = json.load(f)
                    self.modes[manifest['mode_name']] = Mode(manifest, self)

    def load_buttons(self, folder: str='buttons'):
        """Load all the .json file in a specified folder as buttons.
        
        Keyword arguments:
        folder -- An absolute path to a folder containing .json button manifests
        """
        self.buttons = dict()
        logging.debug("Loading Buttons")
        for file_name in os.listdir(os.path.join(FILE_PATH,folder)):
            file_path = os.path.join(FILE_PATH, folder, file_name)
            if file_path.endswith('.json'):
                button = Button_Factory(file_path, self.screen, self.event_manager)
                self.buttons[button.id] = button

    def play_anim(self, animation : Union[Animation, str]):
        """ Display an animation.

        Keyword arguments:
        animation -- Either an animation instance or the animation name.
        """
        if type(animation) == str:
            animation = self.animations[animation]
        
        self.render_sprites = animation
        
        if type(animation) is Timed_Animation:
            t= threading.Thread(target = self._timed_animation_callback, args=(animation.duration,))
            self.clear_screen()
            t.start()

    def _timed_animation_callback(self, duration):
        time.sleep(duration)
        self.clear_screen()
        self.play_anim(self.current_mode.current_state.animation)

    def set_mode(self, mode):
        """ Change the current mode

        Keyword arguments:
        mode -- Mode name or instance.
        """
        
        if type(mode) == str:
            mode = self.current_mode.previous_mode if mode == "last" else self.modes[mode]
        mode.set(self.current_mode)
        self.current_mode = mode
        self.clear_screen()
    
    def set_state(self, state_name: str):
        """ Change the current state

        Keyword arguments:
        state_name -- state name.
        """
        
        self.states[state_name].set()
        self.current_mode.current_state = self.states[state_name]
        self.clear_screen()

    def set_buttons(self, buttons):
        """ Clear visible buttons and display buttons in the list 
        
        Keyword arguments:
        buttons -- a list of Buttons"""
        self.buttons_visible = pg.sprite.OrderedUpdates()
        self.buttons_visible.add(buttons)

    def spotter_status(self, status : bool):
        """ Send a message on the pipeline on wuw_topic (defined in config file) in order to activate or deactivate wake-up-word spotting

        Keyword arguments:
        status -- (boolean) True to allow spotting or false to deactivate it.
        """
        self.event_manager.publish(self.config["wuw_topic"], '{"on":"%(DATE)", "value":"'+ str(status) + '"}')

    def update_sprites(self):
        #Updating sprites
        self.render_sprites.update()
        self.overlay_sprites.update()
        self.buttons_visible.update()
    
    def clear_sprites(self):
        """Clear sprites location"""
        rects = []
        # TODO Clear only updated buttons
        self.overlay_sprites.clear(self.screen, self.background)
        # Clear render_sprite TODO: clear only animated or moving sprites
        for sprite  in self.render_sprites.sprites():
            intersect = False
            for rect in rects:
                if rect.contains(sprite.rect):
                    intersect = True
                    break
            if not intersect:
                rects.append(sprite.rect)
        
        for sprite in self.buttons_visible.sprites():
            intersect = False
            for rect in rects:
                if rect.contains(sprite.rect):
                    intersect = True
                    break
            if not intersect:
                rects.append(sprite.rect)
        for rect in rects:
            self.screen.blit(self.background, [rect[0], rect[1]], area=rect)
        return rects
    
    def clear_screen(self):
        self.screen.blit(self.background, [0,0])

    def draw_sprites(self):
        """Draw all visible sprites and return rect of changed areas"""
        updated_rects = []

        # Drawing
        rect = self.render_sprites.draw(self.screen)
        if rect is not None:
            updated_rects.extend(rect)
        rect = self.overlay_sprites.draw(self.screen)
        if rect is not None:
            updated_rects.extend(rect)
        rect = self.buttons_visible.draw(self.screen)
        updated_rects.extend(rect)

        return updated_rects

    def play_sound(self, name):
        def sound_playing(audio, name):
            logging.debug("playing sound with pyaudio")
            file_path = os.path.join(FILE_PATH, 'sounds', name +'.wav')
            try:
                f = wave.open(file_path)
            except:
                logging.error("Could not open {}".format(file_path))
                return
            logging.debug("Sample_rate={}, channel={}, samp_width={}".format(f.getframerate(),
                                                                f.getnchannels(), 
                                                                f.getsampwidth()))
            stream = audio.open(format = audio.get_format_from_width(f.getsampwidth()),  
                    channels = f.getnchannels(),  
                    rate = f.getframerate(),  
                    output = True)
            data = f.readframes(1024)

            while data:
                stream.write(data)
                data = f.readframes(1024)
        
            stream.stop_stream()
            stream.close()
        t = threading.Thread(target=sound_playing, args=(self.audio,name,))
        t.start()

    def inputs(self):
        for event in pg.event.get():
            if event.type in [pg.MOUSEBUTTONUP]:
                mouse_sprite = pg.sprite.Sprite()
                mouse_sprite.rect = pg.Rect( event.pos[0] -1, event.pos[1]-1, 2,2)
                collided = pg.sprite.spritecollide(mouse_sprite, self.buttons_visible, False)
                for sprite in collided:
                    sprite.clicked()
            if event.type in [pg.KEYUP] and event.key == pg.K_ESCAPE:
                self.event_manager.end()
                exit()

    def run(self):
        """ Main loop of the program. Update sprites and catch events. 
        """
        clock = pg.time.Clock()
        self.spotter_status(True)
        while True:                
            rects = self.clear_sprites()
            self.update_sprites()
            rects.extend(self.draw_sprites())
            pg.display.update()
            clock.tick(FPS)
            self.inputs()

def main():
    config = configparser.ConfigParser()
    config.read(os.path.join(FILE_PATH,"config.conf"))
    config = config['CONFIG']
    logging.basicConfig(level=logging.DEBUG if config['debug'] == 'true' else logging.INFO, format="%(levelname)8s %(asctime)s %(message)s ")
    parser = argparse.ArgumentParser(description='GUI interface for the LinTo device')
    parser.add_argument('-r', dest='resolution', type=int, nargs=2,default=[800,480], help="Screen resolution")
    parser.add_argument('-fs', '--fullscreen', help="Put display on fullscreen with hardware acceleration", action="store_true")
    parser.add_argument('-nt', '--notime', help="Hide timestamp", action="store_true")
    args = parser.parse_args()

    ui = Linto_UI(args, config)
    ui.run()

if __name__ == '__main__':
    main()
