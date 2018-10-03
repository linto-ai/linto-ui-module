# Linto-ui-Module

Linto-ui-module is the User graphic interface that create a visual interactive link between the user and the functionnalities of the Linto Smart Assistant.
It provides a set of animation to provide information regarding the current state of the device and a set of buttons to allow touchscreen inputs.  

## Getting Started

To get a copy a this repository:
```
git clone ...
```

### Dependencies

This program requires python3 and pip to work.
```
sudo apt-get install python3 python3-pip
```
Python libraries required to run the module can be found within the requirements.txt file and can be installed at once using:
```
sudo pip3 install -r requirements.txt
```

apt-get install python3-pygame
pip3 install pyalsaaudio
pip3 install paho-mqtt
pip3 install tenacity

### HOW TO
## Use the module
```
GUI interface for the LinTo device

optional arguments:
  -h, --help            show this help message and exit
  -r RESOLUTION RESOLUTION
                        Screen resolution
  -fs, --fullscreen     Put display on fullscreen with hardware acceleration
```
All executable parameters are overwrites of default parameters that are set in the config.conf file.
For the UI module to be fully functionnal it needs other LinTo modules to be running:
* Command Module 
* Audio Recorder
* Linto Client

Furthermore a backend job server is required to in order to interprete voice commands. 

To launch the module:
```
./linto_ui.py #or
python3 linto_ui.py
```

## Modify the UI
Please refer to the [wiki]().


## Built With

* [PyGame](https://www.pygame.org/) - Cross-platform set of Python modules designed for writing video games.
* [Mosquitto](https://mosquitto.org/) - Easy to use MQTT Broker
* [MQTT Spy](https://github.com/eclipse/paho.mqtt-spy) - Tool to listen and publish MQTT message. 


## License

This project is licensed under the GNU AFFERO License - see the [LICENSE.md](LICENSE.md) file for details

