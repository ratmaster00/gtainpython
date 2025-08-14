# mini_gta_improved.py
# Improved top-down GTA-like prototype with building collisions and nicer visuals.
# Run: pip install pygame ; python mini_gta_improved.py

import pygame, random, math, sys, os
from pygame.math import Vector2

pygame.init()
SCREEN_W, SCREEN_H = 1280, 720
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
CLOCK = pygame.time.Clock()
FONT = pygame.font.SysFont(None, 22)

# Load sprites
ASSET = lambda name: os.path.join("assets", name)
PLAYER_SPRITE = pygame.image.load(ASSET("player.png")).convert_alpha()
NPC_SPRITE = pygame.image.load(ASSET("npc.png")).convert_alpha()
CAR_SPRITE = pygame.image.load(ASSET("car.png")).convert_alpha()
MARKER_SPRITE = pygame.image.load(ASSET("marker.png")).convert_alpha()
GRASS_SPRITE = pygame.image.load(ASSET("grass.png")).convert_alpha()

# Play background music
pygame.mixer.music.load(ASSET("music.mp3"))
pygame.mixer.music.play(-1)

# World
WORLD_W, WORLD_H = 6000, 4000

# Colors
GRASS_COLOR = (76, 153, 80)
ROAD_COLOR = (45, 45, 45)
ROAD_EDGE = (60, 60, 60)
PLAYER_COLOR = (50, 200, 255)
CAR_COLOR = (200, 50, 50)
NPC_COLOR = (230, 200, 60)
MARKER_COLOR = (255, 100, 255)
BUILDING_COLOR = (150, 140, 130)
BUILDING_ROOF = (170, 160, 150)
SHADOW = (0, 0, 0, 60)

def clamp(x, a, b): return max(a, min(b, x))

# Camera
class Camera:
    def __init__(self, w, h):
        self.pos = Vector2(0, 0)
        self.w, self.h = w, h
    def update(self, target_pos):
        self.pos.x = clamp(target_pos.x - self.w/2, 0, WORLD_W - self.w)
        self.pos.y = clamp(target_pos.y - self.h/2, 0, WORLD_H - self.h)
    def world_to_screen(self, world_pos):
        return world_pos - self.pos

# Player
class Player:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.speed = 300.0
        self.size = 24
        self.in_car = None
    def rect(self):
        r = pygame.Rect(0,0,self.size,self.size)
        r.center = self.pos
        return r
    def update(self, dt, keys, buildings):
        if self.in_car:
            return
        dirv = Vector2(0,0)
        if keys[pygame.K_w] or keys[pygame.K_UP]: dirv.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: dirv.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: dirv.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dirv.x += 1
        if dirv.length_squared() > 0:
            dirv = dirv.normalize()
            newpos = self.pos + dirv * self.speed * dt
            # attempt move with collision resolution
            next_rect = pygame.Rect(0,0,self.size,self.size)
            next_rect.center = newpos
            collided = False
            for b in buildings:
                if next_rect.colliderect(b.rect):
                    collided = True
                    break
            if not collided:
                self.pos = newpos
        # clamp to world
        self.pos.x = clamp(self.pos.x, 0, WORLD_W)
        self.pos.y = clamp(self.pos.y, 0, WORLD_H)
    def draw(self, surf, cam):
        s = pygame.Rect(0,0,self.size,self.size)
        s.center = cam.world_to_screen(self.pos)
        sprite = pygame.transform.scale(PLAYER_SPRITE, (self.size, self.size))
        surf.blit(sprite, s.topleft)
        pygame.draw.circle(surf, (8,8,8), s.center, 4)

