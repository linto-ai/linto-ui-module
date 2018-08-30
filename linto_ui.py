#!/usr/bin/env python3
# # -*- coding: utf-8 -*-
import os, sys
import datetime
import threading 
import subprocess
import alsaaudio
from enum import Enum
import logging
import time

import argparse
import configparser
import pygame as pg
import paho.mqtt.client as mqtt
import tenacity
import json

from pgelement import *

FILE_PATH = os.path.dirname(os.path.abspath(__file__)) + '/'

FPS = 30

class Mode:
    """ 
    Mode are a layer on top of states. It has a default state and a set of event triggers on top of the current state's ones.
    Mode parameters are set in a json manifest file.
    """
    def __init__(self, manifest: dict, manager):
        self.id = manifest['mode_name']
        self.manager = manager
        self.previous_mode = None
        #Default state
        try:
            self.default_state = self.manager.states[manifest['default_state']]
        except KeyError:
            logging.warning("Could not set default_state {} for mode {}.".format(manifest['default_state'], self.id))
            self.default_state = None
        self.current_state = self.default_state
        #Events
        self.events = manifest['events']
    
    def set(self, previous_mode):
        """Set this mode as the current mode"""
        logging.debug("Changing to mode {} from mode {}".format(self.id, previous_mode.id if previous_mode is not None else 'None'))
        self.previous_mode = previous_mode
        if self.default_state is not None:
            self.current_state = self.default_state
        self.current_state.set() 

class State:
    """
    State instance represents the current state of the system. It is represented by a specific animation, a set of buttons and specific event responses.
    State parameters are set in json manifest file. 
    """
    def __init__(self, manifest: dict, manager):
        self.id = manifest['state_name']
        self.manager = manager
        # Animation
        try:
            self.animation = self.manager.animations[manifest['animation']]
        except KeyError:
            logging.warning("Could not set animation {} for state {}.".format(manifest['animation'], self.id))
        
        #Buttons
        self.buttons = []
        for button_name in manifest['buttons']:
            try:
                self.buttons.append(self.manager.buttons[button_name])
            except KeyError:
                logging.warning("Could not set button {} for state {}.".format(button_name, self.id))
        #Events
        self.events = manifest['events']

    def set(self):
        """Set this state as the current state"""
        logging.debug("Changing to state {}".format(self.id))
        self.manager.set_buttons(self.buttons)
        self.manager.play_anim(self.animation)

    def __str__(self):
        return "<State: {}>".format(self.id)

class Animation(pg.sprite.OrderedUpdates):
    def __init__(self, screen, manifest, render_group):
        pg.sprite.OrderedUpdates.__init__(self)
        self.screen = screen
        self.render_group = render_group
        self.duration = None
        self.manifest = manifest
        self.load_manifest()
        
    def load_manifest(self):
        try:
            placeholder_man = json.load(open(FILE_PATH + "placeholders.json", 'r'))
            draw_order = placeholder_man["draw_order"]
            placeholder_man = placeholder_man['placeholders']
            self.id = self.manifest['id']
            logging.debug("Loading %s animation" % self.id)
        except FileNotFoundError:
            logging.warning("Could not load placeholder manifest file")
            return

        # Check or create sprites for each placeholder
        for sprite_ph in draw_order:
            if sprite_ph not in self.manifest['sprites'].keys():
                continue
            sprite_info = self.manifest['sprites'][sprite_ph]
            sprite_type = sprites_dict[sprite_info['mode']] #sprite_dict is set in pgelement, it associates sprite type with classes
            if sprite_type is None:
                continue
            sprite_name = sprite_info['sprite_name']
            logging.debug("Adding sprite {}".format(sprite_name))
            sprite = sprite_type(FILE_PATH + "sprites/" + sprite_name)
            sprite.set_rect(self.screen,placeholder_man[sprite_ph], center=True)
            self.add(sprite)

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

