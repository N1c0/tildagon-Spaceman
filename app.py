import app
import math
import random

from collections import namedtuple

from app_components import clear_background
from events.input import Buttons, BUTTON_TYPES
from tildagonos import tildagonos
from system.eventbus import eventbus
from system.patterndisplay.events import PatternDisable, PatternEnable

try:
    import imu
except ImportError:
    imu = None              # Old firmware fails on shake. If error, ignore action

TAU = 2 * math.pi           
R = 66                      # Default body radius
BG = (0.0, 0.0, 0.0)        

FRAMES_PER_SCENE = 60       
SHAKE_THRESHOLD = 20        
SHAKE_COOLDOWN = 20        

STAR_FIELD_RADIUS = 108     # Star nonsense. Configurable
STAR_COUNT_MIN = 20         
STAR_COUNT_MAX = 30         
STAR_BIG_CHANCE = 0.3       
TWINKLE_SPEED = 0.2         
STAR_DIM = 0.6              
STAR_BRIGHT = 1.0           

LED_BRIGHTNESS = 0.28       

Scene = namedtuple("Scene", ("name", "draw", "captioned", "tint"))


class SpaceManApp(app.App):
    def __init__(self):
        self.button_states = Buttons(self)
        self.scenes = [
            Scene("Mercury", self.draw_mercury, True, (150, 150, 150)),
            Scene("Venus", self.draw_venus, True, (220, 180, 110)),
            Scene("Earth", self.draw_earth, True, (40, 120, 220)),
            Scene("Mars", self.draw_mars, True, (210, 80, 40)),
            Scene("Jupiter", self.draw_jupiter, True, (220, 170, 120)),
            Scene("Saturn", self.draw_saturn, True, (225, 195, 120)),
            Scene("Uranus", self.draw_uranus, True, (140, 210, 215)),
            Scene("Neptune", self.draw_neptune, True, (50, 90, 210)),
            Scene("Pluto", self.draw_pluto, True, (185, 160, 135)),
            Scene("Sun", self.draw_sun, False, (255, 190, 40)),
            Scene("Moon", self.draw_moon, False, (200, 200, 215)),
            Scene("Rocket", self.draw_rocket, False, (220, 60, 45)),
        ]
        self.index = 0
        self.frames = 0          
        self.last_acc = None     
        self.cooldown = 0        
        self.ticks = 0           
        self.leds_owned = False  
        # Each scene with a sky gets a random scatter
        self.moon_stars = self._make_stars()
        self.rocket_stars = self._make_stars()

    def _make_stars(self):
        # Build a random stars
        stars = []
        for _ in range(random.randint(STAR_COUNT_MIN, STAR_COUNT_MAX)):
            angle = random.random() * TAU
            # sqrt() spreads stars evenly across the disc instead of bunching them toward the centre.
            dist = STAR_FIELD_RADIUS * math.sqrt(random.random())
            x = dist * math.cos(angle)
            y = dist * math.sin(angle)
            size = 2 if random.random() < STAR_BIG_CHANCE else 1
            phase = random.random() * TAU
            stars.append((x, y, size, phase))
        return stars

    # ---------- LEDs ----------

    def _set_leds(self, tint):
        # Tint all 12 LEDs to colors and dim to defined brightness
        colour = tuple(int(c * LED_BRIGHTNESS) for c in tint)
        for led in range(1, 13):
            tildagonos.leds[led] = colour
        tildagonos.leds.write()

    def _release_leds(self):
        # Return LEDs to selected patten on exit
        if self.leds_owned:
            eventbus.emit(PatternEnable())
            self.leds_owned = False

    # ---------- navigation ----------

    def _show(self, index):
        self.index = index % len(self.scenes)
        self.frames = 0

    def _advance(self, step):
        self._show(self.index + step)

    def _shaken(self):
        
        if imu is None:
            return False
        if self.cooldown > 0:
            self.cooldown -= 1
            if self.cooldown == 0:
                self.last_acc = None     # start clean once the cooldown ends
            return False

        acc = imu.acc_read()
        if not acc:
            return False

        jolted = False
        if self.last_acc is not None:
            dx = acc[0] - self.last_acc[0]
            dy = acc[1] - self.last_acc[1]
            dz = acc[2] - self.last_acc[2]
            if math.sqrt(dx * dx + dy * dy + dz * dz) > SHAKE_THRESHOLD:
                jolted = True
                self.cooldown = SHAKE_COOLDOWN
        self.last_acc = acc
        return jolted

    def update(self, delta):
        self.ticks += 1                  # advances the star twinkle

        if not self.leds_owned:
            eventbus.emit(PatternDisable())   # take the LEDs from the default pattern
            self.leds_owned = True

        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear()
            self._release_leds()         # Go back to set LED pattern before exiting app
            self.minimise()              
            return

        if self.button_states.get(BUTTON_TYPES["RIGHT"]):
            self.button_states.clear()
            self._advance(1)
        if self.button_states.get(BUTTON_TYPES["LEFT"]):
            self.button_states.clear()
            self._advance(-1)

        if self._shaken():
            self._show(0)                # shake jumps back to start

        self.frames += 1
        if self.frames >= FRAMES_PER_SCENE:
            self._advance(1)             # auto-advance 

        self._set_leds(self.scenes[self.index].tint)

    # ---------- drawing helpers ----------

    def disc(self, ctx, r, g, b, radius=R, x=0, y=0):
        ctx.rgb(r, g, b).arc(x, y, radius, 0, TAU, True).fill()

    def ellipse(self, ctx, r, g, b, rx, ry, x=0, y=0):
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(1, ry / rx)
        self.disc(ctx, r, g, b, rx)
        ctx.restore()

    def polygon(self, ctx, points):
        ctx.begin_path()
        ctx.move_to(*points[0])
        for x, y in points[1:]:
            ctx.line_to(x, y)
        ctx.close_path()
        ctx.fill()

    def draw_stars(self, ctx, stars):
        for x, y, size, phase in stars:
            wave = 0.5 + 0.5 * math.sin(self.ticks * TWINKLE_SPEED + phase)
            b = STAR_DIM + (STAR_BRIGHT - STAR_DIM) * wave
            self.disc(ctx, b, b, b, size, x, y)

    # ---------- the scenes ----------

    def draw_mercury(self, ctx):
        self.disc(ctx, 0.55, 0.55, 0.55)
        self.disc(ctx, 0.42, 0.42, 0.42, 13, -25, -15)  # craters
        self.disc(ctx, 0.46, 0.46, 0.46, 17, 22, 20)
        self.disc(ctx, 0.40, 0.40, 0.40, 8, 8, -32)

    def draw_venus(self, ctx):
        self.disc(ctx, 0.86, 0.72, 0.42)
        self.disc(ctx, 0.93, 0.83, 0.55, 30, -20, -18)  # cloud swirls
        self.disc(ctx, 0.78, 0.63, 0.36, 24, 26, 28)

    def draw_earth(self, ctx):
        self.disc(ctx, 0.10, 0.36, 0.80)                # ocean
        self.disc(ctx, 0.16, 0.55, 0.22, 22, -22, -8)   # continents
        self.disc(ctx, 0.16, 0.55, 0.22, 18, 26, 20)
        self.disc(ctx, 0.20, 0.60, 0.26, 12, 4, 42)
        self.disc(ctx, 0.92, 0.92, 0.96, 12, 0, -50)    # polar ice

    def draw_mars(self, ctx):
        self.disc(ctx, 0.76, 0.30, 0.15)
        self.disc(ctx, 0.60, 0.22, 0.10, 18, 22, -10)   # dark regions
        self.disc(ctx, 0.55, 0.20, 0.10, 14, -26, 26)
        self.disc(ctx, 0.95, 0.95, 0.95, 10, 0, 50)     # polar cap

    def draw_jupiter(self, ctx):
        self.disc(ctx, 0.85, 0.70, 0.50)
        bands = [
            (-30, 48, 7, (0.70, 0.50, 0.35)),
            (-15, 58, 7, (0.92, 0.80, 0.60)),
            (0, 62, 8, (0.70, 0.50, 0.35)),
            (15, 58, 7, (0.92, 0.80, 0.60)),
            (30, 48, 7, (0.70, 0.50, 0.35)),
        ]
        for y, rx, ry, (r, g, b) in bands:
            self.ellipse(ctx, r, g, b, rx, ry, 0, y)
        self.ellipse(ctx, 0.80, 0.30, 0.20, 11, 8, 24, 12)  # Red Spot

    def draw_saturn(self, ctx):
        self.ellipse(ctx, 0.80, 0.70, 0.45, 96, 35)
        self.ellipse(ctx, *BG, 62, 22)
        self.disc(ctx, 0.88, 0.78, 0.50, 50)
        self.disc(ctx, 0.80, 0.68, 0.42, 38, 0, -14)    

    def draw_uranus(self, ctx):
        self.disc(ctx, 0.55, 0.80, 0.82)
        self.disc(ctx, 0.63, 0.86, 0.87, 32, -14, -16)

    def draw_neptune(self, ctx):
        self.disc(ctx, 0.20, 0.35, 0.80)
        self.disc(ctx, 0.30, 0.46, 0.92, 22, -20, -20)
        self.disc(ctx, 0.14, 0.27, 0.68, 16, 20, 14)    # dark spot

    def draw_pluto(self, ctx):                          # ikik, I couldn't leave it out though                         
        self.disc(ctx, 0.72, 0.63, 0.52, 46)
        self.disc(ctx, 0.60, 0.50, 0.42, 16, 12, 10)

    def draw_sun(self, ctx):
        self.disc(ctx, 1.00, 0.65, 0.00, 72)   
        self.disc(ctx, 1.00, 0.80, 0.10, 58)   
        self.disc(ctx, 1.00, 0.92, 0.45, 32)   

    def draw_moon(self, ctx):
        self.draw_stars(ctx, self.moon_stars)
        self.disc(ctx, 0.82, 0.82, 0.85, 60)
        self.disc(ctx, 0.68, 0.68, 0.72, 14, -22, -14)  
        self.disc(ctx, 0.72, 0.72, 0.76, 18, 20, 18)
        self.disc(ctx, 0.66, 0.66, 0.70, 9, 12, -28)
        self.disc(ctx, 0.70, 0.70, 0.74, 7, -28, 24)

    def draw_rocket(self, ctx):
        self.draw_stars(ctx, self.rocket_stars)
        ctx.rgb(1.00, 0.55, 0.00)
        self.polygon(ctx, [(-12, 45), (12, 45), (0, 80)])     # outer flame
        ctx.rgb(1.00, 0.85, 0.20)
        self.polygon(ctx, [(-6, 45), (6, 45), (0, 64)])       # inner flame
        ctx.rgb(0.80, 0.20, 0.15)
        self.polygon(ctx, [(-18, 28), (-40, 54), (-18, 54)])  # left fin
        self.polygon(ctx, [(18, 28), (40, 54), (18, 54)])     # right fin
        ctx.rgb(0.90, 0.90, 0.92).round_rectangle(-18, -42, 36, 96, 14).fill()
        ctx.rgb(0.80, 0.20, 0.15)
        self.polygon(ctx, [(-18, -42), (18, -42), (0, -78)])  # nose cone
        self.disc(ctx, 0.30, 0.55, 0.85, 11, 0, -16)          # window
        self.disc(ctx, 0.55, 0.75, 0.95, 6, 0, -16)           # window glint

    # ---------- the screen ----------

    def _draw_caption(self, ctx, name):
        ctx.save()
        ctx.font = ctx.get_font_name(0)
        ctx.font_size = 28
        ctx.move_to(-ctx.text_width(name) / 2, 100)
        ctx.rgb(1, 1, 1).text(name)
        ctx.restore()

    def draw(self, ctx):
        clear_background(ctx)
        scene = self.scenes[self.index]

        ctx.save()
        scene.draw(ctx)
        ctx.restore()

        if scene.captioned:
            self._draw_caption(ctx, scene.name)


__app_export__ = SpaceManApp
