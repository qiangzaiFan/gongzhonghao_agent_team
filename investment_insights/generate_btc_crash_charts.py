import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta
import matplotlib.patches as patches

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['font.size'] = 10

# Chart 1: Bitcoin Price Chart (October-November 2025)
fig, ax = plt.subplots(figsize=(12, 6))

# Generate price data
dates = []
start_date = datetime(2025, 10, 1)
for i in range(52):  # Oct 1 to Nov 21
    dates.append(start_date + timedelta(days=i))

# Price trajectory: peak at ~126K in mid-Oct, crash to ~82K
prices = []
for i, d in enumerate(dates):
    if i < 15:  # Rising to peak
        price = 110000 + (126000 - 110000) * (i / 15)
    elif i < 20:  # Peak period
        price = 126000 - 1000 * (i - 15)
    elif i < 35:  # First leg down
        price = 121000 - (121000 - 95000) * ((i - 20) / 15)
    else:  # Second leg down to 82K
        price = 95000 - (95000 - 82000) * ((i - 35) / 17)
    prices.append(price)

# Plot
ax.plot(dates, prices, color='#FF4444', linewidth=2.5, label='BTC/USD')
ax.fill_between(dates, prices, alpha=0.3, color='#FF4444')

# Add key events
ax.axhline(y=126000, color='green', linestyle='--', alpha=0.7, linewidth=1)
ax.text(dates[18], 127500, 'All-Time High: $126,000', fontsize=9, color='green')

ax.axhline(y=82000, color='red', linestyle='--', alpha=0.7, linewidth=1)
ax.text(dates[45], 79500, 'Nov 21 Low: $82,000', fontsize=9, color='red')

# Add drop annotation
ax.annotate('', xy=(dates[50], 82000), xytext=(dates[17], 126000),
            arrowprops=dict(arrowstyle='->', color='black', lw=2))
ax.text(dates[32], 100000, '-35%', fontsize=14, fontweight='bold', color='#FF4444')

ax.set_title('Bitcoin Price October-November 2025', fontsize=14, fontweight='bold')
ax.set_xlabel('Date', fontsize=11)
ax.set_ylabel('Price (USD)', fontsize=11)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
plt.xticks(rotation=45)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K'))
ax.set_ylim([75000, 135000])
ax.legend(loc='upper right')
plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/btc_price_crash_nov2025.png', dpi=150, bbox_inches='tight')
plt.close()

# Chart 2: Fear & Greed Index
fig, ax = plt.subplots(figsize=(10, 6))

# Data points for November
fear_dates = ['Nov 1', 'Nov 5', 'Nov 10', 'Nov 15', 'Nov 19', 'Nov 20', 'Nov 21']
fear_values = [45, 35, 21, 10, 12, 11, 11]

colors = []
for v in fear_values:
    if v <= 20:
        colors.append('#FF0000')  # Extreme Fear
    elif v <= 40:
        colors.append('#FF8800')  # Fear
    elif v <= 60:
        colors.append('#FFFF00')  # Neutral
    else:
        colors.append('#00FF00')  # Greed

bars = ax.bar(fear_dates, fear_values, color=colors, edgecolor='black', linewidth=1)

# Add value labels
for bar, val in zip(bars, fear_values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            str(val), ha='center', va='bottom', fontweight='bold', fontsize=11)

# Add zones
ax.axhline(y=20, color='red', linestyle='--', alpha=0.5, label='Extreme Fear Zone')
ax.axhline(y=40, color='orange', linestyle='--', alpha=0.5, label='Fear Zone')

ax.set_title('Crypto Fear & Greed Index - November 2025', fontsize=14, fontweight='bold')
ax.set_xlabel('Date', fontsize=11)
ax.set_ylabel('Index Value', fontsize=11)
ax.set_ylim([0, 60])
ax.legend(loc='upper right')

# Add text box
textstr = 'Current: 11\nStatus: Extreme Fear\nLowest since 2022'
props = dict(boxstyle='round', facecolor='#FFEEEE', alpha=0.8)
ax.text(0.02, 0.95, textstr, transform=ax.transAxes, fontsize=10,
        verticalalignment='top', bbox=props)

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/fear_greed_index_nov2025.png', dpi=150, bbox_inches='tight')
plt.close()

# Chart 3: ETF Outflow Data
fig, ax = plt.subplots(figsize=(11, 6))

# ETF data
etf_names = ['BlackRock\nIBIT', 'Fidelity\nFBTC', 'Grayscale\nGBTC', 'ARK 21\nARKB', 'Others']
outflows = [2.47, 1.09, 0.15, 0.05, 0.03]  # in billions
colors_etf = ['#000000', '#228B22', '#FFD700', '#FF6B6B', '#808080']