class Linto_UI:
    def __init__(self, args, config):
        self.config = config

        # Init display
        self.screen_size = args.resolution
        self.screen = self.init_gui(self.screen_size, args.fullscreen)
        self.center_pos = [v//2 for v in self.screen_size]
            
        self.render_sprites = pg.sprite.OrderedUpdates()

        #Animations
        self.animations = dict()
        self.load_animations('animations')

        #Event_Manager
        self.event_manager = Event_Manager(self, config)

        #Backgrounds
        self.background_sprites = pg.sprite.Group()
        self.init_background_sprites()
        
        #Buttons
        self.buttons = pg.sprite.Group()
        self.buttons_visible = pg.sprite.Group()
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
        pg.display.init()
        pg.font.init()
        if not self.config['debug'] == 'true':
            pg.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0)) # set the cursor invisible
        return pg.display.set_mode(resolution,pg.FULLSCREEN|pg.HWSURFACE if fullscreen else pg.NOFRAME)

    def init_background_sprites(self):
        background = pg.Surface(self.screen_size)
        background.fill((0,0,0))
        pg.draw.circle(background,(50,50,50),self.center_pos, self.center_pos[0], 0)
        self.background = pg.sprite.Sprite()
        self.background.image = background
        self.background.rect = background.get_rect()
        self.rings = {}
        placeholder_man = json.load(open(FILE_PATH + "placeholders.json", 'r'))
        placeholder_man = placeholder_man['placeholders']
        for color in ['ring_red', 'ring_blue', 'ring_green']:
            self.rings[color] = Static_Sprite(FILE_PATH + 'sprites/' + color)
            self.rings[color].set_rect(self.screen, placeholder_man['ring'])
        self.set_ring('ring_blue')
        self.background_sprites.add(self.background)
        self.background_sprites.add(TextBox("prototype {}".format(self.config['version']),(2,2)))
        timer = TextTimer((380,2))
        timer.start_timer(0)
        self.background_sprites.add(timer)

    def set_ring(self, ring_color):
        if ring_color in self.rings.keys():
            self.background.image.blit(self.rings[ring_color].image, [0,0])
        else:
            logging.warning('UI: Tried to set unknown ring color %s' % ring_color)

    def load_animations(self, folder):
        self.animations = dict()
        logging.debug("Loading animations")
        for file_name in os.listdir(FILE_PATH + folder):
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
        for file_name in os.listdir(FILE_PATH + folder):
            file_path = os.path.join(FILE_PATH, folder, file_name)
            if file_path.endswith('.json'):
                with open(file_path) as f:
                    manifest = json.load(f)
                    self.states[manifest['state_name']] = State(manifest, self)
    
    def load_modes(self, folder: str='modes'):
        for file_name in os.listdir(FILE_PATH + folder):
            file_path = os.path.join(FILE_PATH, folder, file_name)
            if file_path.endswith('.json'):
                with open(file_path) as f:
                    manifest = json.load(f)
                    self.modes[manifest['mode_name']] = Mode(manifest, self)

    def load_buttons(self, folder: str='buttons'):
        self.buttons = dict()
        logging.debug("Loading Buttons")
        for file_name in os.listdir(FILE_PATH + folder):
            file_path = os.path.join(FILE_PATH, folder, file_name)
            if file_path.endswith('.json'):
                with open(file_path) as f:
                    manifest = json.load(f)
                    self.buttons[manifest['name']] = Button(FILE_PATH + 'buttons/' + manifest['name'], self.event_manager)
                    self.buttons[manifest['name']].set_rect(self.screen, manifest['rect'])

    def play_anim(self, animation):
        if type(animation) == str:
            animation = self.animations[animation]
        self.render_sprites = animation
        if type(animation) is Timed_Animation:
            t= threading.Thread(target = self.timed_animation_callback, args=(animation.duration,))
            t.start()

    def timed_animation_callback(self, duration):
        """ Wait for duration then call the fun function with arguments. """
        time.sleep(duration)
        self.play_anim(self.current_mode.current_state.animation)

    def set_mode(self, mode):
        if type(mode) == str:
            mode = self.current_mode.previous_mode if mode == "last" else self.modes[mode]
        try:
            mode.set(self.current_mode)
            self.current_mode = mode
        except KeyError:
            logging.warning("Could not set mode {}. Not initialized".format(mode))
    
    def set_state(self, state_name):
        try:
            self.states[state_name].set()
            self.current_mode.current_state = self.states[state_name]
        except KeyError:
            logging.warning("Could not set state {}. Not initialized".format(state_name))

    def set_buttons(self, buttons):
        self.buttons_visible.empty()
        self.buttons_visible.add(buttons)

    def run(self):
        clock = pg.time.Clock()
        mouse_sprite = pg.sprite.Sprite()
        while True:
            self.background_sprites.update()
            self.background_sprites.draw(self.screen)
            self.render_sprites.update()
            if len(self.render_sprites) > 0:
                self.render_sprites.draw(self.screen)
            self.buttons_visible.update()
            self.buttons_visible.draw(self.screen)
            pg.display.flip()
            # Event manager
            for event in pg.event.get():
                if event.type in [pg.MOUSEBUTTONUP]:
                    mouse_sprite.rect = pg.Rect(event.pos[0]-1, event.pos[1]-1, 2,2)
                    print("mouse_sprite", mouse_sprite.rect)
                    collided = pg.sprite.spritecollide(mouse_sprite, self.buttons_visible, False)
                    for sprite in collided:
                        sprite.clicked()
                if event.type in [pg.KEYUP] and event.key == pg.K_ESCAPE:
                    self.event_manager.end()
                    exit()
            clock.tick(FPS)

