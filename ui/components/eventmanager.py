import os
import threading
import datetime
import logging
import json
import subprocess
import time

import paho.mqtt.client as mqtt
import tenacity
import alsaaudio

from ui.components import ROOT_PATH

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
        self.callback_guard = True #Prevent state callback to perform when an action has been performed during timeout counter

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
        self.callback_guard = True
        topic = message.topic
        msg = message.payload.decode("utf-8")
        logging.debug("Received message %s on topic %s" % (msg,topic))
        value = None
        try:
            payload = json.loads(msg)
            if 'value' in payload.keys():
                value = payload['value']
        except:
            payload = msg
            logging.warning('Could not load json from message.')        
        mode_trigger = self.ui.current_mode.events['broker_message']
        state_trigger = self.ui.current_mode.current_state.events['broker_message']

        if topic in mode_trigger.keys():
            if value in mode_trigger[topic].keys():
                self._resolve_action(mode_trigger[topic][value], payload)
            elif 'any' in mode_trigger[topic].keys():
                self._resolve_action(mode_trigger[topic]['any'], payload)
        elif topic in state_trigger.keys():
            if value in state_trigger[topic].keys():
                self._resolve_action(state_trigger[topic][value], payload)
            elif 'any' in state_trigger[topic].keys():
                self._resolve_action(state_trigger[topic]['any'], payload)
        

    def timer_callback(self, time_left):
        if time_left < 0: 
            print("Il reste {} minutes".format(time_left))
        elif time_left == 0:
            print("Le temps alloué est terminé")
        else:
            print("Le temps alloué a été dépassé de {} minutes".format(time_left))

    def state_callback(self, duration, return_state):
        self.callback_guard = False
        time.sleep(duration)
        if not self.callback_guard:
            self.ui.set_state(return_state)


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

    def _resolve_action(self, actions, payload = dict()):
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
                self.ui.play_sound(actions["sound"])
            elif action == 'volume':
                self.change_volume(actions['volume'])
            elif action == 'volume_set':
                if "value" in payload.keys():
                    volume = int(payload["value"])
                self.set_volume(volume)
            elif action == 'mode':
                self.ui.set_mode(actions['mode'])
            elif action == 'state':
                self.ui.set_state(actions['state'])
            elif action == 'timeout':
                t = threading.Thread(target = self.state_callback, args=(actions['timeout']['duration'], actions['timeout']['return_state'],))
                t.start()
            elif action == 'wuw_spotting':
                #TODO change publish to accept dict and add date
                self.publish(self.config['wuw_topic'], '{"on":"%(DATE)", "value":"' + self.ui.animations[actions['wuw_spotting']] + '"}')
            elif action == 'mute':
                self.mute(actions['mute'])
        if 'play' in actions.keys(): 
            self.ui.play_anim(self.ui.animations[actions['play']])
    
    def change_volume(self, volume):
        """ The volume value has been changed through the GUI
        """
        try:
            volume = int(volume)
        except:
            logging.warning("Invalid volume value {}".format(volume))
            return
        if 0 > volume > 100:
            return
        mixer = alsaaudio.Mixer()
        mixer.setvolume(volume)
        self.publish("ui/volume", '{"on": "%(DATE)", "value":"' + str(volume) + '"}')

    def set_volume(self, volume = int):
        """ Change the volume from outside
        """
        volume_button = self.ui.buttons['volume_button']
        if volume_button:
            volume_button = volume_button
            if volume == 0:
                volume_button.set_state(3)
            elif 0 < volume <= 30:
                volume_button.set_state(2)
            elif 30 < volume <= 60:
                volume_button.set_state(1)
            elif 60 < volume:
                volume_button.set_state(0)
                if volume > 100:
                    volume = 100
            self.change_volume(volume)

    def get_volume(self):
        mixer = alsaaudio.Mixer()
        return mixer.getvolume()[0]       

    def mute(self, value):
        mute_button = [button for button in self.ui.buttons_visible if button.id == "mute_button"]
        if mute_button:
            mute_button[0].set_state(value)

    def run(self):
        self.set_volume(self.get_volume())
        while self.alive:
            self.broker = self.broker_connect()
            self.broker.loop_forever(retry_first_connection=True)
