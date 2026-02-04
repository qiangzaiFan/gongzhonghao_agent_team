import matplotlib.pyplot as plt
import matplotlib
import numpy as np

# Use non-interactive backend
matplotlib.use('Agg')

# Set Chinese font - try multiple options
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# Output directory
output_dir = '/home/floodsung/media_agents/investment_insights/images/'

# Chart 1: Revenue and Delivery Growth (Q3 2024 vs Q3 2025)
fig, ax = plt.subplots(1, 2, figsize=(14, 6))

# Revenue comparison
quarters = ['Q3 2024', 'Q3 2025']
revenue = [10.1, 20.38]
colors = ['#4a90e2', '#e74c3c']

ax[0].bar(quarters, revenue, color=colors, alpha=0.8)
ax[0].set_ylabel('Revenue (Billion RMB)', fontsize=12)
ax[0].set_title('XPeng Quarterly Revenue Comparison', fontsize=14, fontweight='bold')
ax[0].set_ylim(0, 25)

# Add value labels
for i, v in enumerate(revenue):
    ax[0].text(i, v + 0.5, f'{v}B', ha='center', fontsize=11, fontweight='bold')

# Add growth rate
ax[0].text(1, 18, '+101.8% YoY', ha='center', fontsize=11, color='green', fontweight='bold',
           bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))

# Delivery comparison
deliveries = [46.5, 116.0]
ax[1].bar(quarters, deliveries, color=colors, alpha=0.8)
ax[1].set_ylabel('Deliveries (Thousand Units)', fontsize=12)
ax[1].set_title('XPeng Quarterly Deliveries Comparison', fontsize=14, fontweight='bold')
ax[1].set_ylim(0, 130)

# Add value labels
for i, v in enumerate(deliveries):
    ax[1].text(i, v + 3, f'{v}K', ha='center', fontsize=11, fontweight='bold')

# Add growth rate
ax[1].text(1, 102, '+149.3% YoY', ha='center', fontsize=11, color='green', fontweight='bold',
           bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))

plt.tight_layout()
plt.savefig(f'{output_dir}xpeng_revenue_delivery_comparison.jpg', dpi=150, bbox_inches='tight')
plt.close()

# Chart 2: Gross Margin Trend
fig, ax = plt.subplots(figsize=(12, 7))

quarters_margin = ['Q3 2024', 'Q4 2024', 'Q1 2025', 'Q2 2025', 'Q3 2025']
gross_margin = [15.3, 16.8, 18.2, 19.5, 20.1]
vehicle_margin = [8.6, 9.2, 10.5, 11.8, 13.1]

x = np.arange(len(quarters_margin))
width = 0.35

bars1 = ax.bar(x - width/2, gross_margin, width, label='Overall Gross Margin', color='#3498db', alpha=0.8)
bars2 = ax.bar(x + width/2, vehicle_margin, width, label='Vehicle Margin', color='#e67e22', alpha=0.8)

ax.set_ylabel('Margin (%)', fontsize=12)
ax.set_xlabel('Quarter', fontsize=12)
ax.set_title('XPeng Gross Margin Trend (Record High in Q3 2025)', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(quarters_margin)
ax.legend(fontsize=11)
ax.set_ylim(0, 25)

# Add value labels
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.3,
                f'{height}%', ha='center', va='bottom', fontsize=9)

plt.grid(axis='y', alpha=0.3, linestyle='--')
plt.tight_layout()
plt.savefig(f'{output_dir}xpeng_margin_trend.jpg', dpi=150, bbox_inches='tight')
plt.close()

# Chart 3: Net Loss Reduction Trend
fig, ax = plt.subplots(figsize=(12, 7))

quarters_loss = ['Q3 2024', 'Q4 2024', 'Q1 2025', 'Q2 2025', 'Q3 2025']
net_loss = [-1.81, -1.52, -1.15, -0.48, -0.38]

ax.plot(quarters_loss, net_loss, marker='o', linewidth=3, markersize=10, color='#e74c3c')
ax.fill_between(range(len(quarters_loss)), net_loss, alpha=0.3, color='#e74c3c')

ax.set_ylabel('Net Loss (Billion RMB)', fontsize=12)
ax.set_xlabel('Quarter', fontsize=12)
ax.set_title('XPeng Net Loss Narrowing Trend (8 Consecutive Quarters)', fontsize=14, fontweight='bold')
ax.set_ylim(-2.5, 0.5)

