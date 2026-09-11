"""
坦克大战 (Tank Battle) - 使用 pygame 实现

操作方式:
    方向键 / WASD : 移动坦克
    空格 / J      : 发射子弹
    P             : 暂停 / 继续
    Enter         : 开局 / 重新开始
    Esc           : 暂停 (可退出) / 退出

目标:
    保护你的基地(屏幕下方中间的鹰标),击溃所有敌方坦克。
"""

import random
import sys
import argparse

import pygame

# --------------- 基础配置 ---------------
WIDTH, HEIGHT = 640, 480
FPS = 60
GRID = 32                  # 基地 / 单个格子尺寸
CELL_SIZE = 32             # 墙格边长(正方形), 与坦克同尺寸

ENEMY_PER_LEVEL = 6        # 每关敌人数量(固定, 不随等级递增) 6 个

# 颜色 (R, G, B)
BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
GREY    = (128, 128, 128)
BROWN   = (160, 82, 45)
GREEN   = (0, 128, 0)
RED     = (200, 40, 40)
BLUE    = (40, 80, 200)
ORANGE  = (255, 165, 0)
YELLOW  = (255, 215, 0)

# 在导入时初始化字体子系统,供模块级字体使用
pygame.font.init()

font = pygame.font.SysFont("Consolas", 20)
big_font = pygame.font.SysFont("Consolas", 48, bold=True)


class Tank(pygame.sprite.Sprite):
    """坦克基类:支持移动、转向与射击。"""

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
        """生成一张带炮管的车身位图,炮管朝向 current.direction。"""
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
        """检测给定 rect 是否与墙/坦克重叠。"""
        if not rect.clip(0, 0, WIDTH, HEIGHT).contains(rect):
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

    def shoot(self, bullets_group):
        if self.cooldown > 0:
            return None
        w, h = self.image.get_size()
        cx, cy = w // 2, h // 2
        bd = {"up": (0, -6), "down": (0, 6),
              "left": (-6, 0), "right": (6, 0)}[self.direction]
        pos = {"up": (cx, 0), "down": (cx, h),
               "left": (0, cy), "right": (w, cy)}[self.direction]
        self.cooldown = 25
        return Bullet(self.rect.left + pos[0], self.rect.top + pos[1],
                      bd, self.color, self.owner)

    def draw_hp(self, surface):
        if self.max_hp <= 1:
            return
        w = self.rect.width
        ratio = self.hp / self.max_hp
        pygame.draw.rect(surface, RED, (self.rect.left, self.rect.top - 6, w, 4))
        pygame.draw.rect(surface, GREEN,
                         (self.rect.left, self.rect.top - 6, int(w * ratio), 4))


class Player(Tank):
    COLOR = YELLOW
    SPEED = 3
    MAX_HP = 3

    def __init__(self, x, y):
        super().__init__(x, y, "player")
        self.score = 0


class Enemy(Tank):
    COLORS = [RED, ORANGE, BLUE, (180, 120, 220)]

    def __init__(self, x, y, speed=None, hp=None):
        super().__init__(x, y, "enemy")
        self.color = random.choice(self.COLORS)
        self.speed = speed or random.choice([1, 2])
        self.max_hp = self.hp = hp or random.choice([1, 2, 3])

    def ai_update(self, walls, tanks, bullets_group):
        if random.random() < 0.02:
            self.direction = random.choice(["up", "down", "left", "right"])
        self.move(self.direction, walls, tanks)
        if random.random() < 0.03:
            b = self.shoot(bullets_group)
            if b:
                bullets_group.add(b)


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
        if not self.rect.clip(0, 0, WIDTH, HEIGHT).contains(self.rect):
            self.kill()


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


