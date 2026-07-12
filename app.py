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

# Planet scenes (used for the random-on-shake jump)
PLANETS = {
    "Mercury", "Venus", "Earth", "Mars", "Jupiter",
    "Saturn", "Uranus", "Neptune", "Pluto",
}

# Splash text shown on launch
INTRO_TEXT = (
    "Can be used as a companion app to Nibula the pen plotter. "
    "Cycle through the space objects with B/E buttons. "
    "Choose an object with C and scan your QR code with Nibula's scanner."
    "\n"
    "Press C to continue."
)

# ---- QR Codes for each object ----
# Pre-computed QR codes so the badge never runs an encoder.
# EMF-A-####  (Mercury = EMF-A-0001 ... Rocket = EMF-A-0012).
# Each row is a 21-bit int: bit 20 = left column, bit 0 = right column
QR_SIZE = 21                # modules per side
QR_MOD = 7                  # on-screen pixels per module (147px code)

QR_ROWS = [
    (2083967, 1071681, 1527389, 1525341, 1529181, 1068353, 2086271, 1792, 1395221, 988258, 121118, 374862, 93532, 3759, 2083541, 1065888, 1531611, 1524846, 1526033, 1072231, 2082133),  # EMF-A-0001  Mercury
    (2085759, 1065537, 1531229, 1525085, 1526621, 1072961, 2086271, 1280, 1338437, 69320, 1730484, 1876692, 1268726, 1029, 2081919, 1071370, 1524849, 1526468, 1530811, 1068749, 2088959),  # EMF-A-0002  Venus
    (2086527, 1069889, 1530461, 1524317, 1530717, 1067073, 2086271, 3072, 1309305, 1226653, 1398566, 1126888, 163830, 6594, 2081334, 1067103, 1531107, 1526232, 1530811, 1070858, 2085302),  # EMF-A-0003  Earth
    (2085247, 1071937, 1529181, 1527389, 1531741, 1066049, 2086271, 1024, 1307257, 1450909, 1823526, 1392088, 1998806, 7618, 2082358, 1068127, 1528035, 1527256, 1529787, 1070858, 2086326),  # EMF-A-0004  Mars
    (2086015, 1071937, 1527901, 1526877, 1530717, 1066049, 2086271, 3072, 1308281, 1085341, 1951526, 600568, 1006550, 4546, 2081334, 1067103, 1531107, 1526232, 1529787, 1072906, 2087350),  # EMF-A-0005  Jupiter
    (2085247, 1071425, 1530205, 1525085, 1531741, 1068097, 2086271, 1024, 1309305, 1327005, 840486, 1743304, 1558486, 4546, 2082358, 1067103, 1531107, 1527256, 1531835, 1070858, 2087350),  # EMF-A-0006  Saturn
    (2087551, 1067329, 1527645, 1530973, 1528157, 1071681, 2086271, 4864, 1143377, 1816335, 2085491, 1344716, 355822, 7618, 2085304, 1070898, 1530441, 1531651, 1527420, 1065205, 2087367),  # EMF-A-0007  Uranus
    (2082431, 1066817, 1530973, 1529693, 1529181, 1072705, 2086271, 5120, 1557053, 11244, 745839, 958432, 1145149, 289, 2085540, 1069102, 1528490, 1530848, 1529184, 1068009, 2082084),  # EMF-A-0008  Neptune
    (2084735, 1070145, 1525085, 1525341, 1531229, 1068353, 2086271, 3840, 1395221, 1975394, 682270, 665678, 475468, 3759, 2083541, 1066912, 1528539, 1526894, 1526033, 1069159, 2082133),  # EMF-A-0009  Pluto
    (2083967, 1070401, 1526365, 1524829, 1529181, 1066305, 2086271, 768, 1395221, 2034786, 389406, 1642574, 614764, 1727, 2083541, 1065888, 1529563, 1525870, 1525009, 1069159, 2082133),  # EMF-A-0010  Sun
    (2085759, 1068353, 1530205, 1525597, 1526621, 1070913, 2086271, 256, 1338437, 1119944, 1986484, 2772, 1791942, 3093, 2081919, 1071370, 1526897, 1525444, 1529787, 1065677, 2088959),  # EMF-A-0011  Moon
    (2087039, 1068097, 1527133, 1530717, 1528157, 1070657, 2086271, 5888, 1144401, 756495, 289395, 2068684, 654846, 4562, 2085304, 1069874, 1531465, 1528579, 1525372, 1066229, 2088391),  # EMF-A-0012  Rocket
]

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
        self.show_qr = False     # True while the scannable QR is on screen
        self.show_intro = True   # splash/instructions shown on launch
        self._intro_lines = None # cached wrapped splash text (built on first draw)
        self.planet_indices = [
            i for i, s in enumerate(self.scenes) if s.name in PLANETS
        ]
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
        # Tint all 12 LEDs to colours and dim to defined brightness
        colour = tuple(int(c * LED_BRIGHTNESS) for c in tint)
        for led in range(1, 13):
            tildagonos.leds[led] = colour
        tildagonos.leds.write()

    def _set_leds_white(self):
        # Full-brightness white ring (LEDs 1-12) to illuminate the QR for scanning
        for led in range(1, 13):
            tildagonos.leds[led] = (255, 255, 255)
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

    def _random_planet(self):
        # Jump to a random planet (avoid repeating the current one if possible)
        choices = [i for i in self.planet_indices if i != self.index]
        if not choices:
            choices = self.planet_indices
        self._show(random.choice(choices))

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

        if self.show_intro:
            if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
                self.button_states.clear()
                self.show_intro = False  # C dismisses the splash into the scenes
            self._set_leds(self.scenes[self.index].tint)
            return

        if self.button_states.get(BUTTON_TYPES["RIGHT"]):
            self.button_states.clear()
            self._advance(1)
        if self.button_states.get(BUTTON_TYPES["LEFT"]):
            self.button_states.clear()
            self._advance(-1)
        if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
            self.button_states.clear()
            self.show_qr = not self.show_qr   # toggle the scannable QR overlay
            self.frames = 0                   # reset dwell so exit does not jump

        if self.show_qr:
            self._set_leds_white()       # Set LEDs to white when QR code is diaplayed
            return                       

        if self._shaken():
            self._random_planet()        # shake jumps to a random planet

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
        if self.show_intro:
            self._draw_intro(ctx)
            return
        if self.show_qr:
            self._draw_qr(ctx)
            return

        clear_background(ctx)
        scene = self.scenes[self.index]

        ctx.save()
        scene.draw(ctx)
        ctx.restore()

        if scene.captioned:
            self._draw_caption(ctx, scene.name)


    def _draw_qr(self, ctx):
        rows = QR_ROWS[self.index]
        span = QR_SIZE * QR_MOD
        origin = -span // 2
        ctx.rgb(1, 1, 1).rectangle(-120, -120, 240, 240).fill()
        ctx.rgb(0, 0, 0)
        for r in range(QR_SIZE):
            bits = rows[r]
            y = origin + r * QR_MOD
            c = 0
            while c < QR_SIZE:
                if (bits >> (QR_SIZE - 1 - c)) & 1:
                    run = 1
                    while c + run < QR_SIZE and (bits >> (QR_SIZE - 1 - (c + run))) & 1:
                        run += 1
                    ctx.rectangle(origin + c * QR_MOD, y, run * QR_MOD, QR_MOD).fill()
                    c += run
                else:
                    c += 1

    @staticmethod
    def _wrap(ctx, text, max_width):
        lines = []
        line = ""
        for word in text.split():
            trial = word if not line else line + " " + word
            if ctx.text_width(trial) <= max_width:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    def _build_intro_lines(self, ctx):
        ctx.font = ctx.get_font_name(0)
        max_width = 150
        paragraphs = INTRO_TEXT.split("\n")
        wrapped = []
        for font_size in (16, 15, 14, 13, 12, 11, 10):
            ctx.font_size = font_size
            line_height = font_size + 3
            wrapped = []
            for i, para in enumerate(paragraphs):
                if i:
                    wrapped.append("")       
                wrapped.extend(self._wrap(ctx, para, max_width))
            if len(wrapped) * line_height <= 176:   
                self._intro_lines = (wrapped, font_size)
                return
        self._intro_lines = (wrapped, 10)           

    def _draw_intro(self, ctx):
        clear_background(ctx)
        ctx.save()
        if self._intro_lines is None:
            self._build_intro_lines(ctx)
        lines, font_size = self._intro_lines
        line_height = font_size + 3

        ctx.font = ctx.get_font_name(0)
        ctx.font_size = font_size
        ctx.rgb(1, 1, 1)
        y = -(len(lines) - 1) * line_height / 2
        for ln in lines:
            if ln:
                ctx.move_to(-ctx.text_width(ln) / 2, y)
                ctx.text(ln)
            y += line_height
        ctx.restore()


__app_export__ = SpaceManApp
