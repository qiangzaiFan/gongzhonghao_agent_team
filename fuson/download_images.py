#!/usr/bin/env python3
import urllib.request
import os

# Create images directory if it doesn't exist
os.makedirs('/home/floodsung/media_agents/fuson/images', exist_ok=True)

images = [
    ('https://techcrunch.com/wp-content/uploads/2024/05/openAI-spiral-rose.jpg?w=1024',
     '/home/floodsung/media_agents/fuson/images/openai-logo-spiral.jpg'),
    ('https://wp.technologyreview.com/wp-content/uploads/2025/01/In-action.png',
     '/home/floodsung/media_agents/fuson/images/operator-interface-demo.png'),
    ('https://wp.technologyreview.com/wp-content/uploads/2025/01/no-hands.jpg',
     '/home/floodsung/media_agents/fuson/images/ai-agent-computer-use.jpg')
]

for url, filename in images:
    print(f'Downloading {filename}...')
    urllib.request.urlretrieve(url, filename)
    print(f'✓ Downloaded {filename}')

print('\nAll images downloaded successfully!')