# Car
class Car:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.vel = Vector2(0,0)
        self.angle = 0.0  # degrees
        self.size = Vector2(56,32)
        self.max_speed = 900.0
        self.accel = 1400.0
        self.brake = 2600.0
        self.turn_speed = 160.0
        self.friction = 0.985
        self.driver = None
    def rect(self):
        r = pygame.Rect(0,0,int(self.size.x),int(self.size.y))
        r.center = self.pos
        return r
    def update(self, dt, keys, buildings):
        # driver input
        if self.driver:
            forward = Vector2(math.cos(math.radians(self.angle)),
                              math.sin(math.radians(self.angle)))
            if keys[pygame.K_w] or keys[pygame.K_UP]:
                self.vel += forward * self.accel * dt
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                self.vel -= forward * self.brake * dt * 0.5
            # stronger turning when moving
            speed_factor = clamp(self.vel.length()/200.0, 0.15, 1.2)
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                self.angle -= self.turn_speed * dt * speed_factor
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                self.angle += self.turn_speed * dt * speed_factor
        # physics
        self.vel *= self.friction
        if self.vel.length() > self.max_speed:
            self.vel.scale_to_length(self.max_speed)
        newpos = self.pos + self.vel * dt
        # simple collision: check against buildings; if collision, push back and damp velocity
        car_rect = pygame.Rect(0,0,int(self.size.x),int(self.size.y))
        car_rect.center = newpos
        collided_any = False
        for b in buildings:
            if car_rect.colliderect(b.rect):
                collided_any = True
                # simple bounce: reverse and damp velocity
                self.vel *= -0.35
                # nudge position out along velocity negative direction
                newpos = self.pos + self.vel * dt
                break
        self.pos = Vector2(clamp(newpos.x, 0, WORLD_W), clamp(newpos.y, 0, WORLD_H))
    def draw(self, surf, cam):
        sprite = pygame.transform.rotate(
            pygame.transform.scale(CAR_SPRITE, (int(self.size.x), int(self.size.y))),
            -self.angle
        )
        r = sprite.get_rect(center=cam.world_to_screen(self.pos))
        # shadow
        shadow = pygame.Surface((sprite.get_width(), sprite.get_height()), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), shadow.get_rect())
        surf.blit(shadow, (r.left+6, r.top+8))
        surf.blit(sprite, r.topleft)
        if self.driver:
            pygame.draw.circle(surf, (8,8,8), (int(r.centerx), int(r.centery)), 4)

# NPC simple wandering
class NPC:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.speed = random.uniform(30, 110)
        self.dir = Vector2(random.uniform(-1,1), random.uniform(-1,1))
        if self.dir.length() == 0: self.dir = Vector2(1,0)
        self.dir = self.dir.normalize()
        self.timer = random.uniform(1.0, 4.0)
        self.size = 20
    def update(self, dt, buildings):
        self.timer -= dt
        if self.timer <= 0:
            self.timer = random.uniform(1.0, 4.0)
            self.dir = Vector2(random.uniform(-1,1), random.uniform(-1,1))
            if self.dir.length() == 0: self.dir = Vector2(1,0)
            self.dir = self.dir.normalize()
        newpos = self.pos + self.dir * self.speed * dt
        next_rect = pygame.Rect(0,0,self.size,self.size)
        next_rect.center = newpos
        blocked = False
        for b in buildings:
            if next_rect.colliderect(b.rect):
                blocked = True
                break
        if not blocked:
            self.pos = newpos
        self.pos.x = clamp(self.pos.x, 0, WORLD_W)
        self.pos.y = clamp(self.pos.y, 0, WORLD_H)
    def draw(self, surf, cam):
        r = pygame.Rect(0,0,self.size,self.size)
        r.center = cam.world_to_screen(self.pos)
        sprite = pygame.transform.scale(NPC_SPRITE, (self.size, self.size))
        surf.blit(sprite, r.topleft)

# Buildings with rects and simple roof highlight
class Building:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.roof_color = (clamp(BUILDING_ROOF[0] + random.randint(-10,10), 0,255),
                           clamp(BUILDING_ROOF[1] + random.randint(-10,10), 0,255),
                           clamp(BUILDING_ROOF[2] + random.randint(-10,10), 0,255))
    def draw(self, surf, cam):
        r = pygame.Rect(self.rect)
        r.topleft = cam.world_to_screen(Vector2(self.rect.left, self.rect.top))
        # base
        pygame.draw.rect(surf, BUILDING_COLOR, (r.left, r.top, r.width, r.height))
        # roof highlight
        roof = pygame.Rect(r.left+6, r.top+6, r.width-12, 16)
        pygame.draw.rect(surf, self.roof_color, roof)
    @property
    def rect(self):
        return self._rect
    @rect.setter
    def rect(self, value):
        self._rect = pygame.Rect(value)

