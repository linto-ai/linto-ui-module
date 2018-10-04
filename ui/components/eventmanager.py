import os
import threading
import datetime
import logging
import alsaaudio
import json
import subprocess

import pygame as pg
import paho.mqtt.client as mqtt
import tenacity

from components import ROOT_PATH

class Event_Manager(threading.Thread):
    """
    Event manager deal with the input from the MQTT broker and the touchscreen inputs.
    It matchs each input with the responses defined for the current mode or states.
    """
    def __init__(self, ui : "UI class", config):
        threading.Thread.__init__(self)
        self.config = config
        self.ui = ui
        self.alive = True
        self.connected = True
        self.broker = None

        #Audio init
        mixer = alsaaudio.Mixer()
        mixer.setvolume(60)

    @tenacity.retry(wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_attempt(24),
            retry=tenacity.retry_if_result(lambda s: s is None),
            retry_error_callback=(lambda s: s.result())
            )
    def broker_connect(self):
        logging.info("Attempting connexion to broker at %s:%i" % (self.config['broker_ip'], int(self.config['broker_port'])))
        try:
            broker = mqtt.Client()
            broker.on_connect = self._on_broker_connect
            broker.connect(self.config['broker_ip'], int(self.config['broker_port']), 0)
            broker.on_disconnect = self._on_broker_disconnect
            broker.on_message = self._on_broker_msg
            return broker
        except:
            logging.warning("Failed to connect to broker (Retrying after 5s)")
            self.ui.play_anim('error')
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

        for file_name in [file_name for file_name in os.listdir(os.path.join(ROOT_PATH, 'modes')) if file_name.endswith('.json')]: 
            file_path = os.path.join(ROOT_PATH, 'modes', file_name)
            files.append(file_path)

        for file_name in [file_name for file_name in os.listdir(os.path.join(ROOT_PATH, 'states')) if file_name.endswith('.json')]: 
            file_path = os.path.join(ROOT_PATH, 'states', file_name)
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
        """ Solve received MQTT broker messages.
        """
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

        #TODO Find a proper way to incorporate the following in resolve_actions
        if 'timer' in payload.keys():
            duration = int(payload['timer'])
            msg = payload['title'] if 'title' in payload.keys() else ''
            callback = int(payload['callback']) if 'callback' in payload.keys() else 0
            self.display_timer(msg, duration=duration, callback=callback)
            
    def display_timer(self, msg, duration=0, callback=[]):
        timer = MeetingTimer([100,315,280,80], msg, duration*60)
        timer.set_callback([-1,0,1], self.timer_callback)
        self.ui.overlay_sprites = pg.sprite.OrderedUpdates()
        self.ui.overlay_sprites.add(timer)
        

    def timer_callback(self, time_left):
        if time_left < 0: 
            print("Il reste {} minutes".format(time_left))
        elif time_left == 0:
            print("Le temps alloué est terminé")
        else:
            print("Le temps alloué a été dépassé de {} minutes".format(time_left))


    def touch_input(self, button, value):
        logging.debug('Touch: %s -> %s' % (button, value))
        mode_trigger = self.ui.current_mode.events['button_clicked']
        state_trigger = self.ui.current_mode.current_state.events['button_clicked']
        
        if button in mode_trigger.keys() and value in mode_trigger[button].keys():
            actions = mode_trigger[button][value]
            self._resolve_action(actions)
        elif button in state_trigger.keys() and value in state_trigger[button].keys():
            actions = state_trigger[button][value]
            self._resolve_action(actions)
        
    def publish(self, topic, msg):
        # Format message looking for tokens
        if self.broker is not None:
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
            #TODO add a map function
        for action in actions.keys():
            if action == 'publish' and self.broker is not None: 
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
            elif action == 'wuw_spotting':
                #TODO change publish to accept dict and add date
                self.publish(self.config['wuw_topic'], '{"on":"%(DATE)", "value"="' + self.ui.animations[actions['wuw_spotting']] + '"}')
    
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
