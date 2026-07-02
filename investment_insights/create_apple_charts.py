#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate charts for Apple iPhone China sales analysis article
"""

import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = '#f8f9fa'

# Chart 1: iPhone China Sales Growth Comparison
fig1, ax1 = plt.subplots(figsize=(10, 6))

models = ['iPhone 16\n(Sept 2024)', 'iPhone 17\n(Sept 2025)']
growth_rates = [-5, 22]
colors = ['#ff6b6b' if x < 0 else '#51cf66' for x in growth_rates]

bars = ax1.bar(models, growth_rates, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

# Add value labels on bars
for bar, value in zip(bars, growth_rates):
    height = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2., height,
             f'{value:+d}%',
             ha='center', va='bottom' if value > 0 else 'top',
             fontsize=16, fontweight='bold')

ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
ax1.set_ylabel('YoY Sales Growth Rate (%)', fontsize=12, fontweight='bold')
ax1.set_title('iPhone First-Month Sales Growth in China:\niPhone 16 vs iPhone 17',
              fontsize=14, fontweight='bold', pad=20)
ax1.set_ylim(-10, 30)
ax1.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/iphone_china_sales_growth.jpg',
            dpi=300, bbox_inches='tight')
print("Chart 1 saved: iphone_china_sales_growth.jpg")
plt.close()

# Chart 2: Tech Stocks Performance Comparison (November 2025)
fig2, ax2 = plt.subplots(figsize=(10, 6))

companies = ['Apple', 'Meta', 'Amazon', 'Nvidia', 'Tesla']
nov_returns = [3, -7, -9, -10, -12]
colors_2 = ['#51cf66' if x > 0 else '#ff6b6b' for x in nov_returns]

bars2 = ax2.barh(companies, nov_returns, color=colors_2, alpha=0.8, edgecolor='black', linewidth=1.5)

# Add value labels
for bar, value in zip(bars2, nov_returns):
    width = bar.get_width()
    ax2.text(width, bar.get_y() + bar.get_height()/2.,
             f'{value:+d}%',
             ha='left' if value > 0 else 'right',
             va='center',
             fontsize=13, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
ax2.set_xlabel('Stock Return in November 2025 (%)', fontsize=12, fontweight='bold')
ax2.set_title('Big Tech Stock Performance Comparison\n(November 2025)',
              fontsize=14, fontweight='bold', pad=20)
ax2.set_xlim(-15, 5)
ax2.grid(axis='x', alpha=0.3)

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/tech_stocks_nov_comparison.jpg',
            dpi=300, bbox_inches='tight')
print("Chart 2 saved: tech_stocks_nov_comparison.jpg")
plt.close()

# Chart 3: Apple Q4 2025 Revenue Breakdown
fig3, ax3 = plt.subplots(figsize=(10, 7))

segments = ['iPhone', 'Services', 'Mac', 'iPad', 'Wearables &\nAccessories']
revenue = [49.03, 28.8, 8.72, 6.95, 9.0]  # in billions
colors_3 = ['#ff6b6b', '#51cf66', '#4dabf7', '#ffd43b', '#ff8787']

bars3 = ax3.bar(segments, revenue, color=colors_3, alpha=0.8, edgecolor='black', linewidth=1.5)

# Add value labels
for bar, value in zip(bars3, revenue):
    height = bar.get_height()
    ax3.text(bar.get_x() + bar.get_width()/2., height,
             f'${value:.1f}B',
             ha='center', va='bottom',
             fontsize=12, fontweight='bold')

ax3.set_ylabel('Revenue (Billion USD)', fontsize=12, fontweight='bold')
ax3.set_title('Apple Q4 2025 Revenue by Segment\n(Total: $102.5B, +8% YoY)',
              fontsize=14, fontweight='bold', pad=20)
ax3.set_ylim(0, 55)
ax3.grid(axis='y', alpha=0.3)

# Add growth indicators
growth_indicators = ['+6%', '+15%', '+13%', 'Flat', '+5%']
for bar, indicator in zip(bars3, growth_indicators):
    ax3.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 2,
             indicator,
             ha='center', va='bottom',
             fontsize=10, fontweight='bold', color='green' if '+' in indicator else 'gray',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/apple_q4_revenue_breakdown.jpg',
            dpi=300, bbox_inches='tight')
print("Chart 3 saved: apple_q4_revenue_breakdown.jpg")
plt.close()

# Chart 4: China Smartphone Market Share (2024 Q4)
fig4, ax4 = plt.subplots(figsize=(10, 6))

brands = ['Huawei', 'Xiaomi', 'Apple', 'vivo', 'OPPO']
market_share = [18.1, 17.2, 17.1, 16.5, 14.2]
colors_4 = ['#e03131', '#ff6b6b', '#495057', '#4dabf7', '#51cf66']

bars4 = ax4.bar(brands, market_share, color=colors_4, alpha=0.8, edgecolor='black', linewidth=1.5)

# Add value labels
for bar, value in zip(bars4, market_share):
    height = bar.get_height()
    ax4.text(bar.get_x() + bar.get_width()/2., height,
             f'{value:.1f}%',
             ha='center', va='bottom',
             fontsize=13, fontweight='bold')

ax4.set_ylabel('Market Share (%)', fontsize=12, fontweight='bold')
ax4.set_title('China Smartphone Market Share\n(Q4 2024)',
              fontsize=14, fontweight='bold', pad=20)
ax4.set_ylim(0, 22)
ax4.grid(axis='y', alpha=0.3)

# Highlight Apple
apple_bar = bars4[2]
apple_bar.set_edgecolor('red')
apple_bar.set_linewidth(3)

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/china_smartphone_market_share.jpg',
            dpi=300, bbox_inches='tight')
print("Chart 4 saved: china_smartphone_market_share.jpg")
plt.close()

print("\n✅ All charts generated successfully!")
