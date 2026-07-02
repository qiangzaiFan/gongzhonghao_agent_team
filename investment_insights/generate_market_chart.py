import matplotlib.pyplot as plt
import numpy as np

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
fig, ax = plt.subplots(figsize=(12, 7))

# Data for the week Nov 17-21, 2025
days = ['Mon\nNov 17', 'Tue\nNov 18', 'Wed\nNov 19', 'Thu\nNov 20', 'Fri\nNov 21']

# Daily percentage changes
sp500_changes = [-0.92, -0.83, 0.38, -1.6, 0.98]
nasdaq_changes = [-0.84, -1.21, 0.59, -2.2, 0.88]
dow_changes = [-1.18, -1.07, 0.10, -0.86, 1.08]

x = np.arange(len(days))
width = 0.25

# Create bars
bars1 = ax.bar(x - width, sp500_changes, width, label='S&P 500', color='#2E86AB', alpha=0.85)
bars2 = ax.bar(x, nasdaq_changes, width, label='Nasdaq', color='#A23B72', alpha=0.85)
bars3 = ax.bar(x + width, dow_changes, width, label='Dow Jones', color='#F18F01', alpha=0.85)

# Customize the chart
ax.set_ylabel('Daily Change (%)', fontsize=12, fontweight='bold')
ax.set_title('US Stock Market Weekly Performance\nNovember 17-21, 2025', fontsize=16, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(days, fontsize=10)
ax.legend(loc='upper left', fontsize=10)

# Add horizontal line at 0
ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

# Add value labels on bars
def add_labels(bars):
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3 if height >= 0 else -12),
                    textcoords="offset points",
                    ha='center', va='bottom' if height >= 0 else 'top',
                    fontsize=8)

add_labels(bars1)
add_labels(bars2)
add_labels(bars3)

# Add weekly summary text
weekly_text = 'Weekly Total: S&P 500 -2.0% | Nasdaq -2.7% | Dow -2.0%'
ax.text(0.5, -0.15, weekly_text, transform=ax.transAxes, fontsize=11,
        ha='center', fontweight='bold', color='#333333')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/us_market_weekly_chart.png',
            dpi=150, bbox_inches='tight', facecolor='white')
plt.close()

print("Chart saved successfully!")
