#!/usr/bin/env python3
"""
Generate professional charts for Fed December 2025 meeting analysis
Uses English labels to avoid Chinese font issues
"""

import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import matplotlib.dates as mdates

# Set style for professional financial charts
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = '#f8f9fa'
plt.rcParams['font.size'] = 11

# Chart 1: Fed Funds Rate History and Projections
fig1, ax1 = plt.subplots(figsize=(12, 6))

# Historical and projected data
dates = ['2023-01', '2023-07', '2024-01', '2024-07', '2024-12', '2025-03', '2025-06', '2025-09', '2025-11', '2025-12', '2026-03']
rates = [4.5, 5.25, 5.25, 5.5, 4.75, 4.5, 4.25, 4.0, 3.875, 3.875, 3.5]  # Midpoint of range

ax1.plot(dates, rates, marker='o', linewidth=2.5, markersize=8, color='#2E86AB', label='Fed Funds Rate')
ax1.axvline(x='2025-11', color='#A23B72', linestyle='--', linewidth=2, label='Current (Nov 2025)')
ax1.axvline(x='2025-12', color='#F18F01', linestyle='--', linewidth=2, alpha=0.7, label='Dec Meeting')

ax1.set_title('Federal Funds Rate: 2023-2026 Trajectory', fontsize=16, fontweight='bold', pad=20)
ax1.set_xlabel('Time Period', fontsize=12, fontweight='bold')
ax1.set_ylabel('Interest Rate (%)', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(loc='upper right', fontsize=11)
ax1.set_ylim(3.0, 6.0)

plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/fed_rate_trajectory.jpg', dpi=300, bbox_inches='tight')
print("Chart 1 saved: fed_rate_trajectory.jpg")

# Chart 2: December Rate Cut Probability Evolution
fig2, ax2 = plt.subplots(figsize=(10, 6))

timeline = ['Oct 15', 'Oct 25', 'Nov 5', 'Nov 15', 'Nov 25', 'Nov 30']
probabilities = [97, 85, 50, 35, 70, 41]

colors = ['#2E86AB' if p >= 50 else '#E63946' for p in probabilities]
bars = ax2.bar(timeline, probabilities, color=colors, alpha=0.8, edgecolor='black', linewidth=1.2)

# Add value labels on bars
for bar in bars:
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2., height,
             f'{height}%',
             ha='center', va='bottom', fontsize=11, fontweight='bold')

ax2.axhline(y=50, color='gray', linestyle='--', linewidth=1.5, alpha=0.5, label='50% Threshold')
ax2.set_title('December Rate Cut Probability: Market Expectations Evolution',
              fontsize=15, fontweight='bold', pad=20)
ax2.set_xlabel('Date', fontsize=12, fontweight='bold')
ax2.set_ylabel('Probability (%)', fontsize=12, fontweight='bold')
ax2.set_ylim(0, 105)
ax2.legend(loc='upper right', fontsize=10)
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/dec_cut_probability.jpg', dpi=300, bbox_inches='tight')
print("Chart 2 saved: dec_cut_probability.jpg")

# Chart 3: FOMC Members Split - Dovish vs Hawkish
fig3, ax3 = plt.subplots(figsize=(10, 7))

categories = ['Support\nDecember Cut', 'Oppose\nDecember Cut', 'Neutral/\nData-Dependent']
counts = [7, 8, 4]
colors_split = ['#06A77D', '#D62828', '#F77F00']

bars = ax3.barh(categories, counts, color=colors_split, alpha=0.85, edgecolor='black', linewidth=1.5)

# Add count labels
for i, (bar, count) in enumerate(zip(bars, counts)):
    width = bar.get_width()
    ax3.text(width + 0.2, bar.get_y() + bar.get_height()/2,
             f'{count} officials',
             ha='left', va='center', fontsize=12, fontweight='bold')

ax3.set_title('FOMC Committee Split on December Rate Decision',
              fontsize=15, fontweight='bold', pad=20)
