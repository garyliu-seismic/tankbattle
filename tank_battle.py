"""
坦克大战 (Tank Battle) - 使用 pygame 实现

操作方式:
    方向键 / WASD : 移动坦克
    空格 / J      : 发射子弹
    P             : 暂停 / 继续
    Enter         : 开局 / 重新开始
    Esc           : 退出

目标:
    保护你的基地(屏幕下方中间的鹰标), 击溃每一关的敌方坦克。
    共 10 关, 难度递增; 击毁敌人有几率掉落道具。

地图元素:
    #  砖墙(可击碎)   -  钢墙(不可击碎)   ~  水域(坦克不可过, 子弹可越)
    *  草丛(可藏身)   /  冰面(打滑)
"""

import argparse
import random
import sys

import pygame

from levels import LEVELS, TOTAL_LEVELS, ENEMY_TYPES, POWERUP_KINDS

# --------------- 基础配置 ---------------
WIDTH, HEIGHT = 640, 480
FPS = 60
GRID = 32
CELL_SIZE = 32

PLAYER_LIVES = 3            # 初始生命数
PLAYER_MAX_HP = 3           # 每命血量
PLAYER_SPEED = 3

BASE_GRID = (9, 13)         # 基地所在格子 (列, 行)
PLAYER_GRID = (9, 11)       # 玩家出生格子 (列, 行)
ENEMY_SPAWN_COLS = (2, 9, 16)

# 颜色 (R, G, B)
BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
GREY    = (128, 128, 128)
BROWN   = (160, 82, 45)
GREEN   = (0, 180, 0)
RED     = (200, 40, 40)
BLUE    = (40, 80, 200)
ORANGE  = (255, 165, 0)
YELLOW  = (255, 215, 0)
CYAN    = (0, 220, 220)
WATER_BLUE = (40, 90, 200)
ICE_BLUE   = (170, 220, 255)
GRASS_GREEN = (40, 160, 60)

# 在导入时初始化字体子系统,供模块级字体使用
pygame.font.init()

font = pygame.font.SysFont("Consolas", 20)
small_font = pygame.font.SysFont("Consolas", 16)
big_font = pygame.font.SysFont("Consolas", 48, bold=True)


