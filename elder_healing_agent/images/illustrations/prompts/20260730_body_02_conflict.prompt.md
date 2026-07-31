Original illustration quote-card brief for 晴川黄鹤.

Article title: 人到后半生，别再把身体借给别人
Image slot: conflict
Scene summary: 亮起的手机旁放着没吃完的饭，情绪有点堵
Final card quote text:
别把命
用在不值得的人和事上

Target effect:
Square Chinese WeChat watercolor comic quote-card, similar category to a hand-painted collectible article illustration card, but fully original to 晴川黄鹤.

Canvas and layout:
- 1:1 square card.
- Full warm off-white rough rice-paper texture background.
- Upper/middle 55%-65%: detailed hand-drawn watercolor comic scene.
- Bottom 30%-40%: large dark gray / ink-black Chinese brush-calligraphy quote area.
- Lower right: small original red seal for 晴川黄鹤 only. Do not use Yue Man or any copied mark.

Illustration scene:
a glowing phone beside an unfinished bowl of rice and a small medicine packet, a quiet feeling of being interrupted and tired.

Visual style:
Hand-drawn ink outline, visible watercolor wash, paper grain, warm muted colors, gentle humor, mature healing feeling, not childish, not flat vector, not PowerPoint icon style.

Negative prompt:
blurry, low resolution, ugly, deformed, messy lines, oversimplified details, rough sketch, 3d, photorealistic, text, watermark, extra limbs, harsh shadows, high contrast, gloomy tone

Typography instruction:
The final Chinese card text must read exactly:
"别把命 / 用在不值得的人和事上"
If the image model cannot render Chinese perfectly, generate the illustration without text but reserve the bottom quote area for post-production text overlay.

Recommended stable production:
1. Generate a no-text watercolor base illustration with the same paper texture and bottom empty quote area.
2. Save that base art as:
   images/illustrations/sources/20260730_body_02_conflict_base.png
3. Run:
   python scripts/compose_quote_cards.py
4. The compositor will overlay exact Chinese brush text and the 晴川黄鹤 red seal into the final PNG.

Avoid:
No Yue Man mark, no Yue Man signature, no copied composition from reference images, no copied red stamp, no watermark, no garbled Chinese, no random extra characters, no frightening hospital scene, no exaggerated tears, no low-quality flat vector placeholder.
