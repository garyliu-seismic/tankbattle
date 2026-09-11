# 坦克大战 (Tank Battle)

一款使用 **pygame** 实现的经典坦克大战游戏（灵感源自 Battle City / 红白机坦克大战）。

## 玩法

- 保护你的基地（屏幕下方中间的鹰标 🦅）。
- 击溃每一关的所有敌方坦克即可过关。
- 地图中可分为**砖墙**（可击碎）和**钢墙**（不可击碎）。
- 关卡连续、难度递增，直到被敌方子弹击中、坦克被毁或基地被攻破为止。

## 操作

| 按键 | 功能 |
| :--- | :--- |
| 方向键 / `WASD` | 移动坦克 |
| `空格` / `J` | 发射子弹 |
| `P` | 暂停 / 继续 |
| `Enter` | 开局 / 重新开始 |
| `Esc` | 退出 |

## 技术规格

- 引擎：[pygame 2](https://pygame.org)（Python 3.12）
- 地图：20 × 15 网格，94 面墙体（其中 **26 面砖墙**、**68 面钢墙**）
- 每关固定 **6 个敌方坦克**
- 坐标系：640 × 480，`CELL_SIZE = 32` 像素方格墙

## 运行

```bash
# 在项目目录中
cd c:\project_new\tankbattle
python tank_battle.py
```

## 单元测试

包含覆盖状态、移动、射击/击杀逻辑的单元测试：

```bash
python -m pytest test_game.py -v
```

## 项目结构

```
tankbattle/
├── tank_battle.py    # 游戏主程序 (pygame)
├── test_game.py      # 单元测试
├── README.md         # 说明文档
├── ENHANCEMENT_PLAN.md  # 后续改进计划
└── .gitignore
```
