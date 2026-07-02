#!/usr/bin/env python3
import urllib.request
import os
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
IMAGES_DIR = SCRIPT_DIR / 'images'

# Create images directory if it doesn't exist
os.makedirs(IMAGES_DIR, exist_ok=True)

images = [
    ('https://techcrunch.com/wp-content/uploads/2024/05/openAI-spiral-rose.jpg?w=1024',
     IMAGES_DIR / 'openai-logo-spiral.jpg'),
    ('https://wp.technologyreview.com/wp-content/uploads/2025/01/In-action.png',
     IMAGES_DIR / 'operator-interface-demo.png'),
    ('https://wp.technologyreview.com/wp-content/uploads/2025/01/no-hands.jpg',
     IMAGES_DIR / 'ai-agent-computer-use.jpg')
]

for url, filename in images:
    print(f'Downloading {filename}...')
    urllib.request.urlretrieve(url, filename)
    print(f'✓ Downloaded {filename}')

print('\nAll images downloaded successfully!')
