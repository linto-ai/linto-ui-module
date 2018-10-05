#!/usr/bin/env python3
# # -*- coding: utf-8 -*-
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

from ui.components.animations import Animation, Timed_Animation
from ui.components.buttons import Button_Factory
from ui.components.eventmanager import Event_Manager
from ui.components.states import Mode, State
from ui.components.texts import DateTime, MessageFrame, TextBox, MeetingTimer

FILE_PATH = os.path.dirname(os.path.abspath(__file__))
BACKGROUND_COLOR = (230,230,210)
FPS = 30

class Linto_UI:
    def __init__(self, args, config):
        self.config = config

        # Init display
        self.screen_size = args.resolution
        self.screen = self.init_gui(self.screen_size, args.fullscreen)
        self.center_pos = [v//2 for v in self.screen_size]
            
        self.render_sprites = pg.sprite.OrderedUpdates()
        self.overlay_sprites = pg.sprite.OrderedUpdates()
        self.overlay_sprites.add(DateTime([10,10]))

        #Backgrounds
        self.init_background()
        self.init_linto_surface()
        self.init_side_panel()

        #Animations
        self.animations = dict()
        self.load_animations('animations')

        #Event_Manager
        self.event_manager = Event_Manager(self, config)

        #Buttons
        self.buttons = pg.sprite.Group()
        self.buttons_visible = pg.sprite.Group()
        self.buttons_panel = pg.sprite.Group()
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
        
    def init_gui(self,resolution, fullscreen: bool):
        """ Init pygame modules and set the display surface
        
        Keyword arguments:
        resolution -- set the display resolution [width, heigth]
        fullscreen -- (boolean) Set display to fullscreen
        """
        pg.display.init()
        pg.font.init()
        if not self.config['debug'] == 'true':
            pg.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0)) # set the cursor invisible
        display = pg.display.Info()
        self.display_width = display.current_w
        self.display_height = display.current_h
        print(self.display_width, self.display_height)
        return pg.display.set_mode(resolution,FULLSCREEN|pg.HWSURFACE if fullscreen else pg.NOFRAME)

    def init_background(self):
        """ Create background element such as background color"""
        self.background = pg.Surface(self.screen_size, pg.HWSURFACE)
        self.background.fill(BACKGROUND_COLOR)

    def init_linto_surface(self):
        """ Linto """
        self.linto_size = [min(self.screen_size)]*2
        self.linto_surface = pg.Surface(self.linto_size, pg.HWSURFACE)

    def init_side_panel(self):
        self.panel_size = [self.screen_size[0]-self.linto_size[0], self.screen_size[1]]
        self.panel_surface = pg.Surface(self.panel_size, pg.HWSURFACE)
        self.panel_surface.fill((150,150,150))
        title = MessageFrame([0,0, self.panel_size[0]-20, 100], "Réunion hebdomadaire")
        self.panel_surface.blit(title.image, [10,20])

        abstract = MessageFrame([0,0, self.panel_size[0]-20, 100], "Objet: Réunion d'avancement\nde l'équipe R&D")
        self.panel_surface.blit(abstract.image, [10,55])

        responsable = MessageFrame([0,0, self.panel_size[0]-20, 100], "Organisateur: J.P Lorré")
        self.panel_surface.blit(responsable.image, [10,125])

        duration = MessageFrame([0,0, self.panel_size[0]-20, 100], "Durée: 2h")
        self.panel_surface.blit(duration.image, [10,160])

        remaining_time = MeetingTimer([0,0,self.panel_size[0], 50], "Temps restants: ", 60)
        self.panel_surface.blit(remaining_time.image, [10,195])

        participants = MessageFrame([0,0, self.panel_size[0]-20, 150], "Participants:\n- {}".format("\n- ".join(['Jean-Pierre Lorré', 'Damien Lainé', 'Sonia Badène', 'Vladimir Poutine', 'Sami Naceri'])))
        self.panel_surface.blit(participants.image, [10,230])
        
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
                        anim = Timed_Animation(self.linto_surface, manifest, self.render_sprites)
                    else:
                        anim = Animation(self.linto_surface, manifest, self.render_sprites)
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
                #button = Button_Factory(file_path, self.linto_surface, self.event_manager)
                button = Button_Factory(file_path, self.linto_surface, self.event_manager)
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
            t.start()

    def _timed_animation_callback(self, duration):
        time.sleep(duration)
        self.play_anim(self.current_mode.current_state.animation)

    def set_mode(self, mode):
        """ Change the current mode

        Keyword arguments:
        mode -- Mode name or instance.
        """
        if type(mode) == str:
            mode = self.current_mode.previous_mode if mode == "last" else self.modes[mode]
        self.overlay_sprites = pg.sprite.OrderedUpdates()
        self.overlay_sprites.add(DateTime([10,10]))
        mode.set(self.current_mode)
        self.current_mode = mode
    
    def set_state(self, state_name: str):
        """ Change the current state

        Keyword arguments:
        state_name -- state name.
        """    
        self.states[state_name].set()
        self.current_mode.current_state = self.states[state_name]

    def set_buttons(self, buttons):
        """ Clear visible buttons and display buttons in the list 
        
        Keyword arguments:
        buttons -- a list of Buttons"""
        self.buttons_visible = pg.sprite.Group()
        self.buttons_visible.add(buttons)

    def spotter_status(self, status : bool):
        """ Send a message on the pipeline on wuw_topic (defined in config file) in order to activate or deactivate wake-up-word spotting

        Keyword arguments:
        status -- (boolean) True to allow spotting or false to deactivate it.
        """
        self.event_manager.publish(self.config["wuw_topic"], '{"on":"%(DATE)", "value":"'+ str(status) + '"}')

    def show_side_panel(self):
        self.panel_visible = True
        self.linto_offset = 0

    def hide_side_panel(self):
        self.panel_visible = False
        self.linto_offset = 160

    def run(self):
        """ Main loop of the program. Update sprites and catch events. 
        """
        clock = pg.time.Clock()
        mouse_sprite = pg.sprite.Sprite()
        self.linto_offset = 160
        self.panel_offset = self.linto_surface.get_width()
        self.panel_visible = False
        self.current_offset = 160
        while True:
            self.screen.blit(self.background, [0,0])
            self.render_sprites.update()
            self.overlay_sprites.update()
            self.linto_surface.fill(BACKGROUND_COLOR)
            if len(self.render_sprites) > 0:
                self.render_sprites.draw(self.linto_surface)

            self.buttons_visible.update()
            self.buttons_visible.draw(self.linto_surface)
            
            if self.current_offset < self.linto_offset:
                self.current_offset += 6
                if self.current_offset > self.linto_offset:
                    self.current_offset = self.linto_offset
            elif self.current_offset > self.linto_offset:
                self.current_offset -= 6
                if self.current_offset < self.linto_offset:
                    self.current_offset = self.linto_offset

            self.screen.blit(self.linto_surface, [self.current_offset,0])

            if self.panel_visible or self.current_offset != self.linto_offset:
                self.screen.blit(self.panel_surface, [self.panel_offset + self.current_offset * 2, 0])
            
            self.overlay_sprites.draw(self.screen)
            pg.display.flip()

            # Touch screen event manager
            for event in pg.event.get():
                if event.type in [pg.MOUSEBUTTONUP]:
                    mouse_sprite.rect = pg.Rect( event.pos[0] - self.linto_offset -1, event.pos[1]-1, 2,2)
                    print("mouse_sprite", mouse_sprite.rect)
                    collided = pg.sprite.spritecollide(mouse_sprite, self.buttons_visible, False)
                    for sprite in collided:
                        sprite.clicked()
                if event.type in [pg.KEYUP] and event.key == pg.K_ESCAPE:
                    self.event_manager.end()
                    exit()
                if event.type in [pg.KEYUP] and event.key == pg.K_LEFT:
                    self.show_side_panel()
                if event.type in [pg.KEYUP] and event.key == pg.K_RIGHT:
                    self.hide_side_panel()
            clock.tick(FPS)

def main():
    config = configparser.ConfigParser()
    config.read(os.path.join(FILE_PATH,"config.conf"))
    config = config['CONFIG']
    logging.basicConfig(level=logging.DEBUG if config['debug'] == 'true' else logging.INFO, format="%(levelname)8s %(asctime)s %(message)s ")
    parser = argparse.ArgumentParser(description='GUI interface for the LinTo device')
    parser.add_argument('-r', dest='resolution', type=int, nargs=2,default=[800,480], help="Screen resolution")
    parser.add_argument('-fs', '--fullscreen', help="Put display on fullscreen with hardware acceleration", action="store_true")
    args = parser.parse_args()

    ui = Linto_UI(args, config)
    ui.run()

if __name__ == '__main__':
    main()
