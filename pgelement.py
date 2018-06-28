#!/usr/bin/env python3
# # -*- coding: utf-8 -*-
import pygame as pg
import json

class Sprite(pg.sprite.Sprite):
    def __init__(self, img_name: str, callback=None):
        pg.sprite.Sprite.__init__(self)
        self.callback = callback
        self.img_name = img_name
        self.original_image = pg.image.load("sprites/%s.png" % img_name)
        self.image = self.original_image
        self.rect = self.image.get_rect()
        self.angle = 0

    def set_pos(self, pos, center=False):
        offset_x = 0
        offset_y = 0
        if center:
            offset_x += self.rect.w/2
            offset_y += self.rect.h/2
        self.rect.x = pos[0] - offset_x
        self.rect.y = pos[1] - offset_y

    def update(self):
      pass

    def set_rect(self,screen, rect, center=False):
        screen_size = screen.get_rect().size
        new_rect = [v * rect[i] for i,v in enumerate(screen_size+screen_size)]
        self.set_size(new_rect[2:])
        self.set_pos(new_rect[:2], center=center)

    def rotate_center(self):
        self.image = pg.transform.rotozoom(self.image, self.angle, 1)
        self.rect = self.image.get_rect(center=self.rect.center)
 
    def set_size(self, new_size):
        self.image = pg.transform.scale(self.image, [int(v) for v in new_size])
        self.rect = self.image.get_rect()

    def scale(self, ratio):
        self.set_size([self.rect.w * ratio, self.rect.h * ratio])

class Static_Sprite(Sprite):
    def __init__(self, img_name: str):
        Sprite.__init__(self,img_name)
        
class Bouncing_Sprite(Sprite):
    def __init__(self, img_name: str, amplitude: int = 5, callback=None):
        Sprite.__init__(self,img_name, callback=callback)
        self.max, self.min = amplitude,-amplitude
        self.curr_v, self.dir = 0, 1
        self.frame_skip = True

    def update(self):
        self.frame_skip = not self.frame_skip
        if self.frame_skip:
            if self.curr_v == self.max:
                self.dir *= -1
            if self.curr_v == self.min:
                self.dir *= -1
            self.curr_v += self.dir
            self.rect.y += self.dir

class Rotating_Ring(Sprite):
    def __init__(self, img_name, size):
        Sprite.__init__(self,img_name)
        self.image = pg.transform.scale(self.image, size)
        self.rect = self.image.get_rect()

    def update(self):
        self.angle = (self.angle + 3) % 360
        self.rotate_center()

class Animated_Sprite(Sprite):
    def __init__(self, img_name, callback: callable=None):
        Sprite.__init__(self, img_name, callback=callback)
        self.curr_frame = 0
        self.frame_counter = 0
        self._read_manifest()
        print("=========", self.rect)
        
    def _read_manifest(self):
        manifest_name = "sprites/" + self.img_name + '.json'
        with open(manifest_name, 'r') as f:
            self.manifest = json.load(f)
        self.frames = []
        self.nb_frames = self.manifest['nb_frames']
        self.frame_duration = self.manifest['frame_duration']
        frame_width = self.manifest['frame_width']
        for i in range(self.nb_frames):
            frame = self.image.subsurface((i*frame_width, 0, frame_width, self.rect.h))
            self.frames.append(frame)
            self.rect = frame.get_rect()
        
        
    def set_rect(self,screen, rect, center=False):
        screen_size = screen.get_rect().size
        print("screen size")
        new_rect = [v * rect[i] for i,v in enumerate(screen_size+screen_size)]
        print("NEW RECT", new_rect)
        self.rect = pg.Rect(new_rect)
        new_frames = []
        for f in self.frames:
            f = pg.transform.scale(f, [int(v) for v in new_rect[2:]])
            self.set_pos(new_rect[:2], center=center)
            offset_x = 0
            offset_y = 0
            if center:
                offset_x += f.get_rect().w/2
                offset_y += f.get_rect().h/2
            self.rect.x = new_rect[0] - offset_x
            self.rect.y = new_rect[1] - offset_y
            new_frames.append(f)
        self.frames = new_frames
        self.image = self.frames[0]

    def update(self):
        self.frame_counter+=1
        if self.curr_frame == self.nb_frames - 1 and self.callback != None:
                self.callback()
        self.frame_counter += 1
        if self.frame_counter >= self.frame_duration:
            self.frame_counter = 0
            self.curr_frame = (self.curr_frame + 1) % self.nb_frames
            self.image = self.frames[self.curr_frame]
            
class Button(Sprite):
    def __init__(self, img_name, event_manager):
        Sprite.__init__(self,img_name)
        self.event_manager = event_manager
        self.id = img_name
        self.state = 0
        self._read_manifest()

    def _read_manifest(self):
        manifest_name = "sprites/" + self.img_name + '.json'
        with open(manifest_name, 'r') as f:
            self.manifest = json.load(f)
        self.id = self.manifest['name']
        self.frame_width = self.manifest['frame_width']
        self.nb_frames = self.manifest['nb_frames']
        self.type = self.manifest['type']
        self.frames = []
        for i in range(self.nb_frames):
            frame = self.image.subsurface((i*self.frame_width, 0, self.frame_width, self.rect.h))
            self.frames.append(frame)
        self.image = self.frames[self.state]

    def clicked(self):
        if self.type == 'on-off':
            self.state = not self.state
            self.image = self.frames[self.state]
            self.event_manager.touch_input(self.id, "on" if self.state else "off")

    def set_rect(self, screen, rect, center=True):
        screen_size = screen.get_rect().size
        new_rect = [v * rect[i] for i,v in enumerate(screen_size+screen_size)]
        print('--->', new_rect)
        for i, f in enumerate(self.frames):
            self.frames[i] = pg.transform.scale(f, [int(v) for v in new_rect[2:]])
            self.set_pos(new_rect[:2], center=center)
            offset_x = 0
            offset_y = 0
            if center:
                offset_x += self.frames[i].get_rect().w/2
                offset_y += self.frames[i].get_rect().h/2
            self.rect.x = new_rect[0] - offset_x
            self.rect.y = new_rect[1] - offset_y
            
            self.image = self.frames[self.state]
            print(self.image)
