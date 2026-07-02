import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
from matplotlib import rcParams

# Set up Chinese font (using DejaVu as fallback, all labels will be in English)
rcParams['font.size'] = 11
rcParams['font.family'] = 'DejaVu Sans'

# Create figure with subplots
fig = plt.figure(figsize=(16, 10))

# Chart 1: AWS Revenue Growth Trend (Q1 2025 - Q3 2025)
ax1 = fig.add_subplot(2, 2, 1)
quarters = ['Q1 2025', 'Q2 2025', 'Q3 2025']
revenue = [30.0, 31.5, 33.0]  # Billion USD
growth_rate = [17, 18, 20]  # Percentage

x = np.arange(len(quarters))
width = 0.35

bars1 = ax1.bar(x - width/2, revenue, width, label='Revenue (Billion USD)', color='#FF9900', alpha=0.8)
ax1.set_ylabel('Revenue (Billion USD)', fontsize=12, fontweight='bold')
ax1.set_xlabel('Quarter', fontsize=12, fontweight='bold')
ax1.set_title('AWS Revenue Growth Acceleration\nQ1-Q3 2025', fontsize=14, fontweight='bold', pad=20)
ax1.set_xticks(x)
ax1.set_xticklabels(quarters)
ax1.legend(loc='upper left')
ax1.grid(axis='y', alpha=0.3, linestyle='--')

# Add growth rate line
ax2 = ax1.twinx()
line = ax2.plot(x, growth_rate, color='#232F3E', marker='o', linewidth=3, markersize=8, label='YoY Growth Rate (%)')
ax2.set_ylabel('YoY Growth Rate (%)', fontsize=12, fontweight='bold')
ax2.legend(loc='upper right')
ax2.set_ylim(15, 22)

# Add value labels
for i, (v, g) in enumerate(zip(revenue, growth_rate)):
    ax1.text(i - width/2, v + 0.5, f'${v}B', ha='center', va='bottom', fontweight='bold', fontsize=10)
    ax2.text(i, g + 0.5, f'{g}%', ha='center', va='bottom', fontweight='bold', fontsize=10, color='#232F3E')

# Chart 2: Cloud Market Share Comparison Q3 2025
ax3 = fig.add_subplot(2, 2, 2)
providers = ['AWS', 'Azure', 'Google\nCloud', 'Others']
market_share = [29, 20, 13, 38]
colors = ['#FF9900', '#0078D4', '#4285F4', '#CCCCCC']

wedges, texts, autotexts = ax3.pie(market_share, labels=providers, autopct='%1.0f%%',
                                     colors=colors, startangle=90, textprops={'fontsize': 11, 'fontweight': 'bold'})
ax3.set_title('Cloud Market Share Q3 2025\nGlobal Infrastructure Services', fontsize=14, fontweight='bold', pad=20)

# Make percentage text more visible
for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontsize(12)
    autotext.set_fontweight('bold')

# Chart 3: Growth Rate Comparison - AWS vs Competitors
ax4 = fig.add_subplot(2, 2, 3)
companies = ['AWS', 'Azure', 'Google Cloud']
q3_growth = [20, 40, 34]
colors_growth = ['#FF9900', '#0078D4', '#4285F4']

bars = ax4.barh(companies, q3_growth, color=colors_growth, alpha=0.8)
ax4.set_xlabel('Q3 2025 YoY Growth Rate (%)', fontsize=12, fontweight='bold')
ax4.set_title('Q3 2025 Cloud Growth Rate Comparison', fontsize=14, fontweight='bold', pad=20)
ax4.grid(axis='x', alpha=0.3, linestyle='--')

# Add value labels
for i, (bar, val) in enumerate(zip(bars, q3_growth)):
    ax4.text(val + 1, i, f'{val}%', va='center', fontweight='bold', fontsize=11)

