"""坦克大战游戏逻辑的无头单元测试"""
import sys
sys.path.insert(0, ".")
import pytest
import pygame
import tank_battle as t
from tank_battle import WIDTH, HEIGHT

@pytest.fixture(scope="module")
def game():
    pygame.init()
    pygame.display.set_mode((t.WIDTH, t.HEIGHT))
    return t.Game()


def test_game_state(game):
    assert game.player.hp >= 1
    assert len(game.enemies) >= 1
    assert game.base.alive


def test_player_moves(game):
    p = game.player
    # 移到开阔区域再测试,避免贴在屏幕边缘无法位移
    p.rect.center = (WIDTH // 2, HEIGHT // 2)
    before = p.rect
    p.move("down", game.walls, game.tanks)
    assert p.rect != before
    assert p.rect.top > before.top


def test_shoot_and_enemy_hit(game):
    b = game.player.shoot(game.bullets)
    assert b is not None and b.owner == "player"
    assert game.player.cooldown > 0
    # 直接消灭剩余敌人,验证胜利流程
    for enemy in list(game.enemies):
        enemy.kill()
        game.enemies.remove(enemy)
    game.update()
    assert game.won
    assert game.game_over


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
