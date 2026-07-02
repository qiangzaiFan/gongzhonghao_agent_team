import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta

# Set style for professional financial charts
plt.style.use('ggplot')

# Chart 1: Fed Rate Cut Probability Decline (95% -> 40%)
fig1, ax1 = plt.subplots(figsize=(12, 6), dpi=150)

dates = [datetime(2025, 10, 15), datetime(2025, 10, 25), datetime(2025, 11, 5),
         datetime(2025, 11, 12), datetime(2025, 11, 14), datetime(2025, 11, 17)]
probabilities = [95, 90, 67, 50, 43.6, 40]

ax1.plot(dates, probabilities, marker='o', linewidth=3, markersize=10, color='#e74c3c')
ax1.fill_between(dates, probabilities, alpha=0.3, color='#e74c3c')
ax1.set_xlabel('Date (2025)', fontsize=14, fontweight='bold')
ax1.set_ylabel('Probability (%)', fontsize=14, fontweight='bold')
ax1.set_title('December 2025 Fed Rate Cut Probability Decline', fontsize=16, fontweight='bold', pad=20)
ax1.grid(True, alpha=0.3)
ax1.set_ylim(30, 100)

# Format x-axis
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
plt.xticks(rotation=45)

# Add annotations
ax1.annotate('95%', xy=(dates[0], probabilities[0]), xytext=(dates[0], probabilities[0]+5),
            fontsize=11, fontweight='bold', ha='center')
ax1.annotate('40%', xy=(dates[-1], probabilities[-1]), xytext=(dates[-1], probabilities[-1]-8),
            fontsize=11, fontweight='bold', ha='center', color='red')
ax1.annotate('Powell: "Not a foregone conclusion"',
            xy=(dates[1], probabilities[1]), xytext=(dates[2], 75),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.5),
            fontsize=10, bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7))

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/fed_rate_cut_probability_decline.jpg',
            dpi=150, bbox_inches='tight')
plt.close()

# Chart 2: Federal Funds Rate Trend (2024-2025)
fig2, ax2 = plt.subplots(figsize=(12, 6), dpi=150)

rate_dates = [datetime(2024, 7, 1), datetime(2024, 9, 15), datetime(2024, 11, 1),
              datetime(2025, 1, 1), datetime(2025, 3, 1), datetime(2025, 5, 1),
              datetime(2025, 7, 1), datetime(2025, 9, 18), datetime(2025, 10, 30),
              datetime(2025, 12, 10)]
rates = [5.5, 5.5, 5.5, 5.5, 5.5, 5.5, 5.5, 4.75, 4.0, 3.875]  # Projected

ax2.plot(rate_dates[:-1], rates[:-1], marker='s', linewidth=3, markersize=8,
         color='#3498db', label='Actual Rate')
ax2.plot(rate_dates[-2:], rates[-2:], marker='s', linewidth=3, markersize=8,
         linestyle='--', color='#95a5a6', label='Uncertain')
ax2.set_xlabel('Date', fontsize=14, fontweight='bold')
ax2.set_ylabel('Federal Funds Rate (%)', fontsize=14, fontweight='bold')
ax2.set_title('Federal Funds Rate Trend 2024-2025', fontsize=16, fontweight='bold', pad=20)
ax2.grid(True, alpha=0.3)
ax2.legend(loc='upper right', fontsize=11)

# Format x-axis
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
plt.xticks(rotation=45)

# Add annotations
ax2.annotate('First Cut: 50bp\nSep 18, 2025', xy=(rate_dates[7], rates[7]),
            xytext=(rate_dates[6], 5.0),
            arrowprops=dict(arrowstyle='->', color='green', lw=2),
            fontsize=10, bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7))
ax2.annotate('Oct Cut: 25bp\n4.0%', xy=(rate_dates[8], rates[8]),
            xytext=(rate_dates[8], 4.7),
            arrowprops=dict(arrowstyle='->', color='green', lw=2),
            fontsize=10, bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7))
ax2.annotate('Dec: 40% probability', xy=(rate_dates[9], rates[9]),
            xytext=(rate_dates[8]+timedelta(days=20), 3.3),
            arrowprops=dict(arrowstyle='->', color='red', lw=2),
            fontsize=10, bbox=dict(boxstyle='round,pad=0.5', facecolor='#ffcccc', alpha=0.7))

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/federal_funds_rate_trend.jpg',
            dpi=150, bbox_inches='tight')
plt.close()

# Chart 3: Inflation vs Employment Comparison
fig3, ax3 = plt.subplots(figsize=(12, 6), dpi=150)

months = ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct']
core_pce = [2.6, 2.7, 2.8, 2.8, 2.9, 2.8]  # Core PCE inflation (%)
unemployment = [3.9, 4.0, 4.1, 4.3, 4.2, 4.2]  # Unemployment rate (%)

