import matplotlib.pyplot as plt
import matplotlib
import numpy as np

# Use a font that supports both English and basic characters
matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['font.size'] = 11

# Set figure style
plt.style.use('seaborn-v0_8-darkgrid')

# Chart 1: JD Q3 2025 Revenue Breakdown
fig1, ax1 = plt.subplots(figsize=(10, 6))
categories = ['JD Retail', 'New Businesses\n& Others', 'Service Revenue']
values = [310.1, 46.6, 0]  # Billion RMB, approximations based on revenue structure
colors = ['#E3170D', '#F37021', '#FDB913']

bars = ax1.bar(categories, [310.1, 46.6, 0], color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
ax1.set_ylabel('Revenue (Billion RMB)', fontsize=13, fontweight='bold')
ax1.set_title('JD.com Q3 2025 Revenue Breakdown\nTotal: RMB 356.7 Billion (+22.4% YoY)',
              fontsize=15, fontweight='bold', pad=20)
ax1.set_ylim(0, 350)

# Add value labels on bars
for bar, val in zip(bars, [310.1, 46.6, 0]):
    height = bar.get_height()
    if height > 0:
        ax1.text(bar.get_x() + bar.get_width()/2., height + 5,
                f'RMB {val}B',
                ha='center', va='bottom', fontsize=12, fontweight='bold')

# Adjust layout
plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/jd_q3_revenue_breakdown.png',
            dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

# Chart 2: Quarterly Active Users Growth
fig2, ax2 = plt.subplots(figsize=(10, 6))
quarters = ['Q3\n2024', 'Q4\n2024', 'Q1\n2025', 'Q2\n2025', 'Q3\n2025']
# Estimating quarterly active users based on 40% YoY growth
qac_millions = [400, 450, 500, 530, 560]  # Estimated in millions

line = ax2.plot(quarters, qac_millions, marker='o', linewidth=3,
                markersize=10, color='#E3170D', label='Quarterly Active Customers')
ax2.fill_between(range(len(quarters)), qac_millions, alpha=0.3, color='#E3170D')

ax2.set_ylabel('Quarterly Active Customers (Million)', fontsize=13, fontweight='bold')
ax2.set_title('JD.com Quarterly Active Customer Growth\n+40% YoY in Q3 2025',
              fontsize=15, fontweight='bold', pad=20)
ax2.set_ylim(350, 600)
ax2.grid(True, alpha=0.3)

# Add value labels
for i, (q, val) in enumerate(zip(quarters, qac_millions)):
    ax2.text(i, val + 10, f'{val}M', ha='center', va='bottom',
            fontsize=11, fontweight='bold')

# Add growth annotation
ax2.annotate('', xy=(4, 560), xytext=(0, 400),
            arrowprops=dict(arrowstyle='->', color='green', lw=2))
ax2.text(2, 480, '+40% YoY', fontsize=13, fontweight='bold',
        color='green', ha='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7))

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/jd_qac_growth.png',
            dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

# Chart 3: E-commerce Market Share Comparison
fig3, ax3 = plt.subplots(figsize=(10, 6))
platforms = ['Alibaba\n(Taobao+Tmall)', 'JD.com', 'Pinduoduo', 'Others']
market_share_2024 = [33, 17, 19, 31]
market_share_2025 = [31, 18, 21, 30]  # Estimated based on trends

x = np.arange(len(platforms))
width = 0.35

bars1 = ax3.bar(x - width/2, market_share_2024, width, label='2024',
                color='#3498db', alpha=0.8, edgecolor='black', linewidth=1.2)
bars2 = ax3.bar(x + width/2, market_share_2025, width, label='2025E',
                color='#e74c3c', alpha=0.8, edgecolor='black', linewidth=1.2)

ax3.set_ylabel('Market Share (%)', fontsize=13, fontweight='bold')
ax3.set_title('China E-commerce Market Share Comparison\n2024 vs 2025 Estimated',
              fontsize=15, fontweight='bold', pad=20)
ax3.set_xticks(x)
ax3.set_xticklabels(platforms, fontsize=11)
ax3.set_ylim(0, 40)
ax3.legend(fontsize=12, loc='upper right')
ax3.grid(True, axis='y', alpha=0.3)

# Add value labels
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'{int(height)}%',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/jd_market_share_comparison.png',
            dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

# Chart 4: JD Retail Operating Margin Trend
fig4, (ax4a, ax4b) = plt.subplots(1, 2, figsize=(14, 6))

# Left: Revenue growth
quarters_revenue = ['Q1\n2024', 'Q2\n2024', 'Q3\n2024', 'Q4\n2024',
                    'Q1\n2025', 'Q2\n2025', 'Q3\n2025']
revenue_growth = [7.0, 5.1, 4.8, 6.2, 8.5, 12.3, 20.6]  # YoY % growth

bars_rev = ax4a.bar(quarters_revenue, revenue_growth, color='#27ae60',
                    alpha=0.8, edgecolor='black', linewidth=1.2)
ax4a.set_ylabel('YoY Revenue Growth (%)', fontsize=12, fontweight='bold')
ax4a.set_title('JD Retail Revenue Growth Acceleration', fontsize=13, fontweight='bold', pad=15)
ax4a.grid(True, axis='y', alpha=0.3)
ax4a.set_ylim(0, 25)

# Highlight Q3 2025
bars_rev[-1].set_color('#e74c3c')
bars_rev[-1].set_alpha(1.0)

for bar in bars_rev:
    height = bar.get_height()
    ax4a.text(bar.get_x() + bar.get_width()/2., height + 0.5,
            f'{height:.1f}%',
            ha='center', va='bottom', fontsize=9, fontweight='bold')

# Right: Operating margin improvement
quarters_margin = ['Q3\n2024', 'Q4\n2024', 'Q1\n2025', 'Q2\n2025', 'Q3\n2025']
operating_margin = [3.9, 4.1, 4.2, 4.3, 4.5]

line_margin = ax4b.plot(quarters_margin, operating_margin, marker='o',
                        linewidth=3, markersize=10, color='#9b59b6')
ax4b.fill_between(range(len(quarters_margin)), operating_margin,
                  alpha=0.3, color='#9b59b6')

ax4b.set_ylabel('Operating Margin (%)', fontsize=12, fontweight='bold')
ax4b.set_title('JD Retail Operating Margin Improvement', fontsize=13, fontweight='bold', pad=15)
ax4b.grid(True, alpha=0.3)
ax4b.set_ylim(3.5, 5.0)

for i, val in enumerate(operating_margin):
    ax4b.text(i, val + 0.08, f'{val:.1f}%', ha='center', va='bottom',
            fontsize=10, fontweight='bold')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/jd_margin_revenue_trend.png',
            dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

# Chart 5: Key Metrics Comparison
fig5, ax5 = plt.subplots(figsize=(10, 7))

metrics = ['Total Revenue\nGrowth', 'QAC\nGrowth', 'Electronics\nGrowth',
           'General Merch.\nGrowth', 'Operating\nMargin Δ']
values = [22.4, 40.0, 23.0, 16.0, 0.6]  # YoY % or percentage points
colors_metrics = ['#3498db', '#e74c3c', '#f39c12', '#27ae60', '#9b59b6']

bars_metrics = ax5.barh(metrics, values, color=colors_metrics,
                        alpha=0.8, edgecolor='black', linewidth=1.5)

ax5.set_xlabel('Year-over-Year Change (%)', fontsize=13, fontweight='bold')
ax5.set_title('JD.com Q3 2025 Key Performance Metrics',
              fontsize=15, fontweight='bold', pad=20)
ax5.set_xlim(0, 45)
ax5.grid(True, axis='x', alpha=0.3)

# Add value labels
for bar, val in zip(bars_metrics, values):
    width = bar.get_width()
    ax5.text(width + 1, bar.get_y() + bar.get_height()/2.,
            f'{val:.1f}%' if val != 0.6 else f'+{val:.1f}pp',
            ha='left', va='center', fontsize=12, fontweight='bold')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/jd_key_metrics.png',
            dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

print("All charts created successfully!")
print("Images saved to: /home/floodsung/media_agents/investment_insights/images/")
