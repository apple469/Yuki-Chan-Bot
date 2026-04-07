import numpy as np
import matplotlib.pyplot as plt
import math

# 配置参数
SIGMOID_ALPHA = 0.15
SIGMOID_CENTRE = 40.0
FIXED_TIME_WEIGHT = 1.2  # 假设在白天活跃时段


def calc_energy_desire(energy, activity):
    # 模拟你的逻辑
    recent_level = min(activity / 5.0, 1.0)

    # 模式 A: 跟风 (随 Energy 线性增长)
    follow = recent_level * 80 * (energy / 100.0)

    # 模式 B: 破冰 (Energy > 60 才有戏，且斜率极大)
    ice_break_factor = max(0, (energy - 60) / 40.0)
    ice_break = (1.0 - recent_level) * 60 * ice_break_factor

    total = max(follow, ice_break) * FIXED_TIME_WEIGHT
    normalized = 100 / (1 + math.exp(-SIGMOID_ALPHA * (total - SIGMOID_CENTRE)))
    return normalized


# 准备网格数据
e_range = np.linspace(0, 100, 100)  # 精力从 0 到 100
a_range = np.linspace(0, 10, 100)  # 活跃度从 0 到 10
E, A = np.meshgrid(e_range, a_range)

# 计算 Z 轴
Z = np.array([[calc_energy_desire(e, a) for e in e_range] for a in a_range])

# 绘图
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')

surf = ax.plot_surface(E, A, Z, cmap='plasma', edgecolor='none', alpha=0.9)

ax.set_xlabel('Energy (0-100)')
ax.set_ylabel('Group Activity (0-10)')
ax.set_zlabel('Desire (%)')
ax.set_title("Yuki's Desire: Energy vs. Activity (Fixed TimeWeight=1.2)", fontsize=14)

# 视角调整：从高 Energy 侧看过去
ax.view_init(elev=30, azim=130)

fig.colorbar(surf, shrink=0.5, aspect=5)
plt.show()