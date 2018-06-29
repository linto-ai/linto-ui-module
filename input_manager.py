#!/usr/bin/env python3
# # -*- coding: utf-8 -*-
import os, sys
import datetime
from threading import Thread
import subprocess
from enum import Enum
import logging
import time

import argparse
import pygame as pg
import paho.mqtt.client as mqtt
import tenacity
import json
from pgelement import *

FILE_PATH = os.path.dirname(os.path.abspath(__file__)) + '/'
draw_order= ["body", "eyes", "mouth", "token_right", "token_center", "token_left", "center"]
sprites_dict = {'static' : Static_Sprite, 'bouncing': Bouncing_Sprite, 'animated': Animated_Sprite, 'none': None}
FPS = 30
class Animation(pg.sprite.OrderedUpdates):
    def __init__(self, screen, manifest_path, render_group, end_loop_callback: callable):
        pg.sprite.OrderedUpdates.__init__(self)
        self.screen = screen
        self.render_group = render_group
        self.end_loop_callback = end_loop_callback
        self.duration = None
        self.load_manifest(manifest_path)
        
    def load_manifest(self, manifest_path):
        try:
            print(manifest_path)
            json_manifest = json.load(open(manifest_path, 'r'))
            placeholder_man = json.load(open(FILE_PATH + "placeholders.json", 'r'))
            placeholder_man = placeholder_man['placeholders']
            self.id = json_manifest['id']
            logging.debug("Loading %s animation" % self.id) 
            #Load animation info
            self.type = json_manifest['type']
            if self.type in ['timed']:
                self.duration = json_manifest['duration'] * FPS
        except FileNotFoundError:
            logging.warning("Could not load animation manifest file %s" % manifest_path)
            return

        self.isState = True if json_manifest['type'] == 'state' else False
        # Check or create sprites for each placeholder
        
        for sprite_ph in draw_order:
            if sprite_ph not in json_manifest['sprites'].keys():
                continue
            sprite_info = json_manifest['sprites'][sprite_ph]
            sprite_type = sprites_dict[sprite_info['mode']]
            if sprite_type is None:
                continue
            sprite_name = sprite_info['sprite_name']
            logging.debug("Adding sprite %s" % sprite_name)
            
            if self.type in ['one-time']:
                sprite = sprite_type(FILE_PATH + "sprites/" + sprite_name, callback=self.end_loop_callback)
            else:
                sprite = sprite_type(FILE_PATH + "sprites/" + sprite_name)
            sprite.set_rect(self.screen,placeholder_man[sprite_ph], center=True)
            self.add(sprite)
    
class Linto_UI:
    def __init__(self, manifest_path: str, args):
        self.screen_size = args.resolution
        self.screen = self.init_gui(self.screen_size, args.fullscreen)
        self.center_pos = [v//2 for v in self.screen_size]
        self.frame_counter = 0
        self.anim_end = None
        self.silenced = False

        self.render_sprites = pg.sprite.OrderedUpdates()
        self.buttons_all = pg.sprite.Group()
        self.buttons_visible = pg.sprite.Group()
        self.background_sprites = pg.sprite.Group()
        self.init_background_sprites()
        self.load_animations('animations')
        self.current_state = self.animations['loading']
        self.play_anim('loading')
        self.event_manager = Event_Manager(self)
        self.event_manager.start()
        self.load_button()
        

    def init_gui(self,resolution, fullscreen: bool):
        pg.display.init()
        pg.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))
        print("using resolution: ",resolution)
        return pg.display.set_mode(resolution,pg.FULLSCREEN|pg.HWSURFACE if fullscreen else pg.NOFRAME)

    def init_background_sprites(self):
        background = pg.Surface(self.screen_size)
        background.fill((0,0,0))
        pg.draw.circle(background,(50,50,50),self.center_pos, self.center_pos[0], 0)
        self.background = pg.sprite.Sprite()
        self.background.image = background
        self.background.rect = background.get_rect()
        self.ring = Rotating_Ring(FILE_PATH + 'sprites/ring', self.screen_size)

        self.background_sprites.add(self.background)

    def load_animations(self, dir):
        self.animations = dict()
        logging.debug("Loading animations")
        with open(FILE_PATH +'animations_manifest.json', 'r') as f:
            manifest = json.load(f)
        #loading states
        for state in manifest.keys():
            anim = Animation(self.screen, FILE_PATH + os.path.join(dir, state + '.json'), self.render_sprites, self.back_to_state)
            self.animations[state] = anim

    def load_button(self):
        logging.debug("Loading Buttons")
        with open(FILE_PATH + 'buttons_manifest.json', 'r') as f:
            manifest = json.load(f)
        self.buttons_placeholder = manifest['placeholder']
        self.buttons = {}
        for button in manifest['button'].keys():
            self.buttons[button] = Button(FILE_PATH + '/sprites/' +  button, self.event_manager)
            self.buttons[button].set_rect(self.screen, self.buttons_placeholder[manifest['button'][button]['placeholder']])
            self.buttons[button].visible = manifest['button'][button]['visible']
            if self.buttons[button].visible :
                self.buttons_visible.add(self.buttons[button])
            self.buttons_all.add(self.buttons[button])

    def play_anim(self, anim_name):
        animation = self.animations[anim_name]
        self.frame_counter = 0
        if animation.isState:
            self.current_state = animation
            self.anim_end = None
        elif animation.duration != None:
            self.anim_end = animation.duration
            
        self.render_sprites = self.animations[anim_name]

    def back_to_state(self):
        # Is called when a one-time animation end to go back to suspended state
        self.render_sprites = self.current_state

    def run(self):
        clock = pg.time.Clock()
        mouse_sprite = pg.sprite.Sprite()
        while True:
            if self.anim_end != None:
                self.frame_counter +=1
                if self.frame_counter >= self.anim_end:
                    self.back_to_state()
            self.frame_counter+=1
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

