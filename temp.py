class Mode:
    def __init__(self, manifest: dict, manager):
        self.id = "Mode"
        self.default_state = None
        self.buttons = []
        self.previous_mode = None

    def set(self, previous_mode: Mode = None):
        self.previous_mode = None

class State:
    def __init__(self, manifest: dict, manager):
        self.id = "State"
        self.animation = None
        self.buttons = []

    def set(self):
        pass
