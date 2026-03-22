import math
import matplotlib.pyplot as plt
import numpy as np


class YukiBrain:
    @staticmethod
    def get_smooth_time_weight_test(t) -> float:
        # 1. 定义基础背景 (Base Line) - 优化后的睡眠模型
        if 0 <= t < 7.8:
            if t < 1.0:
                # 快速入睡：0点到2点迅速下滑
                base = 0.7 - (t / 1.0) * 0.45
            elif 1.0 <= t < 7.0:
                # 深睡稳态：维持极低权重 (0.25)
                base = 0.25
            else:
                # 黎明回升：5点到7.2点从小幅回升，准备迎接晨间高峰
                base = 0.25 + ((t - 7.0) / 0.8) * 0.45
        elif t >= 23.8:
            # 23点后快速收尾入睡
            base = 0.9 - (t - 23.8) * 0.8
        else:
            # 白天标准基准
            base = 0.9

        # 2. 活跃峰值函数 (Gaussian Peaks)
        def peak(time, mu, sig, amp):
            return amp * math.exp(-((time - mu) ** 2) / (2 * sig ** 2))

        # --- 活跃点注入 ---
        # 晨间苏醒: 8点峰值，sigma缩窄到0.4让爆发力更集中
        morning = peak(t, 8.0, 0.6, 0.5)
        # 午后高峰: 12.8点
        lunch = peak(t, 12.8, 0.8, 0.4)
        # 晚间活跃: 20.0点，sigma较宽(1.0)模拟长夜畅谈
        evening = peak(t, 20.0, 1.5, 0.4)

        # 3. 融合结果并限幅
        weight = base + morning + lunch + evening
        return max(0.2, min(weight, 1.5))


# --- 可视化部分 ---
def plot_yuki_rhythm():
    # 生成 0.1 步长的时间序列
    t_values = [h / 10.0 for h in range(241)]
    weights = [YukiBrain.get_smooth_time_weight_test(t) for t in t_values]

    plt.figure(figsize=(12, 6))
    plt.plot(t_values, weights, label='Yuki Activity Weight', color='#ff9999', linewidth=2)

    # 填充背景色增强视觉感
    plt.fill_between(t_values, weights, 0.2, color='#ff9999', alpha=0.2)

    # 标记关键点
    peaks = [8.0, 12.8, 20.0]
    labels = ['Morning Wake-up', 'Lunch Rush', 'Evening Peak']
    for p, l in zip(peaks, labels):
        plt.axvline(x=p, color='gray', linestyle='--', alpha=0.5)
        plt.text(p, 1.45, l, horizontalalignment='center', fontsize=9)

    plt.title("Yuki's Circadian Rhythm Model (v3.2 Improved)", fontsize=14)
    plt.xlabel("Time of Day (Hours)", fontsize=12)
    plt.ylabel("Activity Weight (λ)", fontsize=12)
    plt.xticks(range(0, 25))
    plt.ylim(0, 1.6)
    plt.grid(True, which='both', linestyle=':', alpha=0.6)
    plt.legend()

    print("Plotting complete. Displaying the soul of Yuki...")
    plt.show()


if __name__ == "__main__":
    # 打印部分采样数据
    for h in range(0, 241, 10):
        t = h / 10.0
        w = YukiBrain.get_smooth_time_weight_test(t)
        status = "Deep Sleep" if w < 0.4 else "Active"
        print(f"Time {t:04.1f} | Weight: {w:.2f} | Status: {status}")

    plot_yuki_rhythm()