# Add horizontal line at 0
ax.axhline(y=0, color='green', linestyle='--', linewidth=2, alpha=0.5, label='Break-even')

# Add value labels
for i, v in enumerate(net_loss):
    ax.text(i, v - 0.15, f'{v}B', ha='center', fontsize=10, fontweight='bold')

# Highlight Q3 2025
ax.plot(4, net_loss[4], marker='*', markersize=20, color='gold', markeredgecolor='black', markeredgewidth=1.5)
ax.text(4, net_loss[4] + 0.25, 'Q3 2025: -0.38B\n(Lowest since Q3 2020)', ha='center', fontsize=10,
        bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.6))

ax.legend(fontsize=11)
ax.grid(True, alpha=0.3, linestyle='--')
plt.tight_layout()
plt.savefig(f'{output_dir}xpeng_net_loss_trend.jpg', dpi=150, bbox_inches='tight')
plt.close()

# Chart 4: Competitive Comparison (Q3 2025)
fig, ax = plt.subplots(figsize=(12, 8))

companies = ['XPeng', 'NIO\n(Est.)', 'Li Auto\n(Est.)', 'BYD']
deliveries_comp = [116.0, 87.1, 152.8, 1114.2]
margins_comp = [13.1, 10.5, 21.5, 17.6]

x = np.arange(len(companies))
width = 0.35

# Create dual-axis chart
ax1 = ax
ax2 = ax1.twinx()

bars1 = ax1.bar(x - width/2, deliveries_comp, width, label='Q3 Deliveries (K)', color='#3498db', alpha=0.8)
bars2 = ax2.bar(x + width/2, margins_comp, width, label='Vehicle Margin (%)', color='#2ecc71', alpha=0.8)

ax1.set_ylabel('Deliveries (Thousand Units)', fontsize=12, color='#3498db')
ax2.set_ylabel('Vehicle Margin (%)', fontsize=12, color='#2ecc71')
ax1.set_xlabel('Company', fontsize=12)
ax1.set_title('China EV Makers Q3 2025 Comparison', fontsize=14, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(companies)

# Add value labels
for bar in bars1:
    height = bar.get_height()
    if height > 500:
        ax1.text(bar.get_x() + bar.get_width()/2., height + 30,
                f'{height:.0f}K', ha='center', va='bottom', fontsize=9, color='#3498db', fontweight='bold')
    else:
        ax1.text(bar.get_x() + bar.get_width()/2., height + 5,
                f'{height:.1f}K', ha='center', va='bottom', fontsize=9, color='#3498db', fontweight='bold')

for bar in bars2:
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
            f'{height:.1f}%', ha='center', va='bottom', fontsize=9, color='#2ecc71', fontweight='bold')

# Add legends
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=11)

ax1.tick_params(axis='y', labelcolor='#3498db')
ax2.tick_params(axis='y', labelcolor='#2ecc71')

plt.tight_layout()
plt.savefig(f'{output_dir}xpeng_competitive_comparison.jpg', dpi=150, bbox_inches='tight')
plt.close()

# Chart 5: Cash Position
fig, ax = plt.subplots(figsize=(10, 6))

cash_quarters = ['Q3 2024', 'Q4 2024', 'Q1 2025', 'Q2 2025', 'Q3 2025']
cash_position = [38.5, 41.2, 43.8, 46.5, 48.33]

ax.plot(cash_quarters, cash_position, marker='D', linewidth=3, markersize=10, color='#27ae60')
ax.fill_between(range(len(cash_quarters)), cash_position, alpha=0.3, color='#27ae60')

ax.set_ylabel('Cash & Equivalents (Billion RMB)', fontsize=12)
ax.set_xlabel('Quarter', fontsize=12)
ax.set_title('XPeng Cash Position Growth', fontsize=14, fontweight='bold')
ax.set_ylim(35, 52)

# Add value labels
for i, v in enumerate(cash_position):
    ax.text(i, v + 0.5, f'{v}B', ha='center', fontsize=10, fontweight='bold')

ax.grid(True, alpha=0.3, linestyle='--')
plt.tight_layout()
plt.savefig(f'{output_dir}xpeng_cash_position.jpg', dpi=150, bbox_inches='tight')
plt.close()

print("All charts generated successfully!")
print(f"Charts saved to: {output_dir}")
