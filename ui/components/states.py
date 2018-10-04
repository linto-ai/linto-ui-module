import logging

from components.buttons import Button_Factory


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

    def __str__(self):
        return self.id

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

        #Captation
        self.wuw_spotting = manifest['wuw_spotting']

    def set(self):
        """Set this state as the current state"""
        logging.debug("Changing to state {}".format(self.id))
        self.manager.set_buttons(self.buttons)
        self.manager.play_anim(self.animation)
        self.manager.spotter_status(self.wuw_spotting)

    def __str__(self):
        return "<State: {}>".format(self.id)