# Simple map drawing (grass + roads + noise)
def draw_map(surf, cam, roads):
    # fill grass with sprite tiles, fixed to world position
    for x in range(0, WORLD_W, GRASS_SPRITE.get_width()):
        for y in range(0, WORLD_H, GRASS_SPRITE.get_height()):
            screen_pos = cam.world_to_screen(Vector2(x, y))
            # Only draw if on screen (for performance)
            if (0 - GRASS_SPRITE.get_width() < screen_pos.x < SCREEN_W and
                0 - GRASS_SPRITE.get_height() < screen_pos.y < SCREEN_H):
                surf.blit(GRASS_SPRITE, screen_pos)
    # draw roads
    for r in roads:
        r_s = pygame.Rect(r)
        r_s.topleft = cam.world_to_screen(Vector2(r.left, r.top))
        pygame.draw.rect(surf, ROAD_COLOR, (r_s.left, r_s.top, r.width, r.height))
        # road edge lines
        pygame.draw.rect(surf, ROAD_EDGE, (r_s.left, r_s.top, r.width, 4))
        pygame.draw.rect(surf, ROAD_EDGE, (r_s.left, r_s.top + r.height - 4, r.width, 4))
        # --- Add dashed center lines ---
        line_color = (255, 255, 100)
        if r.width > r.height:  # horizontal road
            y = r_s.top + r.height // 2
            for x in range(r_s.left + 20, r_s.left + r.width - 20, 40):
                pygame.draw.rect(surf, line_color, (x, y - 3, 24, 6))
        else:  # vertical road
            x = r_s.left + r.width // 2
            for y in range(r_s.top + 20, r_s.top + r.height - 20, 40):
                pygame.draw.rect(surf, line_color, (x - 3, y, 6, 24))
        # add noise to road
        add_noise(surf, area=(r_s.left, r_s.top, r.width, r.height), density=0.45, scale=1, cam=cam, world_fill='road')
    # subtle vignette (darker near edges)
    vignette = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for i in range(80):
        alpha = int(3)  # keep low
        pygame.draw.rect(vignette, (0,0,0,alpha), (i, i, SCREEN_W - i*2, SCREEN_H - i*2), 1)
    surf.blit(vignette, (0,0))

def add_noise(surf, area, density, scale, cam, world_fill='grass'):
    # area is in screen coordinates already
    # fill with small speckles; scale controls spot size roughly
    left, top, w, h = area
    spots = int((w*h) * 0.0005 * density)
    for _ in range(spots):
        x = random.randint(left, left + w - 1)
        y = random.randint(top, top + h - 1)
        size = random.randint(1, max(1, scale+1))
        if world_fill == 'grass':
            col = (clamp(GRASS_COLOR[0] + random.randint(-18, 18),0,255),
                   clamp(GRASS_COLOR[1] + random.randint(-18, 18),0,255),
                   clamp(GRASS_COLOR[2] + random.randint(-18, 18),0,255))
        else:
            col = (clamp(ROAD_COLOR[0] + random.randint(-12, 12),0,255),
                   clamp(ROAD_COLOR[1] + random.randint(-12, 12),0,255),
                   clamp(ROAD_COLOR[2] + random.randint(-12, 12),0,255))
        surf.fill(col, (x,y,size,size))

def dist(a,b): return (a-b).length()

