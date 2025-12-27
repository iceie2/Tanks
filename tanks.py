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
    
    def shoot(self):
        barrel_end_x = self.x + self.barrel_length * math.cos(math.radians(self.angle))
        barrel_end_y = self.y - self.barrel_length * math.sin(math.radians(self.angle))
        vel_x = 5 * math.cos(math.radians(self.angle))
        vel_y = -5 * math.sin(math.radians(self.angle))
        return Bullet(barrel_end_x, barrel_end_y, vel_x, vel_y)

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
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and turn == "player":
                bullets.append(player.shoot())
                turn = "enemy"
                turn_timer = 0
    
    # Update
    player_keys = keys if turn == "player" else None
    player.update(terrain, player_keys)
    enemy.update(terrain)  # keys=None on purpose

    
    # Enemy AI (simple random shoot)
    if turn == "enemy":
        turn_timer += 1
        if turn_timer > TURN_TIME:
            enemy.angle = random.randint(0, 180)
            bullets.append(enemy.shoot())
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
    
    pygame.display.flip()