class Event_Manager(threading.Thread):
    """
    Event manager deal with the input from the MQTT broker and the touchscreen inputs.
    It matchs each input with the responses defined for the current mode or states.
    """
    def __init__(self, ui: Linto_UI, config):
        threading.Thread.__init__(self)
        self.config = config
        self.ui = ui
        self.alive = True
        self.connected = True
        self.muted = False
        self.counter = 0

        #Audio init
        mixer = alsaaudio.Mixer()
        mixer.setvolume(60)

    @tenacity.retry(wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_attempt(24),
            retry=tenacity.retry_if_result(lambda s: s is None),
            retry_error_callback=(lambda s: s.result())
            )
    def broker_connect(self):
        logging.info("Attempting connexion to broker at %s:%i" % (config['broker_ip'], int(config['broker_port'])))
        try:
            broker = mqtt.Client()
            broker.on_connect = self._on_broker_connect
            broker.connect(config['broker_ip'], int(config['broker_port']), 0)
            broker.on_disconnect = self._on_broker_disconnect
            broker.on_message = self._on_broker_msg
            return broker
        except:
            logging.warning("Failed to connect to broker (Retrying after 5s)")
            self.ui.play_anim('com')
            return None
    
    def end(self):
        self.alive = False
        self.broker.disconnect()
        
    def _on_broker_connect(self, client, userdata, flags, rc):
        """ Function called when the Mqtt client connects to the broker.
        It looks for every broker_message event within the modes and states json files and
        subscribe to the relevant topics.
        """
        logging.info("Connected to broker")
        topics = set() # Set of topics: Prevents duplicate
        files = [] # List of json files

        for file_name in [file_name for file_name in os.listdir(FILE_PATH + 'modes') if file_name.endswith('.json')]: 
            file_path = os.path.join(FILE_PATH, 'modes', file_name)
            files.append(file_path)

        for file_name in [file_name for file_name in os.listdir(FILE_PATH + 'states') if file_name.endswith('.json')]: 
            file_path = os.path.join(FILE_PATH, 'states', file_name)
            files.append(file_path)
        for file_path in files:
            with open(file_path, 'r') as f:
                manifest = json.load(f)
                for topic_name in manifest['events']['broker_message']:
                    topics.add(topic_name)
        for topic in topics:
            self.broker.subscribe(topic)
            logging.debug("Subscribed to {}".format(topic))
    
    def _on_broker_disconnect(self, client, userdata, rc):
        logging.debug("Disconnection")
        if self.broker is not None:
            self.broker.disconnect()
        self.broker = None
    
    def _on_broker_msg(self, client, userdata, message):
        
        topic = message.topic
        msg = message.payload.decode("utf-8")
        logging.debug("Received message %s on topic %s" % (msg,topic))
        value = None
        try:
            payload = json.loads(msg)
            if 'value' in payload.keys():
                value = payload['value']
        except:
            logging.warning('Could not load json from message.')        
        mode_trigger = self.ui.current_mode.events['broker_message']
        state_trigger = self.ui.current_mode.current_state.events['broker_message']

        if topic in mode_trigger.keys():
            if value in mode_trigger[topic].keys():
                self._resolve_action(mode_trigger[topic][value])
            elif 'any' in mode_trigger[topic].keys():
                self._resolve_action(mode_trigger[topic]['any'])
        elif topic in state_trigger.keys():
            if value in state_trigger[topic].keys():
                self._resolve_action(state_trigger[topic][value])
            elif 'any' in state_trigger[topic].keys():
                self._resolve_action(state_trigger[topic]['any'])
            
    def touch_input(self, button, value):
        logging.debug('Touch: %s -> %s' % (button, value))
        mode_trigger = self.ui.current_mode.events['button_clicked']
        state_trigger = self.ui.current_mode.current_state.events['button_clicked']
        
        if button in mode_trigger.keys():
            if value in mode_trigger[button].keys():
                actions = mode_trigger[button][value]
                self._resolve_action(actions)
        
        elif button in state_trigger.keys():
            if value in state_trigger[button].keys():
                actions = state_trigger[button][value]
                self._resolve_action(actions)
        
            
    def publish(self, topic, msg):
        # Format message looking for tokens
        payload = msg.replace("%(DATE)", datetime.datetime.now().isoformat())
        
        logging.debug("Publishing msg %s on topic %s" % (payload, topic))
        self.broker.publish(topic, payload)

    def _resolve_action(self, actions):
        if 'ring' in actions.keys():
                self.ui.set_ring(actions['ring'])
        if 'connexion' in actions.keys():
                self.connected = actions['connexion']
        elif not self.connected:
            return
        for action in actions.keys():
            if action == 'display':                 
                self.ui.play_anim(actions["display"])
            elif action == 'publish' and self.broker is not None:
                self.publish(actions["publish"]['topic'],
                                    actions["publish"]['message'])
            elif action == 'sound':
                self.play_sound(actions["sound"])
            elif action == 'volume':
                self.change_volume(actions['volume'])
            elif action == 'mode':
                self.ui.set_mode(actions['mode'])
            elif action == 'state':
                self.ui.set_state(actions['state'])
            elif action == 'play':
                self.ui.play_anim(self.ui.animations[actions['play']])
                
    
    def change_volume(self, value):
        mixer = alsaaudio.Mixer()
        mixer.setvolume(value)

    def play_sound(self, name):
        logging.debug("playing sound")
        file_path = os.path.dirname(os.path.abspath(__file__)) + '/sounds/'+ name +'.wav'
        subprocess.Popen(['aplay', file_path])

    def run(self):
        while self.alive:
            self.broker = self.broker_connect()
            self.broker.loop_forever(retry_first_connection=True)

def main(args, config):
    ui = Linto_UI(args, config)
    ui.run()

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(FILE_PATH + "config.conf")
    config = config['CONFIG']
    logging.basicConfig(level=logging.DEBUG if config['debug'] == 'true' else logging.INFO, format="%(levelname)8s %(asctime)s %(message)s ")
    parser = argparse.ArgumentParser(description='GUI interface for the LinTo device')
    parser.add_argument('-r', dest='resolution', type=int, nargs=2,default=[480,480], help="Screen resolution")
    parser.add_argument('-fs', '--fullscreen', help="Put display on fullscreen with hardware acceleration", action="store_true")
    args = parser.parse_args()
    main(args, config)