import pygame
import math
import random

pygame.init()

# Screen setup
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Tanks")
clock = pygame.time.Clock()
FPS = 60

# Colors
BLACK = pygame.Color(0, 0, 0)
WHITE = pygame.Color(255, 255, 255)
BROWN = pygame.Color(101, 67, 33)
GRAY = pygame.Color(50, 50, 50)
RED = pygame.Color(255, 0, 0)
GREEN = pygame.Color(0, 200, 0)

# Gravity
GRAVITY = 0.3
GROUND_HEIGHT = 100
MAX_STEP_UP = 8
MOVE_SPEED = 3

FUEL_PER_TURN = 100
FUEL_COST_PER_PIXEL = 1

UI_BG = pygame.Color(25, 25, 25)
UI_BORDER = pygame.Color(200, 200, 200)
UI_TEXT = pygame.Color(240, 240, 240)
UI_HILITE = pygame.Color(70, 70, 70)

scheduled_bullets = []  # list of (fire_time_ms, Bullet)
THREE_SHOT_DELAY_MS = 120

WEAPONS = ["Basic Shell", "Three Shot"]  # add more later
selected_weapon = 0
weapons_open = False

font_ui = pygame.font.Font(None, 22)

PANEL_W, PANEL_H = 220, 180
panel_rect = pygame.Rect(SCREEN_WIDTH - PANEL_W - 10, 10, PANEL_W, PANEL_H)

button_rect = pygame.Rect(0, 0, 110, 26)
button_rect.topright = (SCREEN_WIDTH - 10, 10)  # top-right


class Terrain:
    def __init__(self):
        self.surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.surface.fill(BLACK)
        self.draw_ground()
    
    def draw_ground(self):
        self.surface.fill(BLACK)

        base_y = SCREEN_HEIGHT - GROUND_HEIGHT
        heights = self.generate_midpoint_heights(
            SCREEN_WIDTH,
            base_y=base_y,
            amplitude=140,
            roughness=0.55
        )

        for x, y in enumerate(heights):
            pygame.draw.line(self.surface, BROWN, (x, y), (x, SCREEN_HEIGHT))

    def generate_midpoint_heights(self, width, base_y, amplitude=140, roughness=0.55):
        # Make size = 2^n + 1 (good for midpoint displacement)
        n = 1
        while n < width - 1:
            n *= 2
        size = n + 1

        heights = [None] * size
        heights[0] = base_y + random.uniform(-amplitude, amplitude)
        heights[-1] = base_y + random.uniform(-amplitude, amplitude)

        def subdivide(left, right, disp):
            mid = (left + right) // 2
            if mid == left or mid == right:
                return
            avg = (heights[left] + heights[right]) / 2.0
            heights[mid] = avg + random.uniform(-disp, disp)
            subdivide(left, mid, disp * roughness)
            subdivide(mid, right, disp * roughness)

        subdivide(0, size - 1, amplitude)

        # Fill any Nones by linear interpolation (just in case)
        last_i = 0
        for i in range(1, size):
            if heights[i] is not None:
                a_i, b_i = last_i, i
                a, b = heights[a_i], heights[b_i]
                span = b_i - a_i
                for j in range(a_i + 1, b_i):
                    t = (j - a_i) / span
                    heights[j] = a + (b - a) * t
                last_i = i
        # Downsample/crop to screen width and clamp into view
        out = []
        for x in range(width):
            src_i = int(x * (size - 1) / (width - 1))
            y = int(heights[src_i])
            y = max(80, min(y, SCREEN_HEIGHT - 40))
            out.append(y)
        return out
    
    def destroy_at(self, x, y, radius=20):
        pygame.draw.circle(self.surface, BLACK, (int(x), int(y)), radius)
    
    def get_ground_y(self, x):
        x = int(x)
        if not (0 <= x < SCREEN_WIDTH):
            return SCREEN_HEIGHT
        for y in range(SCREEN_HEIGHT):
            if self.surface.get_at((x, y)) != BLACK:
                return y
        
        return SCREEN_HEIGHT
    
    def is_solid(self, x, y):
        x, y = int(x), int(y)
        if 0 <= x < SCREEN_WIDTH and 0 <= y < SCREEN_HEIGHT:
            return self.surface.get_at((x, y)) != BLACK
        return False

