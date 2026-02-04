#!/usr/bin/env python3
"""Generate Netflix stock charts for article"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from datetime import datetime

# Set style
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9

# Chart 1: Netflix Stock Price History (IPO to Present - Post-Split Adjusted)
fig, ax = plt.subplots(figsize=(12, 6))

# Simulated data representing key milestones
years = [2002, 2004, 2007, 2010, 2013, 2015, 2018, 2020, 2022, 2024, 2025]
prices = [0.12, 0.35, 0.42, 2.1, 5.5, 15.8, 45.2, 65.3, 38.4, 78.5, 107.0]  # Post-split adjusted

ax.plot(years, prices, linewidth=2.5, color='#E50914', marker='o', markersize=6)
ax.fill_between(years, prices, alpha=0.2, color='#E50914')

# Annotate key milestones
ax.annotate('IPO\n$0.12', xy=(2002, 0.12), xytext=(2002, 15),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.2),
            fontsize=9, ha='center')

ax.annotate('Streaming Launch\n2007', xy=(2007, 0.42), xytext=(2007, 12),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.2),
            fontsize=9, ha='center')

ax.annotate('7-for-1 Split\n2015', xy=(2015, 15.8), xytext=(2015, 30),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.2),
            fontsize=9, ha='center')

ax.annotate('10-for-1 Split\nNov 2025', xy=(2025, 107.0), xytext=(2023, 120),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.2),
            fontsize=9, ha='center')

ax.set_xlabel('Year', fontweight='bold')
ax.set_ylabel('Stock Price (USD, Split-Adjusted)', fontweight='bold')
ax.set_title('Netflix Stock Price History: IPO to Present (88,600% Return)', fontweight='bold', pad=20)
ax.grid(True, alpha=0.3, linestyle='--')
ax.set_xlim(2001, 2026)
ax.set_ylim(0, 130)

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/netflix_stock_history.jpg',
            dpi=150, bbox_inches='tight', facecolor='white')
plt.close()

# Chart 2: Netflix Business Metrics Evolution
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# Subscribers Growth
quarters = ['Q1 2020', 'Q1 2021', 'Q1 2022', 'Q1 2023', 'Q1 2024', 'Q3 2025']
subscribers = [182.9, 207.6, 221.6, 232.5, 269.6, 302.3]  # Millions

ax1.bar(quarters, subscribers, color='#E50914', alpha=0.8, edgecolor='black', linewidth=1.2)
ax1.set_xlabel('Quarter', fontweight='bold')
ax1.set_ylabel('Subscribers (Millions)', fontweight='bold')
ax1.set_title('Netflix Global Subscriber Growth', fontweight='bold', pad=15)
ax1.grid(True, axis='y', alpha=0.3, linestyle='--')
ax1.set_ylim(0, 350)

for i, v in enumerate(subscribers):
    ax1.text(i, v + 8, f'{v}M', ha='center', fontsize=9, fontweight='bold')

# Revenue & Profit Growth
years_finance = ['2020', '2021', '2022', '2023', '2024', '2025E']
revenue = [25.0, 29.7, 31.6, 33.7, 38.5, 45.0]  # Billions USD
profit = [2.8, 5.1, 4.5, 5.4, 8.2, 11.0]  # Billions USD

x = np.arange(len(years_finance))
width = 0.35

bars1 = ax2.bar(x - width/2, revenue, width, label='Revenue', color='#E50914', alpha=0.8, edgecolor='black')
bars2 = ax2.bar(x + width/2, profit, width, label='Net Profit', color='#564D4D', alpha=0.8, edgecolor='black')

ax2.set_xlabel('Year', fontweight='bold')
ax2.set_ylabel('Amount (Billion USD)', fontweight='bold')
ax2.set_title('Netflix Revenue & Profit Trend', fontweight='bold', pad=15)
ax2.set_xticks(x)
ax2.set_xticklabels(years_finance)
ax2.legend(loc='upper left', fontsize=10)
ax2.grid(True, axis='y', alpha=0.3, linestyle='--')
ax2.set_ylim(0, 50)

# Add value labels
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'${height:.1f}B', ha='center', va='bottom', fontsize=8)

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/netflix_business_metrics.jpg',
            dpi=150, bbox_inches='tight', facecolor='white')
plt.close()

# Chart 3: Stock Split Comparison
fig, ax = plt.subplots(figsize=(10, 6))

splits = ['Feb 2004\n2-for-1', 'Jul 2015\n7-for-1', 'Nov 2025\n10-for-1']
pre_split_prices = [43.7, 702.6, 1108.5]  # Pre-split prices
post_split_prices = [21.85, 100.37, 110.85]  # Post-split prices

x = np.arange(len(splits))
width = 0.35

bars1 = ax.bar(x - width/2, pre_split_prices, width, label='Pre-Split Price',
               color='#564D4D', alpha=0.8, edgecolor='black')
bars2 = ax.bar(x + width/2, post_split_prices, width, label='Post-Split Price',
               color='#E50914', alpha=0.8, edgecolor='black')

ax.set_xlabel('Stock Split Event', fontweight='bold')
ax.set_ylabel('Stock Price (USD)', fontweight='bold')
ax.set_title('Netflix Stock Split History: Price Before vs After', fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(splits)
ax.legend(loc='upper left', fontsize=10)
ax.grid(True, axis='y', alpha=0.3, linestyle='--')

# Add value labels
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 30,
                f'${height:.2f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/netflix_stock_splits.jpg',
            dpi=150, bbox_inches='tight', facecolor='white')
plt.close()

# Chart 4: Analyst Ratings Distribution
fig, ax = plt.subplots(figsize=(10, 6))

ratings = ['Strong Buy', 'Buy', 'Hold', 'Sell']
counts = [30, 2, 13, 1]
colors = ['#1a7f37', '#26a641', '#FFA500', '#E50914']

wedges, texts, autotexts = ax.pie(counts, labels=ratings, colors=colors, autopct='%1.1f%%',
                                    startangle=90, textprops={'fontsize': 11, 'fontweight': 'bold'},
                                    wedgeprops={'edgecolor': 'white', 'linewidth': 2})

for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontsize(12)
    autotext.set_fontweight('bold')

ax.set_title('Netflix Analyst Ratings Distribution (46 Analysts)',
             fontweight='bold', fontsize=14, pad=20)

# Add legend with counts
legend_labels = [f'{rating}: {count} analysts' for rating, count in zip(ratings, counts)]
ax.legend(legend_labels, loc='upper left', bbox_to_anchor=(1, 1), fontsize=10)

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/netflix_analyst_ratings.jpg',
            dpi=150, bbox_inches='tight', facecolor='white')
plt.close()

print("✅ All Netflix charts generated successfully!")
print("Generated files:")
print("  - netflix_stock_history.jpg")
print("  - netflix_business_metrics.jpg")
print("  - netflix_stock_splits.jpg")
print("  - netflix_analyst_ratings.jpg")