class Event_Manager(Thread):
    def __init__(self, ui: Linto_UI):
        Thread.__init__(self)
        self.ui = ui
        self.load_manifest()
        self.alive = True
        self.anim_lock = False

    def load_manifest(self):
        with open(FILE_PATH + "event_binding.json", 'r') as f:
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
            broker.connect("localhost", 1883, 0)
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
        logging.debug("Connected to broker")
        for topic in self.event_binding['broker_msg'].keys():
                self.broker.subscribe(topic)
        self.ui.play_anim('idle')
    
    def _on_broker_disconnect(self, client, userdata, rc):
        logging.debug("Disconnection")
        if self.broker is not None:
            self.broker.disconnect()
        self.broker = None
    
    def _on_broker_msg(self, client, userdata, message):
        #TODO: Modify according to new MQTT message specs
        topic = message.topic
        msg = message.payload.decode("utf-8")
        logging.debug("Received message %s on topic %s" % (msg,topic))
        if msg not in self.event_binding['broker_msg'][topic].keys():
            if 'any' in self.event_binding['broker_msg'][topic].keys():
                msg = 'any'
            else:
                logging.debug("No matching action for message %s on topic %s" % (msg,topic))
                return  
        actions = self.event_binding['broker_msg'][topic][msg]
        self._resolve_action(actions)
            

    def touch_input(self, button, value):
        logging.debug('Touch: %s -> %s' % (button, value))
        if button in self.event_binding['touch_input'].keys():
            if value in self.event_binding['touch_input'][button].keys():
                actions = self.event_binding['touch_input'][button][value]
                self._resolve_action(actions)

    def publish(self, topic, msg):
        # Format message looking for tokens
        payload = msg.replace("%DATE", datetime.datetime.now().isoformat())
        logging.debug("Publishing msg %s on topic %s" % (payload, topic))
        self.broker.publish(topic, payload)

    def _resolve_action(self, actions):
        if self.anim_lock and "anim_lock" not in actions:
            return
        for action in actions.keys():
            if action == 'display':                        
                self.ui.play_anim(actions["display"])
            elif action == 'publish' and self.broker is not None:
                self.publish(actions["publish"]['topic'],
                                    actions["publish"]['message'])
            elif action == 'sound' and self.ui.silenced != True:
                self.play_sound(actions["sound"])
            elif action == 'anim_lock':
                self.anim_lock = actions["anim_lock"]

    def play_sound(self, name):
        logging.debug("playing sound")
        file_path = os.path.dirname(os.path.abspath(__file__)) + '/sounds/'+ name +'.wav'
        subprocess.call(['aplay', file_path])

    def run(self):
        while self.alive:
            self.ui.play_anim('com')
            self.broker = self.broker_connect()
            self.ui.play_anim('idle')
            self.broker.loop_forever(retry_first_connection=True)

def main(args):
    ui = Linto_UI("", args)
    ui.run()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)8s %(asctime)s %(message)s ")
    parser = argparse.ArgumentParser(description='GUI interface to record audio samples for wake word corpus building')
    parser.add_argument('-r', dest='resolution', type=int, nargs=2,default=[480,480], help="Screen resolution")
    parser.add_argument('-fs', '--fullscreen', help="Put display on fullscreen with hardware acceleration", action="store_true")
    args = parser.parse_args()
    main(args)