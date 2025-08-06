#!/usr/bin/env python3

import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.dates import DateFormatter
import seaborn as sns

# load dataset
file = 'swedbank.csv'
df = pd.read_csv(file)

#df[df.columns[0]] = pd.to_datetime(df[df.columns[0]])
#print(df)

# Set Seaborn style
sns.set(style="whitegrid")

# Set up the figure
plt.figure(figsize=(12, 6))

# Plot each series
for col in df.columns[1:5]:
    plt.plot(df[df.columns[0]], df[col], label=col, linewidth=3)

# Format the x-axis if it's a date
#plt.gca().xaxis.set_major_formatter(DateFormatter('%Y-%m'))

# Labels and title
plt.title("Interest rate", fontsize=16, fontweight='bold')
plt.xlabel(df.columns[0], fontsize=12)
plt.ylabel("Percent (%)", fontsize=12)

# Show legend and grid
plt.legend(fontsize=10)
plt.grid(True, which='major', linestyle='--', linewidth=2.5)
plt.tight_layout()

# Rotate x-axis labels
plt.xticks(rotation=45)

# Save the plot
plt.savefig('images/lineplot.png', dpi=200, bbox_inches='tight')

# Display the plot
#plt.show()