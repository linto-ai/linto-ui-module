import pygame as pg
import time
import datetime

class TextBox(pg.sprite.Sprite):
    font_name = "Comic Sans MS"
    font_size = 30
    color = (125,125,125)
    def __init__(self, text : str, 
                       pos  : tuple = (0,0)): 
                       
        super().__init__()
        self.text = text
        self.pos = pos
        self.font_name = self.font_name
        self.font = pg.font.SysFont(self.font_name, self.font_size)
        self.color = self.color
        self._create_surface()
        
    def _create_surface(self):
        self.image = self.font.render(self.text, True, self.color)
        self.rect = pg.Rect(self.pos[0], self.pos[1], self.image.get_rect().width, self.image.get_rect().height)

    def set_text(self, text):
        self.text = text
        self._create_surface()
    
    def set_font_size(self, font_size : int):
        self.font = pg.font.SysFont(self.font_name, font_size)
        self._create_surface()

    def set_color(self, color : tuple):
        self.color = color
        self._create_surface()

    def update(self):
        pass

class TextTimer(TextBox):
    def __init__(self, pos):
        super().__init__("00:00:00", pos)
        self.start_time = time.time()
    
    def start_timer(self, duration : "Duration in minutes"):
        self.start_time = time.time()
        self.end_time = self.start_time + duration * 60

    def update(self):
        remaining_time = self.end_time - time.time()
        sign = '-' if remaining_time >= 0 else '+'
        remaining_time = abs(remaining_time)
        minutes = remaining_time // 60
        hours = minutes // 60
        minutes -= 60 * hours
        remaining_time -= (hours * 3600 + minutes * 60)
        self.text = "{}{:02d}:{:02d}:{:02d}".format(sign, int(hours), int(minutes), int(remaining_time))
        self._create_surface()

class DateTime(TextBox):
    font_size = 40
    color = (75,75,75)
    def __init__(self, pos):
        super().__init__(datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S'), pos)
    def update(self):
        self.set_text(datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S'))



class Frame(pg.sprite.Sprite):
    background_color = (50,50,50)
    border_color = (0,204,255)
    border_width = 3
    alpha = 150

    def __init__(self, rect : list, frame: bool = False):
        super().__init__()
        self.image = pg.Surface(rect[2:], pg.SRCALPHA|pg.HWSURFACE)
        if frame:
            self.image.set_alpha(0)
            self.image.fill(self.background_color)
            pg.draw.rect(self.image, self.border_color, pg.Rect(0,0,self.image.get_width(), self.image.get_height()), self.border_width)
            self.image.set_alpha(self.alpha)
        else:
            self.image = pg.Surface.convert_alpha(self.image)
        self.rect = pg.Rect(rect)

class MessageFrame(Frame):
    padding = 5
    font_name = "Comic Sans MS"
    font_size = 30
    font_color = (255,255,255)
    def __init__(self, rect : list, text : str):
        super().__init__(rect)
        self.text = text
        self.font = pg.font.SysFont(self.font_name, self.font_size)
        self._init_image()

    def _init_image(self):
        self.image = pg.Surface(self.rect[2:], pg.SRCALPHA|pg.HWSURFACE)
        self.dist_ftop = 0
        for line in self.text.split('\n'):
            text_img = self.font.render(line, True, self.font_color)
            self.image.blit(text_img, [(self.rect.width/2) - text_img.get_width()/2, self.dist_ftop + self.padding])
            self.dist_ftop += text_img.get_height()

class MeetingTimer(MessageFrame):
    timer_font_size = 40
    callback_fun = None
    callback_times = []
    def __init__(self, rect: list, text: str, duration: int):
        super().__init__(rect, text)
        self.static_image = self.image.copy()
        self.end_time = time.time() + duration

    def start_timer(self, duration : "Duration in minutes"):
        self.start_time = time.time()
        self.end_time = self.start_time + duration * 60

    def set_callback(self, callback_times : list, callback_fun):
        self.callback_times = callback_times
        self.callback_fun = callback_fun

    def update(self):
        remaining_time = self.end_time - time.time()
        if int(remaining_time) == 0:
            self.set_timer_color((255,0,0))
        
        if int(remaining_time)//60 in self.callback_times:
            self.callback_fun(int(remaining_time)//60)
            self.callback_times.remove(int(remaining_time)//60)
        sign = '-' if remaining_time >= 0 else '+'
        remaining_time = abs(remaining_time)
        minutes = remaining_time // 60
        hours = minutes // 60
        minutes -= 60 * hours
        remaining_time -= (hours * 3600 + minutes * 60)
        text = "{}{:02d}:{:02d}:{:02d}".format(sign, int(hours), int(minutes), int(remaining_time))
        self.font = pg.font.SysFont(self.font_name, self.timer_font_size)
        text_img = self.font.render(text, True, self.font_color)
        self.image = self.static_image.copy()
        self.image.blit(text_img, [(self.rect.width/2) - text_img.get_width()/2, self.dist_ftop + self.padding])
    
    def set_timer_color(self, color):
        self.font_color = color
        self._init_image()