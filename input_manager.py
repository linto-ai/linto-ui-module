#!/usr/bin/env python3
# # -*- coding: utf-8 -*-
import os
from threading import Thread
from enum import Enum
import logging
import time

import argparse
import pygame as pg
import paho.mqtt.client as mqtt
import tenacity
import json
from pgelement import *

class State(Enum):
    IDLE = 'idle'
    LISTENING = 'listening'
    SLEEPING = 'sleeping'
    SPEAKING = 'speaking'
    COM = 'com'
    LOADING = 'loading'
    HAPPY = 'happy'

class Event(Enum):
    WUW = 'wuw'
    ERROR = 'error'
    MUTED = 'muted'
    UNMUTED = 'unmuted'
    SILENCED = 'silenced'
    UNSILENCED = 'unsilenced'

class Input_type(Enum):
    BROKER_MSG = 0
    TOUCH_INPUT = 1

sprites_dict = {'static' : Static_Sprite, 'bouncing': Bouncing_Sprite, 'animated': Animated_Sprite, 'none': None}
place_holder = ["body", "eyes", "mouth", "token_right", "token_center", "token_left", "center"]
place_holder_rect = [[0.5,0.5,0.7,0.7], [0.5,0.44,0.25,0.1], [0.5,0.6,0.2,0.05],[0.65,0.10,0.15,0.15] , [], [], [0.5,0.5,0.4,0.2] ]
FPS = 30
class Animation:
    def __init__(self, screen, manifest_path, all_sprites, render_group, end_loop_callback: callable):
        self.screen = screen
        self.all_sprites = all_sprites
        self.render_group = render_group
        self.end_loop_callback = end_loop_callback
        self.sprites = []
        self.duration = None
        self.load_manifest(manifest_path)
        
        
    def load_manifest(self, manifest_path):
        try:
            json_manifest = json.load(open(manifest_path, 'r'))
            self.id = json_manifest['animation']['id']
            logging.debug("Loading %s animation" % self.id) 
            #Load animation info
            self.type = json_manifest['animation']['type']
            if self.type in ['timed']:
                self.duration = int(json_manifest['animation']['duration']) * FPS
        except FileNotFoundError:
            logging.warning("Could not load animation manifest file %s" % manifest_path)
            return

        self.isState = True if json_manifest['animation']['type'] == 'state' else False
        # Check or create sprites for each placeholder
        
        for i,sprite_ph in enumerate(place_holder):
            sprite_info = json_manifest['animation']['sprites'][sprite_ph]
            sprite_type = sprites_dict[sprite_info['mode']]
            if sprite_type is None:
                continue
            sprite_name = sprite_info['sprite_name']
            # check if exist
            try:
                sprite = next(s for s in self.all_sprites if isinstance(s, sprite_type) and s.img_name == sprite_name)
            except:
                # If not create it
                if self.type in ['one-time']:
                    sprite = sprite_type(sprite_name, callback=self.end_loop_callback)

                else:
                    sprite = sprite_type(sprite_name)
                sprite.set_rect(self.screen,place_holder_rect[i], center=True)
                self.all_sprites.add(sprite)
            finally:
                self.sprites.append(sprite)

    def play(self, callback=None):
        self.render_group.empty()
        self.render_group.add(self.sprites)
    