# --------------- 音效 (合成方波, 无外部文件) ---------------
class Audio:
    """用 array 合成简单方波音效, 失败时静默降级。"""

    def __init__(self):
        self.enabled = False
        self._sounds = {}
        self._tone_map = {
            "shoot":   (880, 60, 0.18),
            "explode": (110, 200, 0.40),
            "pickup":  (660, 90, 0.30),
            "level":   (523, 140, 0.32),
            "gameover": (200, 450, 0.40),
        }
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.enabled = pygame.mixer.get_init() is not None
        except Exception:
            self.enabled = False

    def _tone(self, freq, ms, vol):
        try:
            import array
        except ImportError:
            return None
        init = pygame.mixer.get_init()
        if not init:
            return None
        sr = init[0]
        n = int(sr * ms / 1000)
        period = max(1, int(sr / freq))
        buf = array.array("h")
        for i in range(n):
            v = 32767 if (i // period) % 2 == 0 else -32767
            buf.append(int(v * vol))
        try:
            return pygame.mixer.Sound(buffer=buf.tobytes())
        except Exception:
            return None

    def play(self, name):
        if not self.enabled:
            return
        if name not in self._tone_map:
            return
        if name not in self._sounds:
            self._sounds[name] = self._tone(*self._tone_map[name])
        snd = self._sounds[name]
        if snd:
            try:
                snd.play()
            except Exception:
                pass


# --------------- 坦克 ---------------
class Tank(pygame.sprite.Sprite):
    """坦克基类: 支持移动、转向与射击。"""

    COLOR = YELLOW
    SPEED = 3
    MAX_HP = 3

    def __init__(self, x, y, owner):
        super().__init__()
        self.owner = owner                  # "player" 或 "enemy"
        self.color = self.COLOR
        self.speed = self.SPEED
        self.max_hp = self.MAX_HP
        self.hp = self.max_hp
        self.direction = "up"
        self.cooldown = 0
        self.rect = pygame.Rect(0, 0, GRID, GRID)
        self.rect.topleft = (x, y)
        self.image, self.tbar = self._make_image()
        self.rect = self.image.get_rect(x=x, y=y)

    def _make_image(self):
        """生成一张带炮管的车身位图, 炮管朝向 self.direction。"""
        w = self.rect.width
        h = self.rect.height
        img = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(img, self.color, (4, 4, w - 8, h - 8), border_radius=4)
        pygame.draw.rect(img, BLACK, (0, 4, 6, h - 8), border_radius=3)   # 左履带
        pygame.draw.rect(img, BLACK, (w - 6, 4, 6, h - 8), border_radius=3)  # 右履带
        cx, cy = w // 2, h // 2
        tbar = None
        if self.direction == "up":
            tbar = pygame.Rect(cx - 3, 0, 6, cy + 4)
        elif self.direction == "down":
            tbar = pygame.Rect(cx - 3, cy - 4, 6, cy + 4)
        elif self.direction == "left":
            tbar = pygame.Rect(0, cy - 3, cx + 4, 6)
        elif self.direction == "right":
            tbar = pygame.Rect(cx - 4, cy - 3, cx + 4, 6)
        pygame.draw.rect(img, WHITE, tbar, border_radius=2)
        return img, tbar

    def _rotate(self, direction):
        if direction == self.direction:
            return
        self.direction = direction
        self.image, self.tbar = self._make_image()
        self.rect = self.image.get_rect(center=self.rect.center)

    def _collides(self, rect, walls, tanks, except_tank=None):
        """检测给定 rect 是否与墙/坦克重叠或超出边界。"""
        if rect.left < 0 or rect.top < 0 or rect.right > WIDTH or rect.bottom > HEIGHT:
            return True
        for w in walls:
            if rect.colliderect(w.rect):
                return True
        for t in tanks:
            if t is except_tank:
                continue
            if rect.colliderect(t.rect):
                return True
        return False

    def can_move(self, direction, walls, tanks):
        """返回朝某方向移动一格(speed 步)是否可行。"""
        d = {"up": (0, -self.speed), "down": (0, self.speed),
             "left": (-self.speed, 0), "right": (self.speed, 0)}[direction]
        new_rect = self.rect.move(d)
        return not self._collides(new_rect, walls, tanks, except_tank=self)

    def move(self, direction, walls, tanks):
        self._rotate(direction)
        d = {"up": (0, -self.speed), "down": (0, self.speed),
             "left": (-self.speed, 0), "right": (self.speed, 0)}[direction]
        new_rect = self.rect.move(d)
        if not self._collides(new_rect, walls, tanks, except_tank=self):
            self.rect = new_rect

    def update(self, walls, tanks, bullets_group):
        if self.cooldown > 0:
            self.cooldown -= 1

    def shoot(self, bullets_group, cooldown=None):
        if self.cooldown > 0:
            return None
        w, h = self.image.get_size()
        cx, cy = w // 2, h // 2
        bd = {"up": (0, -6), "down": (0, 6),
              "left": (-6, 0), "right": (6, 0)}[self.direction]
        pos = {"up": (cx, 0), "down": (cx, h),
               "left": (0, cy), "right": (w, cy)}[self.direction]
        self.cooldown = self.default_cooldown if cooldown is None else cooldown
        return Bullet(self.rect.left + pos[0], self.rect.top + pos[1],
                      bd, self.color, self.owner)

    def draw_hp(self, surface):
        if self.max_hp <= 1:
            return
        w = self.rect.width
        ratio = max(0.0, self.hp / self.max_hp)
        pygame.draw.rect(surface, RED, (self.rect.left, self.rect.top - 6, w, 4))
        pygame.draw.rect(surface, GREEN,
                         (self.rect.left, self.rect.top - 6, int(w * ratio), 4))


class Player(Tank):
    COLOR = YELLOW
    SPEED = PLAYER_SPEED
    MAX_HP = PLAYER_MAX_HP

    def __init__(self, x, y):
        super().__init__(x, y, "player")
        self.default_cooldown = 25
        self.shield_timer = 0      # 护盾剩余帧数 (无敌)
        self.rapid_timer = 0       # 连发剩余帧数
        self.star_level = 0        # 升级星数 (永久强化)

    def apply_powerup(self, kind):
        if kind == "heal":
            self.hp = min(self.hp + 1, self.max_hp + 2)
        elif kind == "shield":
            self.shield_timer = FPS * 8
        elif kind == "rapid":
            self.rapid_timer = FPS * 12
        elif kind == "star":
            self.star_level += 1
            self.max_hp += 1
            self.hp = min(self.hp + 1, self.max_hp)
            self.speed = PLAYER_SPEED + min(self.star_level, 1)

    def update(self, walls, tanks, bullets_group):
        super().update(walls, tanks, bullets_group)
        if self.shield_timer > 0:
            self.shield_timer -= 1
        if self.rapid_timer > 0:
            self.rapid_timer -= 1

    def shoot(self, bullets_group, cooldown=None):
        if self.cooldown > 0:
            return None
        cd = 10 if self.rapid_timer > 0 else self.default_cooldown
        return super().shoot(bullets_group, cooldown=cd)

    @property
    def invincible(self):
        return self.shield_timer > 0


class Enemy(Tank):
    """敌方坦克, 通过 kind 区分类型: normal / fast / power / armor。"""

    def __init__(self, x, y, kind="normal"):
        super().__init__(x, y, "enemy")
        cfg = ENEMY_TYPES[kind]
        self.kind = kind
        self.color = cfg["color"]
        self.speed = cfg["speed"]
        self.max_hp = self.hp = cfg["hp"]
        self.score_value = cfg["score"]
        self.shoot_prob = cfg["shoot_prob"]
        self.default_cooldown = cfg["cooldown"]
        self.turn_timer = random.randint(30, 90)
        self.stuck_frames = 0
        self.image, self.tbar = self._make_image()

    def _pick_direction(self, base_rect, player_rect, walls, tanks):
        """朝基地/玩家方向带概率倾向, 且优先选择可行方向。"""
        choices = ["up", "down", "left", "right"]
        r = random.random()
        target = None
        if r < 0.30:
            target = base_rect.center       # 倾向进攻基地
        elif r < 0.45:
            target = player_rect.center     # 倾向追击玩家
        if target:
            tx, ty = target
            cx, cy = self.rect.center
            dx, dy = tx - cx, ty - cy
            preferred = []
            if abs(dx) > abs(dy):
                preferred = ["right" if dx > 0 else "left",
                             "down" if dy > 0 else "up"]
            else:
                preferred = ["down" if dy > 0 else "up",
                             "right" if dx > 0 else "left"]
            ordered = preferred + [c for c in choices if c not in preferred]
        else:
            random.shuffle(choices)
            ordered = choices
        # 优先选择可通行方向
        for d in ordered:
            if d != self.direction and self.can_move(d, walls, tanks):
                return d
        # 若都不可行, 保持原方向(可能撞墙, 下一帧再换)
        return self.direction

    def ai_update(self, walls, tanks, bullets_group, base_rect, player_rect):
        self.turn_timer -= 1
        blocked = not self.can_move(self.direction, walls, tanks)
        if blocked:
            self.stuck_frames += 1
        else:
            self.stuck_frames = 0
        if blocked or self.turn_timer <= 0 or self.stuck_frames > 8:
            self.direction = self._pick_direction(base_rect, player_rect, walls, tanks)
            self.turn_timer = random.randint(30, 90)
        self.move(self.direction, walls, tanks)

        # 射击: 与玩家/基地大致对齐时提高开火概率
        prob = self.shoot_prob
        aligned = (abs(self.rect.centerx - player_rect.centerx) < GRID // 2 or
                   abs(self.rect.centery - player_rect.centery) < GRID // 2 or
                   abs(self.rect.centerx - base_rect.centerx) < GRID // 2 or
                   abs(self.rect.centery - base_rect.centery) < GRID // 2)
        if aligned:
            prob *= 3
        if random.random() < prob:
            b = self.shoot(bullets_group)
            if b:
                bullets_group.add(b)


# --------------- 子弹 ---------------
class Bullet(pygame.sprite.Sprite):
    DAMAGE = 1
    RADIUS = 4

    def __init__(self, x, y, direction, owner_color, owner):
        super().__init__()
        self.color = owner_color
        self.owner = owner
        self.image = pygame.Surface((self.RADIUS * 2, self.RADIUS * 2),
                                    pygame.SRCALPHA)
        pygame.draw.circle(self.image, (255, 255, 180),
                           (self.RADIUS, self.RADIUS), self.RADIUS)
        self.rect = self.image.get_rect(center=(x, y))
        self.direction = direction

    def update(self):
        self.rect.move_ip(self.direction)
        if not pygame.Rect(0, 0, WIDTH, HEIGHT).contains(self.rect):
            self.kill()


# --------------- 基地 ---------------
class Base(pygame.sprite.Sprite):
    """玩家基地(鹰标)。被击中则游戏结束。"""

    def __init__(self, x, y):
        super().__init__()
        self.alive = True
        self.rect = pygame.Rect(x, y, GRID, GRID)
        self._paint()

    def _paint(self):
        img = pygame.Surface((GRID, GRID), pygame.SRCALPHA)
        pygame.draw.rect(img, BLACK, (0, 0, GRID, GRID))
        color = GREEN if self.alive else RED
        pygame.draw.polygon(img, color, [
            (GRID // 2, 4), (GRID - 6, GRID - 4), (6, GRID - 4)])
        pygame.draw.rect(img, (255, 255, 255), (12, 16, GRID - 24, 8))
        self.image = img

    def hit(self):
        self.alive = False
        self._paint()


# --------------- 道具 ---------------
class PowerUp(pygame.sprite.Sprite):
    """掉落道具: heal 回血 / shield 护盾 / rapid 连发 / bomb 全屏炸弹 / star 升级。"""

    COLORS = {
        "heal":   (240, 60, 60),
        "shield": (70, 130, 240),
        "rapid":  (255, 200, 0),
        "bomb":   (90, 90, 90),
        "star":   (255, 215, 0),
    }

    def __init__(self, x, y, kind=None):
        super().__init__()
        self.kind = kind or random.choice(POWERUP_KINDS)
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (x, y)
        self._paint()

    def _paint(self):
        s = self.rect.width
        img = pygame.Surface((s, s), pygame.SRCALPHA)
        c = self.COLORS[self.kind]
        pygame.draw.circle(img, c, (s // 2, s // 2), s // 2 - 2)
        pygame.draw.circle(img, WHITE, (s // 2, s // 2), s // 2 - 2, 2)
        if self.kind == "heal":
            pygame.draw.rect(img, WHITE, (s // 2 - 2, s // 2 - 8, 4, 16))
            pygame.draw.rect(img, WHITE, (s // 2 - 8, s // 2 - 2, 16, 4))
        elif self.kind == "shield":
            pygame.draw.polygon(img, WHITE, [(s // 2, 4), (s - 6, 8),
                                             (s - 6, s // 2), (s // 2, s - 4)])
        elif self.kind == "rapid":
            pygame.draw.polygon(img, WHITE, [(s // 2 + 2, 4), (s // 2 - 6, s // 2),
                                             (s // 2 - 2, s // 2), (s // 2 - 2, s - 4),
                                             (s // 2 + 8, s // 2 - 2), (s // 2 + 2, s // 2 - 2)])
        elif self.kind == "bomb":
            pygame.draw.circle(img, BLACK, (s // 2, s // 2 + 2), s // 2 - 6)
            pygame.draw.line(img, WHITE, (s // 2, s // 2 - 2), (s // 2 + 4, s // 2 - 8), 2)
        elif self.kind == "star":
            pygame.draw.polygon(img, WHITE, [(s // 2, 3), (s // 2 + 3, s // 2 - 3),
                                             (s - 4, s // 2 - 3), (s // 2 + 4, s // 2 + 2),
                                             (s // 2 + 7, s - 3), (s // 2, s // 2 + 6),
                                             (s // 2 - 7, s - 3), (s // 2 - 4, s // 2 + 2),
                                             (4, s // 2 - 3), (s // 2 - 3, s // 2 - 3)])
        self.image = img


# --------------- 地图 ---------------
def make_map(layout):
    """根据字符串数组构建地形。

    返回 (walls, grass, ice) 三个 sprite.Group:
        walls: 砖墙 / 钢墙 / 水域 (坦克不可通行)
        grass: 草丛 (绘制在坦克之上, 藏身用)
        ice:   冰面 (坦克在上面打滑)
    """
    walls = pygame.sprite.Group()
    grass = pygame.sprite.Group()
    ice = pygame.sprite.Group()

    def _sprite(surf, x, y, kind):
        sp = pygame.sprite.Sprite()
        sp.image = surf
        sp.rect = surf.get_rect(x=x, y=y)
        sp.kind = kind
        return sp

    for r, row in enumerate(layout):
        for c, ch in enumerate(row):
            x, y = c * CELL_SIZE, r * CELL_SIZE
            if ch == "-":      # 钢墙: 不可击碎
                surf = pygame.Surface((CELL_SIZE, CELL_SIZE))
                surf.fill(GREY)
                pygame.draw.line(surf, BLACK, (0, 0), (CELL_SIZE, CELL_SIZE), 2)
                pygame.draw.line(surf, BLACK, (CELL_SIZE, 0), (0, CELL_SIZE), 2)
                pygame.draw.rect(surf, BLACK, (0, 0, CELL_SIZE, CELL_SIZE), 1)
                walls.add(_sprite(surf, x, y, "steel"))
            elif ch == "#":    # 砖墙: 可击碎
                surf = pygame.Surface((CELL_SIZE, CELL_SIZE))
                surf.fill(BROWN)
                pygame.draw.line(surf, BLACK, (0, CELL_SIZE // 2), (CELL_SIZE, CELL_SIZE // 2))
                pygame.draw.line(surf, BLACK, (CELL_SIZE // 2, 0), (CELL_SIZE // 2, CELL_SIZE))
                pygame.draw.rect(surf, BLACK, (0, 0, CELL_SIZE, CELL_SIZE), 1)
                walls.add(_sprite(surf, x, y, "brick"))
            elif ch == "~":    # 水域
                surf = pygame.Surface((CELL_SIZE, CELL_SIZE))
                surf.fill(WATER_BLUE)
                pygame.draw.line(surf, (90, 140, 255), (0, 8), (CELL_SIZE, 8), 2)
                pygame.draw.line(surf, (90, 140, 255), (0, 22), (CELL_SIZE, 22), 2)
                walls.add(_sprite(surf, x, y, "water"))
            elif ch == "*":    # 草丛
                surf = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                surf.fill((GRASS_GREEN[0], GRASS_GREEN[1], GRASS_GREEN[2], 180))
                for _ in range(10):
                    gx = random.randint(0, CELL_SIZE - 2)
                    gy = random.randint(0, CELL_SIZE - 2)
                    pygame.draw.rect(surf, (20, 110, 40, 200), (gx, gy, 3, 3))
                grass.add(_sprite(surf, x, y, "grass"))
            elif ch == "/":    # 冰面
                surf = pygame.Surface((CELL_SIZE, CELL_SIZE))
                surf.fill(ICE_BLUE)
                pygame.draw.line(surf, WHITE, (0, 0), (CELL_SIZE, CELL_SIZE), 1)
                pygame.draw.line(surf, WHITE, (CELL_SIZE, 0), (0, CELL_SIZE), 1)
                ice.add(_sprite(surf, x, y, "ice"))
    return walls, grass, ice


def draw_text(surface, text, x, y, color=WHITE, size="normal"):
    f = {"normal": font, "small": small_font, "big": big_font}[size]
    surface.blit(f.render(text, True, color), (x, y))


def draw_centered(surface, text, y, color=WHITE, size="normal"):
    f = {"normal": font, "small": small_font, "big": big_font}[size]
    img = f.render(text, True, color)
    surface.blit(img, (WIDTH // 2 - img.get_width() // 2, y))


# --------------- 游戏主类 ---------------
class Game:
    def __init__(self):
        try:
            pygame.mixer.pre_init(22050, -16, 1, 512)
        except Exception:
            pass
        pygame.init()
        self.audio = Audio()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("坦克大战 Tank Battle")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "start"     # start / intro / play / pause / gameover / victory
        self.level = 1
        self.score = 0
        self.lives = PLAYER_LIVES
        self.high_score = 0
        self.frame = 0
        self.intro_timer = 0
        self.spawn_timer = 0
        self._load_level(self.level)

    # -------- 关卡加载 --------
    def _load_level(self, n):
        cfg = LEVELS[n - 1]
        self.level_cfg = cfg
        self.walls, self.grass, self.ice = make_map(cfg["layout"])
        bx, by = BASE_GRID[0] * CELL_SIZE, BASE_GRID[1] * CELL_SIZE
        self.base = Base(bx, by)
        px, py = PLAYER_GRID[0] * CELL_SIZE, PLAYER_GRID[1] * CELL_SIZE
        self.player = Player(px, py)
        self.player.shield_timer = FPS * 3   # 开局短暂无敌
        self.tanks = pygame.sprite.Group()
        self.tanks.add(self.player)
        self.enemies = []
        self.bullets = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        # 敌人队列(本关全部敌人), 场上同时最多 max_active 个
        self.enemy_queue = []
        for kind, count in cfg["enemy_mix"].items():
            self.enemy_queue += [kind] * count
        random.shuffle(self.enemy_queue)
        self.max_active = cfg["max_active"]
        self.spawn_timer = 0

    def reset(self):
        self.score = 0
        self.level = 1
        self.lives = PLAYER_LIVES
        self._load_level(self.level)
        self.state = "intro"
        self.intro_timer = FPS * 2

    # -------- 敌人出生 --------
    def _enemy_spawn_positions(self):
        spots = []
        for col in ENEMY_SPAWN_COLS:
            for row in (1, 2):
                spots.append((col * CELL_SIZE, row * CELL_SIZE))
        return spots

    def spawn_enemy(self):
        if not self.enemy_queue:
            return
        if len(self.enemies) >= self.max_active:
            return
        kind = self.enemy_queue.pop(0)
        for x, y in self._enemy_spawn_positions():
            r = pygame.Rect(x, y, GRID, GRID)
            if any(r.colliderect(w.rect) for w in self.walls):
                continue
            if any(r.colliderect(t.rect) for t in self.tanks):
                continue
            e = Enemy(x, y, kind)
            self.enemies.append(e)
            self.tanks.add(e)
            return
        # 找不到空格就放弃本次(下帧重试)

    # -------- 关卡推进 --------
    def _level_cleared(self):
        return not self.enemy_queue and not self.enemies

    def _advance_level(self):
        if self.level >= TOTAL_LEVELS:
            self.state = "victory"
            self.high_score = max(self.high_score, self.score)
            self.audio.play("level")
            return
        self.level += 1
        self._load_level(self.level)
        self.state = "intro"
        self.intro_timer = FPS * 2
        self.audio.play("level")

    def _respawn_player(self):
        px, py = PLAYER_GRID[0] * CELL_SIZE, PLAYER_GRID[1] * CELL_SIZE
        self.player.rect.center = (px + GRID // 2, py + GRID // 2)
        self.player.hp = self.player.max_hp
        self.player.direction = "up"
        self.player.image, self.player.tbar = self.player._make_image()
        self.player.shield_timer = FPS * 3

    # -------- 输入 --------
    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_RETURN:
                    if self.state in ("start", "gameover", "victory"):
                        self.reset()
                    elif self.state == "intro":
                        self.intro_timer = 0
                elif event.key == pygame.K_p and self.state in ("play", "pause"):
                    self.state = "pause" if self.state == "play" else "play"

        if self.state != "play":
            return

        keys = pygame.key.get_pressed()
        p = self.player
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            p.move("up", self.walls, self.tanks)
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            p.move("down", self.walls, self.tanks)
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            p.move("left", self.walls, self.tanks)
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            p.move("right", self.walls, self.tanks)
        if keys[pygame.K_SPACE] or keys[pygame.K_j]:
            b = p.shoot(self.bullets)
            if b:
                self.bullets.add(b)
                self.audio.play("shoot")

    # -------- 更新 --------
    def _on_ice(self, rect):
        for t in self.ice:
            if rect.colliderect(t.rect):
                return True
        return False

    def _apply_slide(self, tank):
        """坦克在冰面上时额外滑动一步。"""
        if self._on_ice(tank.rect):
            tank.move(tank.direction, self.walls, self.tanks)

    def _spawn_powerup(self, rect):
        if random.random() < 0.28:   # 28% 概率掉落
            kind = random.choice(POWERUP_KINDS)
            self.powerups.add(PowerUp(rect.centerx, rect.centery, kind))

    def update(self):
        self.frame += 1
        if self.state == "intro":
            self.intro_timer -= 1
            if self.intro_timer <= 0:
                self.state = "play"
            return
        if self.state != "play":
            return

        p = self.player

        # 生成敌人
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self.spawn_enemy()
            self.spawn_timer = 60   # 每 60 帧尝试生成一个

        # 敌人 AI
        for e in self.enemies:
            e.ai_update(self.walls, self.tanks, self.bullets,
                        self.base.rect, p.rect)
        self.tanks.update(self.walls, self.tanks, self.bullets)
        self.bullets.update()

        # 冰面打滑
        self._apply_slide(p)
        for e in self.enemies:
            self._apply_slide(e)

        # 道具拾取
        for pu in list(self.powerups):
            if p.rect.colliderect(pu.rect):
                p.apply_powerup(pu.kind)
                pu.kill()
                self.audio.play("pickup")
                if pu.kind == "bomb":
                    self._detonate_bomb()

        # 子弹碰撞
        new_bullets = pygame.sprite.Group()
        for b in self.bullets:
            killed = False
            for w in self.walls:
                if b.rect.colliderect(w.rect):
                    if w.kind == "water":
                        continue           # 子弹越过水域
                    killed = True
                    if w.kind == "brick":
                        w.kill()
                    break
            if not killed:
                if b.owner == "player":
                    for e in self.enemies:
                        if b.rect.colliderect(e.rect):
                            killed = True
                            e.hp -= b.DAMAGE
                            if e.hp <= 0:
                                self._kill_enemy(e)
                            break
                else:
                    if p.rect.colliderect(b.rect):
                        killed = True
                        if not p.invincible:
                            self._hit_player()
            if not killed and b.rect.colliderect(self.base.rect):
                killed = True
                self.base.hit()
                self.state = "gameover"
                self.audio.play("gameover")
            if not killed:
                new_bullets.add(b)
        self.bullets = new_bullets

        # 敌人与基地/玩家碰撞
        for e in self.enemies:
            if e.rect.colliderect(self.base.rect):
                self.base.hit()
                self.state = "gameover"
                self.audio.play("gameover")
                break
            if e.rect.colliderect(p.rect) and not p.invincible:
                self._hit_player()
                break

        # 过关检测
        if self.state == "play" and self._level_cleared():
            self._advance_level()

    def _kill_enemy(self, e):
        e.kill()
        if e in self.enemies:
            self.enemies.remove(e)
        self.score += e.score_value
        self.audio.play("explode")
        self._spawn_powerup(e.rect)

    def _detonate_bomb(self):
        for e in list(self.enemies):
            self.score += e.score_value
            e.kill()
            self.enemies.remove(e)
        for b in list(self.bullets):
            if b.owner == "enemy":
                b.kill()
        self.audio.play("explode")

    def _hit_player(self):
        p = self.player
        p.hp -= 1
        self.audio.play("explode")
        if p.hp <= 0:
            self.lives -= 1
            if self.lives <= 0:
                self.state = "gameover"
                self.high_score = max(self.high_score, self.score)
                self.audio.play("gameover")
            else:
                self._respawn_player()

    # -------- 渲染 --------
    def render(self):
        self.screen.fill(BLACK)
        self.ice.draw(self.screen)
        self.walls.draw(self.screen)
        self.screen.blit(self.base.image, self.base.rect)
        self.tanks.draw(self.screen)
        self.bullets.draw(self.screen)

        # 道具(闪烁)
        for pu in self.powerups:
            if (self.frame // 15) % 2 == 0:
                self.screen.blit(pu.image, pu.rect)

        # 草丛绘制在坦克之上(藏身)
        self.grass.draw(self.screen)

        # 护盾光圈
        if self.player.invincible:
            pygame.draw.circle(self.screen, CYAN, self.player.rect.center,
                               GRID // 2 + 4, 2)

        self._draw_hud()

        if self.state == "start":
            self._draw_overlay("坦克大战", "TANK BATTLE", "按 Enter 开始 · Esc 退出", YELLOW)
        elif self.state == "intro":
            self._draw_overlay(f"第 {self.level} 关", self.level_cfg["name"],
                               f"剩余敌人 {len(self.enemy_queue) + len(self.enemies)}", CYAN)
        elif self.state == "pause":
            self._draw_overlay("已暂停", "PAUSED", "按 P 继续 · Esc 退出", YELLOW)
        elif self.state == "gameover":
            self._draw_overlay("游戏结束", "GAME OVER",
                               f"最终得分 {self.score}", RED)
        elif self.state == "victory":
            self._draw_overlay("胜利!", "YOU WIN!",
                               f"最终得分 {self.score} · 最高分 {self.high_score}", GREEN)

        pygame.display.flip()

    def _draw_hud(self):
        draw_text(self.screen, f"SCORE {self.score}", 10, 8)
        draw_text(self.screen, f"HI {self.high_score}", 10, 30, GREY, "small")
        draw_text(self.screen, f"LEVEL {self.level}", WIDTH // 2 - 40, 8)
        draw_text(self.screen, f"LIVES {self.lives}", WIDTH - 110, 8)
        remaining = len(self.enemy_queue) + len(self.enemies)
        draw_text(self.screen, f"ENEMY {remaining}", WIDTH - 110, 30, GREY, "small")
        # 玩家血量条
        self.player.draw_hp(self.screen)
        for e in self.enemies:
            e.draw_hp(self.screen)

    def _draw_overlay(self, title, subtitle, hint, color):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        draw_centered(self.screen, title, HEIGHT // 2 - 60, color, "big")
        draw_centered(self.screen, subtitle, HEIGHT // 2 - 20, WHITE)
        draw_centered(self.screen, hint, HEIGHT // 2 + 20, GREY, "small")

    # -------- 主循环 --------
    def run(self):
        while self.running:
            self.handle_input()
            self.update()
            self.render()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()


def main():
    parser = argparse.ArgumentParser(description="坦克大战 (Tank Battle)")
    parser.add_argument("--level", type=int, default=1,
                        help=f"起始关卡 (1-{TOTAL_LEVELS})")
    args = parser.parse_args()
    game = Game()
    game.level = max(1, min(TOTAL_LEVELS, args.level))
    game._load_level(game.level)
    game.state = "intro"
    game.intro_timer = FPS * 2
    game.run()


if __name__ == "__main__":
    main()
