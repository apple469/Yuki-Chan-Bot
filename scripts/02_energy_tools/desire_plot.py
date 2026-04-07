import numpy as np
import matplotlib.pyplot as plt
import math

# 配置参数（同步你的代码逻辑）
SIGMOID_ALPHA = 0.15
SIGMOID_CENTRE = 40.0


def get_yuki_weight(t):
    # 你的最终版生物钟逻辑
    if 0 <= t < 7.8:
        if t < 1.0:
            base = 0.7 - (t / 1.0) * 0.45
        elif 1.0 <= t < 7.0:
            base = 0.25
        else:
            base = 0.25 + ((t - 7.0) / 0.8) * 0.45
    elif t >= 23.8:
        base = 0.9 - (t - 23.8) * 0.8
    else:
        base = 0.9

    peak = lambda time, mu, sig, amp: amp * math.exp(-((time - mu) ** 2) / (2 * sig ** 2))
    w = base + peak(t, 8.0, 0.6, 0.5) + peak(t, 12.8, 0.8, 0.4) + peak(t, 20.0, 1.5, 0.4)
    return max(0.2, min(w, 1.5))


def calc_final_desire(t, activity, energy=100):
    tw = get_yuki_weight(t)
    recent_level = min(activity / 5.0, 1.0)

    # 模式 A: 跟风 (80系)
    follow = recent_level * 80 * (energy / 100)
    # 模式 B: 破冰 (60系)
    ice_break = (1.0 - recent_level) * 60 * max(0, (energy - 60) / 40)

    total = max(follow, ice_break) * tw
    normalized = 100 / (1 + math.exp(-SIGMOID_ALPHA * (total - SIGMOID_CENTRE)))
    return normalized


# 准备网格数据
t_range = np.linspace(0, 24, 100)
a_range = np.linspace(0, 10, 100)
T, A = np.meshgrid(t_range, a_range)

# 计算 Z 轴 (Desire)
Z = np.array([[calc_final_desire(t, a) for t in t_range] for a in a_range])

# 绘图
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')

# 使用 cmap='viridis' 或 'magma' 展现欲望强度
surf = ax.plot_surface(T, A, Z, cmap='magma', edgecolor='none', alpha=0.9)

# 设置轴标签
ax.set_xlabel('Time (Hour)')
ax.set_ylabel('Group Activity (0-10)')
ax.set_zlabel('Yuki Desire (%)')
ax.set_title("Yuki's 3D Desire Landscape", fontsize=15)

# 调整视角以便观察
ax.view_init(elev=30, azim=220)

fig.colorbar(surf, shrink=0.5, aspect=5)
plt.show()