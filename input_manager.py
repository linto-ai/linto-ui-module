#!/usr/bin/env python3
# # -*- coding: utf-8 -*-
import os, sys
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


sprites_dict = {'static' : Static_Sprite, 'bouncing': Bouncing_Sprite, 'animated': Animated_Sprite, 'none': None}
draw_order= ["body", "eyes", "mouth", "token_right", "token_center", "token_left", "center"]
FPS = 15
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
            placeholder_man = json.load(open("placeholders.json", 'r'))
            placeholder_man = placeholder_man['placeholders']
            self.id = json_manifest['animation']['id']
            logging.debug("Loading %s animation" % self.id) 
            #Load animation info
            self.type = json_manifest['animation']['type']
            if self.type in ['timed']:
                self.duration = json_manifest['animation']['duration'] * FPS
        except FileNotFoundError:
            logging.warning("Could not load animation manifest file %s" % manifest_path)
            return

        self.isState = True if json_manifest['animation']['type'] == 'state' else False
        # Check or create sprites for each placeholder
        
        for sprite_ph in draw_order:
            sprite_info = json_manifest['animation']['sprites'][sprite_ph]
            sprite_type = sprites_dict[sprite_info['mode']]
            if sprite_type is None:
                continue
            sprite_name = sprite_info['sprite_name']
            # check if exist
            logging.debug("Adding sprite %s" % sprite_name)
            try:
                sprite = next(s for s in self.all_sprites if isinstance(s, sprite_type) and s.img_name == sprite_name)
            except:
                # If not create it
                if self.type in ['one-time']:
                    sprite = sprite_type(sprite_name, callback=self.end_loop_callback)
                else:
                    sprite = sprite_type(sprite_name)
                sprite.set_rect(self.screen,placeholder_man[sprite_ph], center=True)
                self.all_sprites.add(sprite)
            finally:
                self.sprites.append(sprite)

    def play(self, callback=None):
        if len(self.render_group) > 0:
            self.render_group.empty()
        print('has sprite', [sprite.img_name for sprite in self.sprites])
        for sprite in [sprite for sprite in self.sprites if isinstance(sprite, Animated_Sprite)]:
            sprite.frame_counter = 0
        self.render_group.add(self.sprites)
        print('has sprite', [sprite.img_name for sprite in self.render_group.sprites()])
    
class Linto_UI:
    def __init__(self, manifest_path: str, args):
        self.screen_width = 480
        self.screen_height = 480
        self.screen_size = [self.screen_width, self.screen_height]
        self.screen = self.init_gui(self.screen_size)
        self.center_pos = [v//2 for v in self.screen_size]
        self.frame_counter = 0
        self.anim_end = None
        self.silenced = False

        self.all_sprites = pg.sprite.Group()
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
        

    def init_gui(self,resolution):
        pg.display.init()
        #pg.font.init()
        pg.mixer.quit()
        print("using resolution: ",resolution)
        return pg.display.set_mode(resolution,pg.NOFRAME)

    def init_background_sprites(self):
        background = pg.Surface(self.screen_size)
        background.fill((0,0,0))
        pg.draw.circle(background,(50,50,50),self.center_pos, self.center_pos[0], 0)
        self.background = pg.sprite.Sprite()
        self.background.image = background
        self.background.rect = background.get_rect()
        self.ring = Rotating_Ring('ring', self.screen_size)

        self.background_sprites.add(self.background)

    def load_animations(self, dir):
        self.animations = dict()
        logging.debug("Loading animations")
        with open('animations_manifest.json', 'r') as f:
            manifest = json.load(f)
        #loading states
        for state in manifest.keys():
            anim = Animation(self.screen, os.path.join(dir, state + '.json'), self.all_sprites, self.render_sprites, self.back_to_state)
            self.animations[state] = anim

    def load_button(self):
        logging.debug("Loading Buttons")
        with open('buttons_manifest.json', 'r') as f:
            manifest = json.load(f)
        self.buttons_placeholder = manifest['placeholder']
        self.buttons = {}
        for button in manifest['button'].keys():
            self.buttons[button] = Button(button, self.event_manager)
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
            
        self.animations[anim_name].play()

    def back_to_state(self):
        # Is called when a one-time animation end to go back to suspended state
        self.current_state.play()

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
            self.render_sprites.draw(self.screen)
            self.buttons_visible.update()
            self.buttons_visible.draw(self.screen)
            pg.display.flip()

            for event in pg.event.get():
                if event.type in [pg.MOUSEBUTTONUP]:
                    mouse_sprite.rect = pg.Rect(event.pos[0]-1, event.pos[1]-1, 2,2)
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
            broker.connect("localhost", 1883, 0)
            broker.on_disconnect = self._on_broker_disconnect
            broker.on_message = self._on_broker_msg
            return broker
        except:
            logging.warning("Failed to connect to broker (Retrying after 5s)")
            self.ui.play_anim('com')
            return None
    
    def end(self):
        self.broker.disconnect()
        self.alive = False

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
        topic = message.topic
        msg = message.payload.decode("utf-8")
        logging.debug("Received message %s on topic %s" % (msg,topic))
        if msg not in self.event_binding['broker_msg'][topic].keys():
            if 'any' in self.event_binding['broker_msg'][topic].keys():
                msg = 'any'
            else:
                logging.debug("No matching action for message %s on topic %s" % (msg,topic))
                return  
        for action in self.event_binding['broker_msg'][topic][msg].keys():
            if action == 'display':                        
                self.ui.play_anim(self.event_binding['broker_msg'][topic][msg]["display"])
            elif action == 'publish' and self.broker is not None:
                self.broker.publish(self.event_binding['broker_msg'][topic][msg]["publish"]['topic'],
                                    self.event_binding['broker_msg'][topic][msg]["publish"]['message'])
            elif action == 'sound' and self.ui.silenced != True:
                self.play_sound(self.event_binding['broker_msg'][topic][msg]["sound"])


    def touch_input(self, button, value):
        logging.debug('Touch: %s -> %s' % (button, value))
        if button in self.event_binding['touch_input'].keys():
            if value in self.event_binding['touch_input'][button].keys():
                for action in self.event_binding['touch_input'][button][value].keys():
                    if action == 'display':                        
                        self.ui.play_anim(self.event_binding['touch_input'][button][value]["display"])
                    elif action == 'publish' and self.broker is not None:
                        self.broker.publish(self.event_binding['touch_input'][button][value]["publish"]['topic'],
                                            self.event_binding['touch_input'][button][value]["publish"]['message'])
                    elif action == 'sound' and self.ui.silenced != True:
                        self.play_sound(self.event_binding['touch_input'][button][value]["sound"]['name'])

    def play_sound(self, name):
        logging.debug("playing sound")
        subprocess.call(['aplay', os.path.dirname(os.path.abspath(__file__)) + '/sounds/'+ name +'.wav'])

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
    parser.add_argument('-r', dest='resolution', type=int, nargs=2, help="Screen resolution")
    args = parser.parse_args()
    main(args)