# Chart 4: AWS Operating Income & Margin
ax5 = fig.add_subplot(2, 2, 4)
quarters_income = ['Q1 2025', 'Q2 2025', 'Q3 2025']
operating_income = [10.2, 10.8, 11.4]  # Billion USD
operating_margin = [34.0, 34.3, 34.5]  # Percentage

x2 = np.arange(len(quarters_income))
bars2 = ax5.bar(x2, operating_income, color='#146EB4', alpha=0.8, label='Operating Income (Billion USD)')
ax5.set_ylabel('Operating Income (Billion USD)', fontsize=12, fontweight='bold')
ax5.set_xlabel('Quarter', fontsize=12, fontweight='bold')
ax5.set_title('AWS Operating Income & Margin\nQ1-Q3 2025', fontsize=14, fontweight='bold', pad=20)
ax5.set_xticks(x2)
ax5.set_xticklabels(quarters_income)
ax5.legend(loc='upper left')
ax5.grid(axis='y', alpha=0.3, linestyle='--')

# Add margin line
ax6 = ax5.twinx()
line2 = ax6.plot(x2, operating_margin, color='#FF9900', marker='s', linewidth=3, markersize=8, label='Operating Margin (%)')
ax6.set_ylabel('Operating Margin (%)', fontsize=12, fontweight='bold')
ax6.legend(loc='upper right')
ax6.set_ylim(32, 36)

# Add value labels
for i, (income, margin) in enumerate(zip(operating_income, operating_margin)):
    ax5.text(i, income + 0.2, f'${income}B', ha='center', va='bottom', fontweight='bold', fontsize=10)
    ax6.text(i, margin + 0.3, f'{margin}%', ha='center', va='bottom', fontweight='bold', fontsize=10, color='#FF9900')

plt.tight_layout(pad=3.0)
plt.savefig('/home/floodsung/media_agents/investment_insights/images/aws_q3_2025_comprehensive_analysis.png',
            dpi=300, bbox_inches='tight', facecolor='white')
print("Chart 1 saved: aws_q3_2025_comprehensive_analysis.png")
plt.close()

# Create a second chart: AWS vs Competitors Revenue Comparison
fig2, ax = plt.subplots(figsize=(12, 7))

companies_rev = ['AWS', 'Azure*', 'Google Cloud']
q3_2025_revenue = [33.0, 31.0, 14.0]  # Billion USD (Azure is estimated from Intelligent Cloud segment)
colors_rev = ['#FF9900', '#0078D4', '#4285F4']

x_pos = np.arange(len(companies_rev))
bars = ax.bar(x_pos, q3_2025_revenue, color=colors_rev, alpha=0.85, width=0.6)

ax.set_ylabel('Q3 2025 Revenue (Billion USD)', fontsize=13, fontweight='bold')
ax.set_xlabel('Cloud Service Provider', fontsize=13, fontweight='bold')
ax.set_title('Q3 2025 Cloud Revenue Comparison\nAWS Maintains Leadership Position',
             fontsize=15, fontweight='bold', pad=20)
ax.set_xticks(x_pos)
ax.set_xticklabels(companies_rev, fontsize=12)
ax.grid(axis='y', alpha=0.3, linestyle='--')

# Add value labels on bars
for i, (bar, val) in enumerate(zip(bars, q3_2025_revenue)):
    ax.text(bar.get_x() + bar.get_width()/2, val + 0.5,
            f'${val}B', ha='center', va='bottom', fontweight='bold', fontsize=12)

# Add note
ax.text(0.5, -0.15, '*Azure revenue estimated from Microsoft Intelligent Cloud segment',
        transform=ax.transAxes, ha='center', fontsize=9, style='italic', color='gray')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/aws_revenue_comparison_q3_2025.png',
            dpi=300, bbox_inches='tight', facecolor='white')
print("Chart 2 saved: aws_revenue_comparison_q3_2025.png")
plt.close()

print("\nAll charts generated successfully!")