def make_map():
    """字符串数组构建地图:"#砖墙可击碎 -钢墙不可击碎 .空格"""
    # 强制 GRID 对齐(每行 20 列、15 行 = 640x480，墙格统一为 GRID x GRID)：
    # 墙体对齐、不溢出屏幕。layout 每行必须恰好 20 个字符。
    layout = [
        "--------------------",  # row,0/14
        "-..................-",  # row,1/14
        "-.....#.....#......-",  # row,2/14
        "-....#.#....#.#....-",  # row,3/14
        "-..#...#.#..#...#..-",  # row,4/14
        "-.#....#....#...#..-",  # row,5/14
        "-....#....#...-....-",  # row,6/14
        "-.....##...-.##....-",  # row,7/14
        "-..................-",  # row,8/14
        "-..................-",  # row,9/14
        "-..................-",  # row,10/14
        "-..................-",  # row,11/14
        "-.....#.....#......-",  # row,12/14
        "-....#.#.....#.....-",  # row,13/14
        "--------------------",  # row,14/14
    ]
    cell_w = CELL_SIZE
    cell_h = CELL_SIZE
    walls = pygame.sprite.Group()
    for r, row in enumerate(layout):
        for c, ch in enumerate(row):
            if ch in ("#", "-"):
                surf = pygame.Surface((cell_w, cell_h))
                if ch == "-":  # 钢墙: 不可击碎
                    pygame.draw.rect(surf, GREY, (0, 0, cell_w, cell_h))
                    pygame.draw.line(surf, BLACK, (0, 0), (cell_w, cell_h))
                    pygame.draw.line(surf, BLACK, (cell_w, 0), (0, cell_h))
                    breakable = False
                else:  # 砖墙: 可击碎
                    pygame.draw.rect(surf, BROWN, (1, 1, cell_w - 2, cell_h - 2))
                    pygame.draw.rect(surf, BLACK, (0, 0, cell_w, cell_h), 1)
                    breakable = True
                w = pygame.sprite.Sprite()
                w.image = surf
                w.rect = w.image.get_rect(x=c * cell_w, y=r * cell_h)
                w.breakable = breakable
                walls.add(w)
    return walls


def draw_text(surface, text, x, y, color=WHITE):
    surface.blit(font.render(text, True, color), (x, y))