class Linto_UI:
    def __init__(self, manifest_path: str, args):
        self.screen = self.init_gui([1024 ,1024])
        self.screen_width = 1024
        self.screen_height = 1024
        self.screen_size = [self.screen_width, self.screen_height]
        self.center_pos = [v//2 for v in self.screen_size]
        self.frame_counter = 0
        self.anim_end = None

        self.all_sprites = pg.sprite.Group()
        self.background_sprites = pg.sprite.Group()
        self.render_sprites = pg.sprite.Group()

        self.init_background_sprites()
        self.load_animations('animations')
        self.current_state = self.animations['loading']
        self.play_anim('loading')
        self.event_manager = Event_Manager(self)
        self.event_manager.start()
        

    def init_gui(self,resolution):
        pg.display.init()
        pg.font.init()
        print("using resolution: ",resolution)
        return pg.display.set_mode(resolution,pg.NOFRAME)

    def init_background_sprites(self):
        self.ring = Rotating_Ring('ring')
        self.background_sprites.add(self.ring)

    def load_animations(self, dir):
        self.animations = dict()
        logging.debug("Loading animations")
        #loading states
        for state in [e.value for e in State]:
            anim = Animation(self.screen, os.path.join(dir, state + '.json'), self.all_sprites, self.render_sprites, self.back_to_state)
            self.animations[state] = anim

    def play_anim(self, anim_name):
        animation = self.animations[anim_name]
        self.frame_counter = 0
        if animation.isState:
            self.current_state = animation
            self.anim_end = None
        elif animation.duration != None:
            self.anim_end = animation.duration
            
        self.animations[anim_name].play()

    def back_to_state(self):
        # Is called when a one-time animation end to go back to suspended state
        self.current_state.play()

    def run(self):
        clock = pg.time.Clock()
        while True:
            if self.anim_end != None:
                self.frame_counter +=1
                if self.frame_counter >= self.anim_end:
                    self.back_to_state()
            self.frame_counter+=1
            self.screen.fill((0,0,0))
            pg.draw.circle(self.screen,(50,50,50),self.center_pos, self.center_pos[0], 0)
            self.background_sprites.update()
            self.background_sprites.draw(self.screen)
            self.render_sprites.update()
            self.render_sprites.draw(self.screen)
            pg.display.update()
           
            clock.tick(FPS)

class Event_Manager(Thread):
    def __init__(self, ui: Linto_UI):
        Thread.__init__(self)
        self.ui = ui

    def load_manifest(self):
        with open("event_binding.json", 'r') as f:
            self.event_binding = json.load(f)

    @tenacity.retry(wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_attempt(24),
            retry=tenacity.retry_if_result(lambda s: s is None),
            retry_error_callback=(lambda s: s.result())
            )
    def broker_connect(self):
        logging.info("Attempting connexion to broker at %s:%i" % ("localhost", 8889))
        try:
            broker = mqtt.Client()
            broker.on_connect = self._on_broker_connect
            broker.connect("localhost", 8889, 0)
            broker.on_disconnect = self._on_broker_disconnect
            broker.on_message = self._on_broker_msg
            return broker
        except:
            logging.warning("Failed to connect to broker (Retrying after 5s)")
            return None

    def _on_broker_connect(self, client, userdata, flags, rc):
        logging.debug("Connected to broker")
        self.ui.play_anim('idle')
    
    def _on_broker_disconnect(self, client, userdata, rc):
        logging.debug("Disconnection")
        self.broker.disconnect()
    
    def _on_broker_msg(self, client, userdata, message):
        topic = message.topic
        msg = message.payload.decode("utf-8")
        logging.debug("Received message %s on topic %s" % (msg,topic))
        if msg in self.event_binding['broker_msg'][topic].keys():
            anim = self.event_binding['broker_msg'][topic][msg]['display']
        elif 'any' in self.event_binding['broker_msg'][topic].keys():
            anim = self.event_binding['broker_msg'][topic]['any']['display']
        else:
            logging.debug("No matching action for message %s on topic %s" % (msg,topic))
            return
        self.ui.play_anim(anim)


    def run(self):
        while True:
            self.ui.play_anim('com')
            self.broker = self.broker_connect()
            self.load_manifest()
            for key in self.event_binding['broker_msg'].keys():
                self.broker.subscribe(key)
            self.ui.play_anim('idle')
            self.broker.loop_forever(retry_first_connection=True)

def main(args):
    ui = Linto_UI("", args)
    ui.run()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)8s %(asctime)s %(message)s ")
    parser = argparse.ArgumentParser(description='GUI interface to record audio samples for wake word corpus building')
    parser.add_argument('-r', dest='resolution', type=int, nargs=2, help="Screen resolution")
    args = parser.parse_args()
    main(args)