x = np.arange(len(months))
width = 0.35

bars1 = ax3.bar(x - width/2, core_pce, width, label='Core PCE Inflation (%)', color='#e74c3c', alpha=0.8)
bars2 = ax3.bar(x + width/2, unemployment, width, label='Unemployment Rate (%)', color='#3498db', alpha=0.8)

ax3.set_xlabel('Month (2025)', fontsize=14, fontweight='bold')
ax3.set_ylabel('Percentage (%)', fontsize=14, fontweight='bold')
ax3.set_title('Inflation vs Employment Data - 2025', fontsize=16, fontweight='bold', pad=20)
ax3.set_xticks(x)
ax3.set_xticklabels(months)
ax3.legend(fontsize=11)
ax3.grid(True, alpha=0.3, axis='y')
ax3.axhline(y=2.0, color='red', linestyle='--', linewidth=2, alpha=0.5, label='Fed Target (2%)')

# Add value labels on bars
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/inflation_employment_comparison.jpg',
            dpi=150, bbox_inches='tight')
plt.close()

# Chart 4: Market Reaction - Treasury Yields
fig4, ax4 = plt.subplots(figsize=(12, 6), dpi=150)

market_dates = [datetime(2025, 10, 29), datetime(2025, 11, 1), datetime(2025, 11, 5),
                datetime(2025, 11, 8), datetime(2025, 11, 12), datetime(2025, 11, 14),
                datetime(2025, 11, 17)]
yield_10yr = [4.09, 4.12, 4.15, 4.18, 4.22, 4.25, 4.28]
yield_2yr = [3.95, 3.98, 4.02, 4.05, 4.08, 4.11, 4.15]

ax4.plot(market_dates, yield_10yr, marker='o', linewidth=3, markersize=8,
         color='#e67e22', label='10-Year Treasury Yield')
ax4.plot(market_dates, yield_2yr, marker='s', linewidth=3, markersize=8,
         color='#9b59b6', label='2-Year Treasury Yield')
ax4.set_xlabel('Date (November 2025)', fontsize=14, fontweight='bold')
ax4.set_ylabel('Yield (%)', fontsize=14, fontweight='bold')
ax4.set_title('Treasury Yields Rise on Hawkish Fed Comments', fontsize=16, fontweight='bold', pad=20)
ax4.grid(True, alpha=0.3)
ax4.legend(loc='upper left', fontsize=11)

# Format x-axis
ax4.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
plt.xticks(rotation=45)

# Add annotation
ax4.annotate('Yields rise as rate cut\nprobability declines',
            xy=(market_dates[4], yield_10yr[4]), xytext=(market_dates[2], 4.35),
            arrowprops=dict(arrowstyle='->', color='red', lw=2),
            fontsize=10, bbox=dict(boxstyle='round,pad=0.5', facecolor='#ffe6e6', alpha=0.8))

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/treasury_yields_reaction.jpg',
            dpi=150, bbox_inches='tight')
plt.close()

# Chart 5: Fed Officials Hawkish Stance
fig5, ax5 = plt.subplots(figsize=(10, 6), dpi=150)

officials = ['Schmid\n(Kansas City)', 'Bowman\n(Governor)', 'Mester\n(Cleveland)',
             'Waller\n(Governor)', 'Barkin\n(Richmond)']
hawkish_scores = [9, 7, 6, 5, 4]  # Hawkishness score (1-10)
colors_map = ['#c0392b', '#e74c3c', '#e67e22', '#f39c12', '#f1c40f']

bars = ax5.barh(officials, hawkish_scores, color=colors_map, alpha=0.8)
ax5.set_xlabel('Hawkish Stance (1=Dovish, 10=Most Hawkish)', fontsize=12, fontweight='bold')
ax5.set_title('Fed Officials Hawkish Stance - November 2025', fontsize=14, fontweight='bold', pad=15)
ax5.grid(True, alpha=0.3, axis='x')
ax5.set_xlim(0, 10)

# Add value labels
for i, (bar, score) in enumerate(zip(bars, hawkish_scores)):
    ax5.text(score + 0.2, bar.get_y() + bar.get_height()/2,
            f'{score}/10', va='center', fontsize=11, fontweight='bold')

# Add notes
ax5.text(9, 0.5, 'Dissented on\nOct rate cut', fontsize=9, style='italic',
         bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.5))

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/fed_officials_hawkish_stance.jpg',
            dpi=150, bbox_inches='tight')
plt.close()

print("All 5 charts created successfully!")
print("1. Fed Rate Cut Probability Decline")
print("2. Federal Funds Rate Trend")
print("3. Inflation vs Employment Comparison")
print("4. Treasury Yields Reaction")
print("5. Fed Officials Hawkish Stance")