def draw_pause_screen(surface):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surface.blit(overlay, (0, 0))
    msg = big_font.render("PAUSED", True, YELLOW)
    surface.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - 30))
    draw_text(surface, "按 P 继续 / Esc 退出", WIDTH // 2 - 100, HEIGHT // 2 + 30)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("坦克大战 Tank Battle")
        self.clock = pygame.time.Clock()
        self.running = True
        self.reset()

    def reset(self):
        self.score = 0
        self.level = 1
        self.game_over = False
        self.paused = False
        self.won = False
        self.walls = make_map()
        self.base = Base(WIDTH // 2 - GRID // 2, HEIGHT - GRID * 2)
        self.player = Player(WIDTH // 2 - 16, HEIGHT - GRID * 3 - GRID)
        self.tanks = pygame.sprite.Group()     # 所有坦克
        self.tanks.add(self.player)
        self.enemies = []                      # 保留 enemy 引用列表
        self.bullets = pygame.sprite.Group()
        self.enemies_left = ENEMY_PER_LEVEL
        self.spawn_wave()

    def _valid_spawn(self, rect):
        """出生合法性: 不与墙体、任何坦克重叠, 且不超出地图边界。"""
        inside = (rect.left >= 0 and rect.top >= 0 and
                  rect.right <= WIDTH and rect.bottom <= HEIGHT)
        if not inside:
            return False
        if any(rect.colliderect(w.rect) for w in self.walls):
            return False
        if any(rect.colliderect(t.rect) for t in self.tanks):
            return False
        return True

    def spawn_wave(self):
        # 三个起始列(左/中/右)，并排避免重叠；超出列数时依次排到下面几行(Y 错位)。
        positions = [WIDTH // 6, WIDTH // 2, WIDTH * 5 // 6]
        for i in range(self.enemies_left):
            row = i // 3          # 每列最多 3 个敌人, 超出则换下一行
            col = i % 3
            x = positions[col] - GRID // 2
            y = GRID * (row + 1)  # 顶部留一行作为出生缓冲区(顶层为钢墙边界)
            e = Enemy(x, y)
            e.rect = e.rect.copy()
            # 寻找一个贴墙对齐且不与墙体、地图边界重叠的格子并落位
            placed = False
            for dx, dy in ((0, 0), (GRID, 0), (-GRID, 0), (0, GRID)):
                e.rect.topleft = (x + dx, y + dy)
                if self._valid_spawn(e.rect):
                    placed = True
                    break
            if not placed:
                # 实在难找空格: 退回当前对齐位置, 不要超出地图边界
                e.rect.topleft = (max(GRID, min(WIDTH - GRID, x)),
                                  max(GRID + GRID, min(HEIGHT - GRID, y)))
            e.col = col
            e.enemy_id = i
            self.enemies.append(e)
            self.tanks.add(e)


    def next_level(self):
        self.level += 1
        self.enemies_left = ENEMY_PER_LEVEL
        safe_tanks = list(self.tanks)
        for e in safe_tanks:
            if isinstance(e, Enemy):
                e.remove(self.tanks)
                e.kill()
        self.enemies = []
        self.spawn_wave()

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.paused:
                        self.paused = False  # Esc 继续
                    else:
                        self.running = False  # 首 Esc 退出
                elif event.key == pygame.K_RETURN and self.game_over:
                    self.reset()
                elif event.key == pygame.K_p and not self.game_over:
                    self.paused = not self.paused

        if self.game_over or self.paused:
            return
        keys = pygame.key.get_pressed()
        p = self.player
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            p.move("up", self.walls, self.tanks)
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            p.move("down", self.walls, self.tanks)
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            p.move("left", self.walls, self.tanks)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            p.move("right", self.walls, self.tanks)
        if keys[pygame.K_SPACE] or keys[pygame.K_j]:
            b = p.shoot(self.bullets)
            if b:
                self.bullets.add(b)

    def update(self):
        if self.game_over or self.paused:
            return
        p = self.player
        # AI move + shoot of enemies
        for e in self.enemies:
            e.ai_update(self.walls, self.tanks, self.bullets)
        self.tanks.update(self.walls, self.tanks, self.bullets)
        self.bullets.update()

        # Collision handling
        new_bullets = pygame.sprite.Group()
        for b in self.bullets:
            killed = False
            # vs walls
            for w in self.walls:
                if b.rect.colliderect(w.rect):
                    killed = True
                    if w.breakable:
                        w.kill()
                    break
            # vs tanks / player
            if not killed:
                if b.owner == "player":
                    for e in self.enemies:
                        if b.rect.colliderect(e.rect):
                            killed = True
                            e.hp -= b.DAMAGE
                            if e.hp <= 0:
                                e.kill()
                                self.enemies.remove(e)
                                self.score += 100
                            break
                else:
                    if b.rect.colliderect(p.rect):
                        killed = True
                        p.hp -= b.DAMAGE
                        if p.hp <= 0:
                            self.game_over = True
                            self.won = False
            # vs base
            if not killed and b.rect.colliderect(self.base.rect):
                killed = True
                self.base.hit()
                self.game_over = True
                self.won = False
            if not killed:
                new_bullets.add(b)
        self.bullets = new_bullets

        # win check
        if not self.enemies:
            self.game_over = True
            self.won = True

    def render(self):
        self.screen.fill(BLACK)
        self.walls.draw(self.screen)
        self.screen.blit(self.base.image, self.base.rect)
        self.tanks.draw(self.screen)
        self.bullets.draw(self.screen)
        self.player.draw_hp(self.screen)
        for e in self.enemies:
            e.draw_hp(self.screen)

        # HUD
        draw_text(self.screen, f"SCORE {self.score}", 10, 8)
        draw_text(self.screen, f"LEVEL {self.level}", WIDTH // 2 - 40, 8)
        draw_text(self.screen, f"ENEMY {len(self.enemies)}", WIDTH - 110, 8)

        if self.game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            self.screen.blit(overlay, (0, 0))
            msg = "YOU WIN!" if self.won else "GAME OVER"
            c = GREEN if self.won else RED
            t = big_font.render(msg, True, c)
            self.screen.blit(t, (WIDTH // 2 - t.get_width() // 2, HEIGHT // 2 - 40))
            draw_text(self.screen, f"最终得分: {self.score}",
                      WIDTH // 2 - 90, HEIGHT // 2 + 10)
            draw_text(self.screen, "按 Enter 重新开始, Esc 退出",
                      WIDTH // 2 - 130, HEIGHT // 2 + 45)
        elif self.paused:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.screen.blit(overlay, (0, 0))
            msg = big_font.render("PAUSED", True, YELLOW)
            self.screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - 30))
            draw_text(self.screen, "按 P 继续 / Esc 退出", WIDTH // 2 - 100, HEIGHT // 2 + 30)

        pygame.display.flip()

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
    parser.add_argument("--width", type=int, default=WIDTH, help="窗口宽度")
    parser.add_argument("--height", type=int, default=HEIGHT, help="窗口高度")
    args = parser.parse_args()
    globals()["WIDTH"] = max(320, args.width)
    globals()["HEIGHT"] = max(240, args.height)
    Game().run()


if __name__ == "__main__":
    main()
