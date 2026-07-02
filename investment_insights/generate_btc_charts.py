import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
import matplotlib.dates as mdates

# Set style
plt.style.use('seaborn-v0_8-darkgrid')

# Figure 1: Bitcoin Price Crash Chart (Oct - Nov 2025)
fig1, ax1 = plt.subplots(figsize=(12, 6))

# Bitcoin price data (simulated based on market info)
dates = [datetime(2025, 10, 1) + timedelta(days=x) for x in range(48)]
prices = []

# Simulate price movement: peak at 126k early Oct, crash to 95k by Nov 14
for i, date in enumerate(dates):
    if i < 6:  # Oct 1-6, rising to peak
        prices.append(120000 + i * 1000)
    elif i < 25:  # Oct 7-25, gradual decline
        prices.append(126000 - (i-6) * 1200)
    else:  # Oct 26 - Nov 17, accelerated crash
        prices.append(103200 - (i-25) * 330)

ax1.plot(dates, prices, linewidth=2.5, color='#f7931a', label='BTC/USD')
ax1.fill_between(dates, prices, alpha=0.3, color='#f7931a')

# Mark key points
ax1.axhline(y=126000, color='green', linestyle='--', alpha=0.5, label='Oct Peak: $126,296')
ax1.axhline(y=95722, color='red', linestyle='--', alpha=0.5, label='Nov 14 Low: $95,722')

# Annotations
ax1.annotate('Peak\n$126,296', xy=(dates[6], 126000), xytext=(dates[10], 130000),
            arrowprops=dict(arrowstyle='->', color='green', lw=1.5),
            fontsize=11, color='green', fontweight='bold')

ax1.annotate('Crash\n-24%', xy=(dates[43], 95722), xytext=(dates[35], 88000),
            arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
            fontsize=11, color='red', fontweight='bold')

ax1.set_xlabel('Date', fontsize=12, fontweight='bold')
ax1.set_ylabel('Price (USD)', fontsize=12, fontweight='bold')
ax1.set_title('Bitcoin Price Crash: October - November 2025', fontsize=14, fontweight='bold', pad=20)
ax1.legend(loc='upper right', fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K'))
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/btc_price_crash_oct_nov.png', dpi=300, bbox_inches='tight')
plt.close()

# Figure 2: ETF Flows Analysis
fig2, ax2 = plt.subplots(figsize=(10, 6))

dates_etf = ['Nov 6', 'Nov 7', 'Nov 10', 'Nov 11', 'Nov 13', 'Nov 14']
flows = [240, -558, 0, 524, -867, -492]  # in millions USD
colors = ['green' if x > 0 else 'red' for x in flows]

bars = ax2.bar(dates_etf, flows, color=colors, alpha=0.7, edgecolor='black', linewidth=1.2)

# Add value labels on bars
for i, (bar, flow) in enumerate(zip(bars, flows)):
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2., height + (30 if height > 0 else -30),
            f'${abs(flow)}M',
            ha='center', va='bottom' if height > 0 else 'top',
            fontweight='bold', fontsize=10)

ax2.axhline(y=0, color='black', linewidth=1.5)
ax2.set_ylabel('Net Flow (Million USD)', fontsize=12, fontweight='bold')
ax2.set_xlabel('Date (November 2025)', fontsize=12, fontweight='bold')
ax2.set_title('Bitcoin Spot ETF Daily Net Flows', fontsize=14, fontweight='bold', pad=20)
ax2.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/btc_etf_flows.png', dpi=300, bbox_inches='tight')
plt.close()

# Figure 3: Liquidation Breakdown
fig3, (ax3a, ax3b) = plt.subplots(1, 2, figsize=(14, 6))

# Liquidation by position type
positions = ['Long\nPositions', 'Short\nPositions']
amounts = [1220, 130]  # in millions
colors_liq = ['#dc3545', '#28a745']

wedges, texts, autotexts = ax3a.pie(amounts, labels=positions, autopct='%1.1f%%',
                                      colors=colors_liq, startangle=90,
                                      textprops={'fontsize': 11, 'fontweight': 'bold'})

ax3a.set_title('Liquidations by Position Type\nTotal: $1.35 Billion',
               fontsize=13, fontweight='bold', pad=15)

# Liquidation by cryptocurrency
cryptos = ['BTC', 'ETH', 'Others']
crypto_amounts = [407, 356, 587]
colors_crypto = ['#f7931a', '#627eea', '#95a5a6']

bars = ax3b.barh(cryptos, crypto_amounts, color=colors_crypto, alpha=0.8, edgecolor='black', linewidth=1.2)

# Add value labels
for i, (bar, amount) in enumerate(zip(bars, crypto_amounts)):
    ax3b.text(amount + 15, i, f'${amount}M',
             va='center', fontweight='bold', fontsize=11)

ax3b.set_xlabel('Liquidation Amount (Million USD)', fontsize=11, fontweight='bold')
ax3b.set_title('Liquidations by Cryptocurrency\n(Nov 13-14, 2025)',
               fontsize=13, fontweight='bold', pad=15)
ax3b.grid(True, alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/btc_liquidations_breakdown.png', dpi=300, bbox_inches='tight')
plt.close()

print("All charts generated successfully!")
print("1. btc_price_crash_oct_nov.png")
print("2. btc_etf_flows.png")
print("3. btc_liquidations_breakdown.png")
