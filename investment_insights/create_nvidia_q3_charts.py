import matplotlib.pyplot as plt
import numpy as np

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'

# Chart 1: NVIDIA Quarterly Revenue Trend
fig, ax = plt.subplots(figsize=(12, 6))

quarters = ['Q3 FY24', 'Q4 FY24', 'Q1 FY25', 'Q2 FY25', 'Q3 FY25', 'Q4 FY25 (Guidance)']
revenue = [35.08, 41.1, 46.74, 46.74, 57.01, 65.0]
colors = ['#76B900' if i < 5 else '#FFB900' for i in range(6)]

bars = ax.bar(quarters, revenue, color=colors, edgecolor='black', linewidth=0.5)

# Add value labels on bars
for bar, val in zip(bars, revenue):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 1,
            f'${val}B',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

# Add YoY growth annotation for Q3
ax.annotate('YoY +62%', xy=(4, 57.01), xytext=(4.3, 50),
            fontsize=10, color='#76B900', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#76B900', lw=1.5))

ax.set_ylabel('Revenue (Billion USD)', fontsize=12, fontweight='bold')
ax.set_title('NVIDIA Quarterly Revenue Trend - Q3 FY2026 Results', fontsize=14, fontweight='bold', pad=20)
ax.set_ylim(0, 75)

# Add legend for guidance
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor='#76B900', label='Actual Revenue'),
                   Patch(facecolor='#FFB900', label='Q4 Guidance')]
ax.legend(handles=legend_elements, loc='upper left')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/nvidia_q3_revenue_trend.png', dpi=150, bbox_inches='tight')
plt.close()

# Chart 2: Revenue Breakdown by Segment
fig, ax = plt.subplots(figsize=(10, 8))

segments = ['Data Center', 'Gaming', 'Professional\nVisualization', 'Automotive']
revenue_breakdown = [51.2, 4.3, 0.76, 0.592]
yoy_growth = [66, 30, 56, 32]
colors = ['#76B900', '#4CAF50', '#8BC34A', '#CDDC39']

# Create horizontal bar chart
bars = ax.barh(segments, revenue_breakdown, color=colors, edgecolor='black', linewidth=0.5)

# Add value labels
for bar, val, growth in zip(bars, revenue_breakdown, yoy_growth):
    width = bar.get_width()
    ax.text(width + 0.5, bar.get_y() + bar.get_height()/2.,
            f'${val}B (+{growth}% YoY)',
            ha='left', va='center', fontsize=11, fontweight='bold')

ax.set_xlabel('Revenue (Billion USD)', fontsize=12, fontweight='bold')
ax.set_title('NVIDIA Q3 FY2026 Revenue Breakdown by Segment', fontsize=14, fontweight='bold', pad=20)
ax.set_xlim(0, 60)

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/nvidia_q3_revenue_breakdown.png', dpi=150, bbox_inches='tight')
plt.close()

print("Charts created successfully!")
print("1. nvidia_q3_revenue_trend.png")
print("2. nvidia_q3_revenue_breakdown.png")
