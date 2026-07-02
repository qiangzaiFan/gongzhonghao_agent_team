import matplotlib.pyplot as plt
import numpy as np

# Set style
plt.style.use('seaborn-v0_8-whitegrid')

# Chart 1: December Rate Cut Probability Jump
fig, ax = plt.subplots(figsize=(10, 6))

dates = ['Nov 19', 'Nov 20\n(AM)', 'Nov 20\n(PM)', 'Nov 21\n(Pre-Williams)', 'Nov 21\n(Post-Williams)']
probabilities = [50.1, 43.8, 35, 35, 73]

colors = ['#3498db', '#3498db', '#e74c3c', '#e74c3c', '#27ae60']
bars = ax.bar(dates, probabilities, color=colors, edgecolor='white', linewidth=2)

# Add value labels on bars
for bar, prob in zip(bars, probabilities):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 1,
            f'{prob}%', ha='center', va='bottom', fontsize=12, fontweight='bold')

ax.set_ylabel('Probability (%)', fontsize=12)
ax.set_title('December 2025 Fed Rate Cut Probability\nCME FedWatch Tool', fontsize=14, fontweight='bold')
ax.set_ylim(0, 85)

# Add annotation for Williams speech impact
ax.annotate('Williams Speech\nImpact', xy=(4, 73), xytext=(3.2, 60),
            arrowprops=dict(arrowstyle='->', color='#27ae60', lw=2),
            fontsize=10, color='#27ae60', fontweight='bold')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/dec_rate_cut_probability_jump.png', dpi=150, bbox_inches='tight')
plt.close()

# Chart 2: Market Reaction - Dow Jones Rally
fig, ax = plt.subplots(figsize=(10, 6))

times = ['Nov 20\nClose', 'Nov 21\nOpen', 'Nov 21\n10:00', 'Nov 21\n12:00', 'Nov 21\n14:00', 'Nov 21\nClose']
dow_levels = [45752, 45850, 46100, 46450, 46500, 46245]

ax.plot(times, dow_levels, marker='o', linewidth=2.5, markersize=8, color='#2ecc71')
ax.fill_between(range(len(times)), dow_levels, 45700, alpha=0.3, color='#2ecc71')

# Mark the Williams speech effect
ax.axvline(x=2, color='#3498db', linestyle='--', linewidth=2, alpha=0.7)
ax.text(2.1, 46300, 'Williams\nSpeech', fontsize=9, color='#3498db', fontweight='bold')

ax.set_ylabel('Dow Jones Industrial Average', fontsize=12)
ax.set_title('Dow Jones Rally on November 21, 2025\n+493 Points (+1.08%)', fontsize=14, fontweight='bold')
ax.set_ylim(45700, 46600)

# Add gain annotation
ax.annotate('+493 pts', xy=(5, 46245), xytext=(4.3, 45900),
            arrowprops=dict(arrowstyle='->', color='#27ae60', lw=2),
            fontsize=11, color='#27ae60', fontweight='bold')

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/dow_rally_nov21.png', dpi=150, bbox_inches='tight')
plt.close()

# Chart 3: Treasury Yields Drop
fig, ax = plt.subplots(figsize=(10, 6))

yields_data = {
    'Before Williams': [4.10, 3.56, 4.72],
    'After Williams': [4.06, 3.51, 4.71]
}
treasury_types = ['10-Year', '2-Year', '30-Year']
x = np.arange(len(treasury_types))
width = 0.35

bars1 = ax.bar(x - width/2, yields_data['Before Williams'], width, label='Before Williams Speech', color='#e74c3c', alpha=0.8)
bars2 = ax.bar(x + width/2, yields_data['After Williams'], width, label='After Williams Speech', color='#27ae60', alpha=0.8)

# Add value labels
for bar in bars1:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 0.02,
            f'{height}%', ha='center', va='bottom', fontsize=10)

for bar in bars2:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 0.02,
            f'{height}%', ha='center', va='bottom', fontsize=10)

ax.set_ylabel('Yield (%)', fontsize=12)
ax.set_title('Treasury Yields Fall After Williams Speech\nNovember 21, 2025', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(treasury_types)
ax.legend(loc='upper right')
ax.set_ylim(3.3, 5.0)

plt.tight_layout()
plt.savefig('/home/floodsung/media_agents/investment_insights/images/treasury_yields_nov21.png', dpi=150, bbox_inches='tight')
plt.close()

print("Charts created successfully!")