class Tank:
    def __init__(self, x, y, is_player=True):
        self.x = x
        self.y = y
        self.fuel = FUEL_PER_TURN
        self.is_player = is_player
        self.width = 30
        self.height = 20
        self.angle = 45 if is_player else 135
        self.health = 100
        self.vel_y = 0
        self.color = GREEN if is_player else RED
        self.barrel_length = 25
    
    def update(self, terrain, keys=None):
    # --- Player-only input (keys can be None for enemy) ---
        if self.is_player and keys is not None:
            # Horizontal move that can climb small bumps
            dx = 0
            if keys[pygame.K_a]:
                dx -= MOVE_SPEED
            if keys[pygame.K_d]:
                dx += MOVE_SPEED

            if self.fuel <= 0:
                dx = 0

            if dx != 0:
                max_dx = self.fuel
                dx = max(-max_dx, min(dx, max_dx))
                old_x, old_y = self.x, self.y

                # try the move
                self.x += dx
                self.x = max(self.width // 2, min(self.x, SCREEN_WIDTH - self.width // 2))

                moved_pixels = abs(int(self.x - old_x))
                if moved_pixels > 0:
                    self.fuel -= moved_pixels * FUEL_COST_PER_PIXEL
                    self.fuel = max(0, self.fuel)

                # ground at new X
                check_xs = [int(self.x - self.width // 3), int(self.x), int(self.x + self.width // 3)]
                new_ground_y = max(terrain.get_ground_y(px) for px in check_xs)
                target_y = new_ground_y - self.height // 2

                # climb small step or cancel if too steep
                if target_y < self.y:
                    if (self.y - target_y) <= MAX_STEP_UP:
                        self.y = target_y
                        self.vel_y = 0
                    else:
                        self.x, self.y = old_x, old_y
                else:
                    # going down: stick to ground (arcade feel)
                    self.y = target_y
                    self.vel_y = 0

            # aiming (player only)
            if keys[pygame.K_w]:
                self.angle = min(self.angle + 2, 180)
            if keys[pygame.K_s]:
                self.angle = max(self.angle - 2, 0)

        # --- Gravity / vertical snap (runs for both player + enemy) ---
        self.x = max(self.width // 2, min(self.x, SCREEN_WIDTH - self.width // 2))

        check_points = [int(self.x - self.width // 3), int(self.x), int(self.x + self.width // 3)]
        ground_y = max(terrain.get_ground_y(px) for px in check_points)
        tank_bottom = self.y + self.height // 2

        if tank_bottom < ground_y:
            self.vel_y += GRAVITY
            self.vel_y = min(self.vel_y, 10)
            self.y += self.vel_y

            tank_bottom = self.y + self.height // 2
            ground_y = max(terrain.get_ground_y(px) for px in check_points)

        if tank_bottom >= ground_y:
            self.y = ground_y - self.height // 2
            self.vel_y = 0
    
    def start_turn(self):
        self.fuel = FUEL_PER_TURN


    def draw(self, surface):
        # Body
        pygame.draw.rect(surface, self.color, (self.x - self.width // 2, self.y - self.height // 2, self.width, self.height))
        
        # Barrel
        barrel_end_x = self.x + self.barrel_length * math.cos(math.radians(self.angle))
        barrel_end_y = self.y - self.barrel_length * math.sin(math.radians(self.angle))
        pygame.draw.line(surface, self.color, (self.x, self.y), (barrel_end_x, barrel_end_y), 5)
    
    def shoot(self, weapon_name):
        barrel_end_x = self.x + self.barrel_length * math.cos(math.radians(self.angle))
        barrel_end_y = self.y - self.barrel_length * math.sin(math.radians(self.angle))

        speed = 5

        def make_bullet(angle_deg):
            vx = speed * math.cos(math.radians(angle_deg))
            vy = -speed * math.sin(math.radians(angle_deg))
            return Bullet(barrel_end_x, barrel_end_y, vx, vy)
        
        now = pygame.time.get_ticks()
        
        if weapon_name == "Three Shot":
            spread = 1
            angels = [self.angle - spread, self.angle, self.angle + spread]

            for i, ang in enumerate(angels):
                fire_time = now + i * THREE_SHOT_DELAY_MS
                scheduled_bullets.append((fire_time, make_bullet(ang))) 
            return []
        return [make_bullet(self.angle)]
class Bullet:
    def __init__(self, x, y, vel_x, vel_y):
        self.x = x
        self.y = y
        self.vel_x = vel_x
        self.vel_y = vel_y
        self.radius = 4
        self.alive = True
    
    def update(self, terrain):
        self.vel_y += GRAVITY
        self.x += self.vel_x
        self.y += self.vel_y
        
        # Terrain collision
        if terrain.is_solid(self.x, self.y):
            self.alive = False
            terrain.destroy_at(self.x, self.y, radius=15)
        
        # Screen bounds
        if self.x < 0 or self.x > SCREEN_WIDTH or self.y > SCREEN_HEIGHT:
            self.alive = False
    
    def draw(self, surface):
        pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), self.radius)

# Game state
terrain = Terrain()
print(terrain.surface.get_at((10, 10)))
print(terrain.surface.get_at((10, SCREEN_HEIGHT-10)))
player = Tank(150, SCREEN_HEIGHT - GROUND_HEIGHT - 40, is_player=True)
enemy = Tank(SCREEN_WIDTH - 150, SCREEN_HEIGHT - GROUND_HEIGHT - 40, is_player=False)
bullets = []
turn = "player"  # "player" or "enemy"
turn_timer = 0
TURN_TIME = 300  # 5 seconds at 60 FPS

running = True
while running:
    clock.tick(FPS)
    keys = pygame.key.get_pressed()

    now = pygame.time.get_ticks()  # [web:306]
    for fire_time, b in scheduled_bullets[:]:
        if now >= fire_time:
            bullets.append(b)
            scheduled_bullets.remove((fire_time, b))
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and turn == "player":
                bullets.extend(player.shoot(WEAPONS[selected_weapon]))
                turn = "enemy"
                turn_timer = 0
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            if button_rect.collidepoint((mx, my)):
                weapons_open = not weapons_open

            elif weapons_open and panel_rect.collidepoint((mx, my)):
                list_top = panel_rect.y + 40
                item_h = 26
                for i, name in enumerate(WEAPONS):
                    item_rect = pygame.Rect(panel_rect.x + 10, list_top + i * item_h, panel_rect.w - 20, item_h)
                    if item_rect.collidepoint((mx, my)):
                        selected_weapon = i
                        weapons_open = False
                        break

    
    # Update
    player_keys = keys if turn == "player" else None
    player.update(terrain, player_keys)
    enemy.update(terrain)  # keys=None on purpose

    
    # Enemy AI (simple random shoot)
    if turn == "enemy":
        turn_timer += 1
        if turn_timer > TURN_TIME:
            enemy.angle = random.randint(0, 180)
            bullets.extend(enemy.shoot("Basic Shell"))
            turn = "player"
            turn_timer = 0
    
    # Update bullets
    for bullet in bullets[:]:
        bullet.update(terrain)
        if not bullet.alive:
            bullets.remove(bullet)
    
    # Draw
    screen.fill(BLACK)
    screen.blit(terrain.surface, (0, 0))
    player.draw(screen)
    enemy.draw(screen)
    for bullet in bullets:
        bullet.draw(screen)
    
    # Draw UI
    font = pygame.font.Font(None, 24)
    turn_text = font.render(f"Turn: {turn.upper()}", True, WHITE)
    health_text = font.render(f"P: {player.health} | E: {enemy.health}", True, WHITE)
    fuel_text = font.render(f"Fuel: {player.fuel}", True, WHITE)
    controls_text = font.render("WASD: Move/Aim | SPACE: Shoot", True, WHITE)
    screen.blit(turn_text, (10, 10))
    screen.blit(health_text, (10, 40))
    screen.blit(fuel_text, (10, 70))
    screen.blit(controls_text, (10, SCREEN_HEIGHT - 30))

        # Weapons button
    pygame.draw.rect(screen, UI_BG, button_rect, border_radius=6)
    pygame.draw.rect(screen, UI_BORDER, button_rect, 2, border_radius=6)
    screen.blit(font_ui.render("Weapons", True, UI_TEXT), (button_rect.x + 10, button_rect.y + 5))

    # Weapons panel (dropdown)
    if weapons_open:
        pygame.draw.rect(screen, UI_BG, panel_rect, border_radius=8)
        pygame.draw.rect(screen, UI_BORDER, panel_rect, 2, border_radius=8)

        screen.blit(font_ui.render("Select weapon:", True, UI_TEXT), (panel_rect.x + 10, panel_rect.y + 12))

        list_top = panel_rect.y + 40
        item_h = 26
        mx, my = pygame.mouse.get_pos()

        for i, name in enumerate(WEAPONS):
            item_rect = pygame.Rect(panel_rect.x + 10, list_top + i * item_h, panel_rect.w - 20, item_h)
            hovered = item_rect.collidepoint((mx, my))
            if hovered or i == selected_weapon:
                pygame.draw.rect(screen, UI_HILITE, item_rect, border_radius=6)

            screen.blit(font_ui.render(name, True, UI_TEXT), (item_rect.x + 8, item_rect.y + 5))

    
    pygame.display.flip()