def main():
    cam = Camera(SCREEN_W, SCREEN_H)
    # create buildings (rectangles)
    buildings = []
    # Add sparse grid of buildings near city center
    for rx in range(900, 1700, 320):  # wider spacing
        for ry in range(500, 1100, 260):  # wider spacing
            w = random.randint(120,180)
            h = random.randint(100,180)
            b = Building((rx + random.randint(-30,30), ry + random.randint(-30,30), w, h))
            buildings.append(b)
    # fewer scattered buildings elsewhere
    for _ in range(6):
        x = random.randint(100, WORLD_W-300)
        y = random.randint(100, WORLD_H-300)
        w = random.randint(80,180)
        h = random.randint(80,180)
        buildings.append(Building((x,y,w,h)))

    # Find a player spawn point not inside any building
    def get_valid_spawn():
        while True:
            pos = Vector2(random.randint(100, WORLD_W-1000), random.randint(100, WORLD_H-1000))
            r = pygame.Rect(0,0,24,24)
            r.center = pos
            if not any(r.colliderect(b.rect) for b in buildings):
                return pos

    player = Player(get_valid_spawn())
    car = Car((430,30))

    # Create NPCs (add this block)
    npcs = []
    for _ in range(10):  # fewer NPCs for less crowding
        while True:
            pos = Vector2(random.randint(100, WORLD_W-100), random.randint(100, WORLD_H-100))
            r = pygame.Rect(0,0,20,20)
            r.center = pos
            if not any(r.colliderect(b.rect) for b in buildings):
                npcs.append(NPC(pos))
                break

    # generate roads (Rect in world coords)
    roads = [
        pygame.Rect(0, 900, WORLD_W, 160),
        pygame.Rect(400, 0, 200, WORLD_H),
        pygame.Rect(1200, 1200, 1000, 140),
        pygame.Rect(2000, 200, 300, WORLD_H),
    ]
    marker_pos = Vector2(2200, 1600)

    # input state
    running = True
    show_debug = False

    # --- Konami code detection ---
    konami_code = [pygame.K_UP, pygame.K_UP, pygame.K_DOWN, pygame.K_DOWN,
                   pygame.K_LEFT, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_RIGHT,
                   pygame.K_b, pygame.K_a]
    konami_progress = []
    konami_active = False
    konami_timer = 0.0

    while running:
        dt = CLOCK.tick(60) / 1000.0
        e_pressed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_e:
                    e_pressed = True
                if event.key == pygame.K_F1:
                    show_debug = not show_debug

                # --- Konami code detection ---
                konami_progress.append(event.key)
                if konami_progress[-len(konami_code):] == konami_code:
                    konami_active = True
                    konami_timer = 0.0
                if len(konami_progress) > len(konami_code):
                    konami_progress = konami_progress[-len(konami_code):]
                # ----------------------------

        keys = pygame.key.get_pressed()

        # Secret crash button: hold F10 to exit
        if keys[pygame.K_F10]:
            pygame.quit()
            sys.exit()

        # Handle enter/exit on KEYDOWN E
        if e_pressed:
            # if player not in car and close enough
            if not player.in_car and dist(player.pos, car.pos) < 80:
                player.in_car = car
                car.driver = player
                # snap player's position to car (keeps consistent)
                player.pos = Vector2(car.pos)
            elif player.in_car == car:
                # exit the car to its right side
                off = Vector2(math.cos(math.radians(car.angle+90))*70,
                              math.sin(math.radians(car.angle+90))*70)
                exit_pos = car.pos + off
                # ensure exit doesn't land inside building
                exit_rect = pygame.Rect(0,0, player.size, player.size)
                exit_rect.center = exit_pos
                blocked = False
                for b in buildings:
                    if exit_rect.colliderect(b.rect):
                        blocked = True
                        break
                if blocked:
                    # try left side
                    off = Vector2(math.cos(math.radians(car.angle-90))*70,
                                  math.sin(math.radians(car.angle-90))*70)
                    exit_pos = car.pos + off
                player.pos = Vector2(clamp(exit_pos.x, 0, WORLD_W), clamp(exit_pos.y, 0, WORLD_H))
                player.in_car = None
                car.driver = None
                # small backward impulse so car doesn't instantly run player over
                car.vel *= 0.6

        # Konami effect: flashing rainbow and super speed
        if konami_active:
            konami_timer += dt
            # Flashing rainbow color
            import colorsys
            hue = (konami_timer * 2) % 1.0
            rgb = colorsys.hsv_to_rgb(hue, 1, 1)
            PLAYER_COLOR = tuple(int(c*255) for c in rgb)
            player.speed = 1200.0  # extremely fast
        else:
            PLAYER_COLOR = (50, 200, 255)
            player.speed = 300.0

        # Update
        player.update(dt, keys, buildings)
        car.update(dt, keys, buildings)
        for n in npcs: n.update(dt, buildings)

        cam_target = car.pos if player.in_car else player.pos
        cam.update(cam_target)

        # Draw view
        view = pygame.Surface((SCREEN_W, SCREEN_H))
        draw_map(view, cam, roads)

        # draw buildings (shadows + buildings)
        for b in buildings:
            # shadow
            br = pygame.Rect(b.rect)
            br.topleft = cam.world_to_screen(Vector2(b.rect.left, b.rect.top))
            shadow_rect = pygame.Rect(br.left+8, br.top+10, br.width, br.height)
            s = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
            s.fill((0,0,0,40))
            view.blit(s, (shadow_rect.left, shadow_rect.top))
        for b in buildings:
            b.draw(view, cam)

        # draw marker
        marker_rect = MARKER_SPRITE.get_rect(center=cam.world_to_screen(marker_pos))
        view.blit(MARKER_SPRITE, marker_rect.topleft)

        # draw npcs and vehicles and player
        for n in npcs: n.draw(view, cam)
        car.draw(view, cam)
        if not player.in_car:
            player.draw(view, cam)
        # If Konami active and in car, flash car too
        if konami_active and player.in_car == car:
            car_color_hue = (konami_timer * 2.5) % 1.0
            car_rgb = colorsys.hsv_to_rgb(car_color_hue, 1, 1)
            CAR_COLOR = tuple(int(c*255) for c in car_rgb)
        else:
            CAR_COLOR = (200, 50, 50)

        # HUD
        screen.blit(view, (0,0))
        fps = int(CLOCK.get_fps())
        hud_lines = [
            f'FPS: {fps}   World: {int(cam.pos.x)},{int(cam.pos.y)}   Press E to enter/exit car',
            f'Press R near marker to move it. F1 toggles debug.',
            f'Use WASD or arrows to move/drive.'
        ]
        for i, line in enumerate(hud_lines):
            txt = FONT.render(line, True, (255,255,255))
            screen.blit(txt, (8, 8 + i*20))

        '''# --- Add big transparent text in the middle ---
        big_font = pygame.font.SysFont(None, 120)
        secret_txt = big_font.render("Rockstar Games Secret", True, (255,0,0))
        secret_txt.set_alpha(80)  # half transparent
        txt_rect = secret_txt.get_rect(center=(SCREEN_W//2, SCREEN_H//2))
        screen.blit(secret_txt, txt_rect)
        # ----------------------------------------------'''

        # marker distance + teleport
        dmarker = int(dist(cam_target, marker_pos))
        mtxt = FONT.render(f'Distance to marker: {dmarker}', True, (255,255,255))
        screen.blit(mtxt, (8, 72))
        if dmarker < 100:
            win = FONT.render("Mission: Reached marker! Press R to teleport it elsewhere.", True, (255,255,255))
            screen.blit(win, (8,96))
            if keys[pygame.K_r]:
                marker_pos.x = random.randint(200, WORLD_W-200)
                marker_pos.y = random.randint(200, WORLD_H-200)

        # Debug overlay (optional)
        if show_debug:
            # draw building rects
            for b in buildings:
                br = pygame.Rect(b.rect)
                br.topleft = cam.world_to_screen(Vector2(b.rect.left, b.rect.top))
                pygame.draw.rect(screen, (255,0,0), br, 1)
            pr = player.rect()
            pr_screen = pr.copy()
            pr_screen.center = cam.world_to_screen(pr.center)
            pygame.draw.rect(screen, (0,0,255), pr_screen, 1)
            cr = car.rect()
            cr_screen = cr.copy()
            cr_screen.center = cam.world_to_screen(cr.center)
            pygame.draw.rect(screen, (255,255,0), cr_screen, 1)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
