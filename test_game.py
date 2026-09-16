"""坦克大战游戏逻辑的无头单元测试"""
import sys
sys.path.insert(0, ".")
import pytest
import pygame
import tank_battle as t
from tank_battle import WIDTH, HEIGHT
from levels import LEVELS, TOTAL_LEVELS, ENEMY_TYPES

pygame.init()
pygame.display.set_mode((WIDTH, HEIGHT))


@pytest.fixture()
def game():
    g = t.Game()
    g.state = "play"
    g.intro_timer = 0
    return g


# ---------- 关卡数据 ----------
def test_levels_data():
    assert TOTAL_LEVELS == 10
    for i, lv in enumerate(LEVELS):
        layout = lv["layout"]
        assert len(layout) == 15, f"level {i+1} row count"
        for row in layout:
            assert len(row) == 20, f"level {i+1} bad width: {row!r}"
            assert all(ch in ".#-~*/" for ch in row)
        assert sum(lv["enemy_mix"].values()) == lv["total_enemies"]


def test_enemy_types():
    for kind in ("normal", "fast", "power", "armor"):
        cfg = ENEMY_TYPES[kind]
        assert cfg["speed"] >= 1
        assert cfg["hp"] >= 1
        assert cfg["score"] > 0


# ---------- 游戏状态 ----------
def test_game_state(game):
    assert game.player.hp >= 1
    assert game.base.alive
    assert game.level_cfg is not None
    assert len(game.enemy_queue) == game.level_cfg["total_enemies"]


def test_player_moves(game):
    p = game.player
    p.rect.center = (WIDTH // 2, HEIGHT // 2)
    before = p.rect.copy()
    p.move("down", game.walls, game.tanks)
    assert p.rect != before
    assert p.rect.top > before.top


def test_shoot_creates_bullet(game):
    b = game.player.shoot(game.bullets)
    assert b is not None and b.owner == "player"
    assert game.player.cooldown > 0


def test_kill_enemy_scores(game):
    game.enemy_queue = ["normal"]
    game.spawn_enemy()
    assert len(game.enemies) == 1
    e = game.enemies[0]
    before = game.score
    game._kill_enemy(e)
    assert game.score == before + e.score_value
    assert e not in game.enemies


# ---------- 关卡推进 ----------
def test_level_progression(game):
    # 清空第 1 关敌人 -> 进入第 2 关
    game.enemy_queue = []
    for e in list(game.enemies):
        e.kill()
        game.enemies.remove(e)
    game.update()
    assert game.level == 2
    assert game.state == "intro"


def test_final_victory(game):
    game.level = TOTAL_LEVELS
    game._load_level(game.level)
    game.state = "play"
    game.enemy_queue = []
    for e in list(game.enemies):
        e.kill()
        game.enemies.remove(e)
    game.update()
    assert game.state == "victory"


def test_levels_increasing_difficulty():
    totals = [lv["total_enemies"] for lv in LEVELS]
    assert totals == sorted(totals)
    assert totals[-1] > totals[0]


# ---------- 地形 ----------
def test_make_map_terrain():
    # 第 7 关包含水域/草丛/冰面混合地形
    layout = LEVELS[6]["layout"]
    walls, grass, ice = t.make_map(layout)
    kinds = {w.kind for w in walls}
    assert "water" in kinds
    assert len(grass) > 0
    assert len(ice) > 0


def test_water_blocks_tank():
    layout = [
        "--------------------",
        "-..................-",
        "-..~~~........~~~..-",
        "-..~~~........~~~..-",
        "-..................-",
        "-..................-",
        "-..................-",
        "-..................-",
        "-..................-",
        "-..................-",
        "-..................-",
        "-..................-",
        "-..................-",
        "-..................-",
        "--------------------",
    ]
    walls, grass, ice = t.make_map(layout)
    water = [w for w in walls if w.kind == "water"]
    assert water
    # 造一辆坦克放在水域正下方, 尝试向上移动应被阻挡
    w = water[0]
    tank = t.Tank(w.rect.centerx - 16, w.rect.bottom, "player")
    tanks = pygame.sprite.Group(tank)
    before = tank.rect.copy()
    tank.move("up", walls, tanks)
    assert tank.rect == before


# ---------- 道具 ----------
def test_powerup_heal(game):
    p = game.player
    p.hp = 1
    p.apply_powerup("heal")
    assert p.hp >= 2


def test_powerup_shield(game):
    p = game.player
    p.apply_powerup("shield")
    assert p.invincible


def test_powerup_rapid(game):
    p = game.player
    p.apply_powerup("rapid")
    assert p.rapid_timer > 0


def test_powerup_star(game):
    p = game.player
    before = p.max_hp
    p.apply_powerup("star")
    assert p.max_hp > before


def test_powerup_bomb_clears_enemies(game):
    game.enemy_queue = ["normal", "normal", "normal"]
    for _ in range(3):
        game.spawn_enemy()
    assert len(game.enemies) == 3
    game._detonate_bomb()
    assert len(game.enemies) == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