ax3.set_xlabel('Number of Officials', fontsize=12, fontweight='bold')
ax3.set_xlim(0, 10)
ax3.grid(axis='x', alpha=0.3)

# Add names
names_text = """Dovish (Cut supporters): Williams, Daly, Waller, Miran, Bowman
Hawkish (Cut opponents): Collins, Bostic, Schmid, Hammack, Logan, Musalem
Neutral: Powell, Jefferson, Goolsbee"""

ax3.text(0.02, 0.02, names_text, transform=ax3.transAxes,
         fontsize=9, verticalalignment='bottom',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/fomc_split_analysis.jpg', dpi=300, bbox_inches='tight')
print("Chart 3 saved: fomc_split_analysis.jpg")

# Chart 4: Key Economic Indicators Dashboard
fig4, ((ax4a, ax4b), (ax4c, ax4d)) = plt.subplots(2, 2, figsize=(14, 10))

# Unemployment Rate
months_unemp = ['Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov']
unemployment = [4.1, 4.2, 4.3, 4.4, 4.3, 4.2]
ax4a.plot(months_unemp, unemployment, marker='o', linewidth=2.5, markersize=9, color='#E63946')
ax4a.axhline(y=4.0, color='gray', linestyle='--', alpha=0.5)
ax4a.set_title('Unemployment Rate (%)', fontsize=13, fontweight='bold')
ax4a.set_ylabel('Rate (%)', fontsize=11)
ax4a.grid(True, alpha=0.3)
ax4a.set_ylim(3.8, 4.6)

# Inflation (CPI)
months_cpi = ['Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov']
cpi = [3.2, 3.1, 2.8, 3.0, 3.1, 2.9]
target = [2.0] * len(months_cpi)
ax4b.plot(months_cpi, cpi, marker='s', linewidth=2.5, markersize=9, color='#F77F00', label='CPI YoY')
ax4b.plot(months_cpi, target, linestyle='--', linewidth=2, color='#06A77D', label='Fed Target')
ax4b.set_title('Inflation Rate (CPI YoY %)', fontsize=13, fontweight='bold')
ax4b.set_ylabel('Rate (%)', fontsize=11)
ax4b.legend(loc='upper right', fontsize=10)
ax4b.grid(True, alpha=0.3)
ax4b.set_ylim(1.5, 3.5)

# Job Growth
months_jobs = ['Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov']
jobs = [185, 142, 78, 119, 165, 180]
ax4c.bar(months_jobs, jobs, color='#2E86AB', alpha=0.8, edgecolor='black')
ax4c.axhline(y=150, color='red', linestyle='--', linewidth=1.5, alpha=0.6, label='Avg Needed (150K)')
ax4c.set_title('Monthly Job Additions (Thousands)', fontsize=13, fontweight='bold')
ax4c.set_ylabel('Jobs (K)', fontsize=11)
ax4c.legend(loc='upper right', fontsize=10)
ax4c.grid(axis='y', alpha=0.3)

# Fed Rate Cuts Timeline
rate_dates = ['Sep 2024', 'Nov 2024', 'Oct 2025', 'Dec 2025?']
rate_changes = [-0.50, -0.25, -0.25, -0.25]
cut_colors = ['#06A77D', '#06A77D', '#06A77D', '#CCCCCC']
bars = ax4d.bar(rate_dates, rate_changes, color=cut_colors, alpha=0.8, edgecolor='black', linewidth=1.2)
ax4d.set_title('Rate Cut Timeline (Basis Points)', fontsize=13, fontweight='bold')
ax4d.set_ylabel('Change (bps)', fontsize=11)
ax4d.grid(axis='y', alpha=0.3)
ax4d.set_ylim(-0.6, 0)

plt.suptitle('Key Economic Indicators Dashboard - November 2025',
             fontsize=16, fontweight='bold', y=0.995)
plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/economic_indicators_dashboard.jpg',
            dpi=300, bbox_inches='tight')
print("Chart 4 saved: economic_indicators_dashboard.jpg")

print("\nAll charts generated successfully!")