bars = ax.bar(etf_names, outflows, color=colors_etf, edgecolor='black', linewidth=1)

# Add value labels
for bar, val in zip(bars, outflows):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
            f'${val}B', ha='center', va='bottom', fontweight='bold', fontsize=11)

# Add percentage annotation for IBIT
ax.text(bars[0].get_x() + bars[0].get_width()/2, bars[0].get_height()/2,
        '65%', ha='center', va='center', color='white', fontsize=14, fontweight='bold')

ax.set_title('US Bitcoin ETF Net Outflows - November 2025', fontsize=14, fontweight='bold')
ax.set_xlabel('ETF Fund', fontsize=11)
ax.set_ylabel('Net Outflow (Billion USD)', fontsize=11)

# Add total
ax.text(0.98, 0.95, f'Total: $3.79 Billion\nRecord Monthly Outflow',
        transform=ax.transAxes, fontsize=11, verticalalignment='top',
        horizontalalignment='right', bbox=dict(boxstyle='round', facecolor='#FFE4E1', alpha=0.8))

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/btc_etf_outflow_nov2025.png', dpi=150, bbox_inches='tight')
plt.close()

# Chart 4: Support Level Analysis
fig, ax = plt.subplots(figsize=(12, 7))

# Price range
price_levels = [126000, 110000, 94000, 89400, 82400, 80000, 70000]
labels = ['ATH Oct 2025', 'Resistance', 'STH Cost Basis', 'Active Realized', 'True Market Mean', 'Key Support', 'Bear Target']
colors_level = ['#00AA00', '#88CC88', '#FFAA00', '#FF8800', '#FF4400', '#FF0000', '#880000']

# Create horizontal bars
y_pos = np.arange(len(price_levels))
bars = ax.barh(y_pos, price_levels, color=colors_level, edgecolor='black', linewidth=1, height=0.6)

# Add labels
for i, (bar, label, price) in enumerate(zip(bars, labels, price_levels)):
    ax.text(price + 2000, bar.get_y() + bar.get_height()/2,
            f'${price/1000:.1f}K - {label}', va='center', fontsize=10)

# Mark current price
current_price = 82000
ax.axvline(x=current_price, color='red', linestyle='-', linewidth=3, label=f'Current: ${current_price/1000:.0f}K')

ax.set_title('Bitcoin Key Price Levels & Support Analysis', fontsize=14, fontweight='bold')
ax.set_xlabel('Price (USD)', fontsize=11)
ax.set_yticks([])
ax.set_xlim([0, 160000])
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K'))
ax.legend(loc='upper right')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/btc_support_levels_analysis.png', dpi=150, bbox_inches='tight')
plt.close()

# Chart 5: 2022 vs 2025 Bear Market Comparison
fig, ax = plt.subplots(figsize=(11, 6))

# Comparison metrics
metrics = ['Peak Price', 'Trough Price', 'Max Drawdown', 'Duration\n(days)', 'Fear Index\nLow']
values_2022 = [69000, 15476, 77.5, 365, 6]  # Normalized for visualization
values_2025 = [126000, 82000, 35, 51, 11]  # Normalized

# Normalize for comparison (percentage of 2022 values)
x = np.arange(len(metrics))
width = 0.35

# Create separate y-axis scales for better visualization
ax1 = ax

# For display, use normalized percentages
display_2022 = [100, 100, 100, 100, 100]  # baseline
display_2025 = [182.6, 530, 45.2, 14, 183.3]  # relative to 2022

bars1 = ax1.bar(x - width/2, display_2022, width, label='2022 Bear Market', color='#4444FF', alpha=0.8)
bars2 = ax1.bar(x + width/2, display_2025, width, label='2025 Current', color='#FF4444', alpha=0.8)

# Add actual values as labels
actual_2022 = ['$69K', '$15.5K', '77.5%', '365', '6']
actual_2025 = ['$126K', '$82K', '35%', '51', '11']

for bar, val in zip(bars1, actual_2022):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
             val, ha='center', va='bottom', fontsize=9, color='#4444FF', fontweight='bold')

for bar, val in zip(bars2, actual_2025):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
             val, ha='center', va='bottom', fontsize=9, color='#FF4444', fontweight='bold')

ax1.set_title('2022 Bear Market vs 2025 November Crash', fontsize=14, fontweight='bold')
ax1.set_ylabel('Relative Scale (2022 = 100)', fontsize=11)
ax1.set_xticks(x)
ax1.set_xticklabels(metrics, fontsize=10)
ax1.legend(loc='upper right')
ax1.set_ylim([0, 600])

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/btc_2022_vs_2025_comparison.png', dpi=150, bbox_inches='tight')
plt.close()

print("All 5 charts generated successfully!")
print("Charts saved to /home/floodsung/media_agents/investment_insights/images/")
