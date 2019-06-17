import os
import sys

if getattr(sys, 'frozen', False):
    ROOT_PATH = os.path.dirname(sys.executable)
else:
    ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))