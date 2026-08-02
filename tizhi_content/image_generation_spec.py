"""Shared image-generation rules for the tizhi_content track."""

from __future__ import annotations


MODEL_NAME = "ComfyUI FLUX.2 Klein"
ENDPOINT = "http://127.0.0.1:8188"

POSITIVE_BASE_PROMPT = (
    "masterpiece, best quality, ultra detailed, 8k, ultra realistic, sharp focus, "
    "intricate details, soft natural lighting, depth of field, clean composition, "
    "mild tone, peaceful atmosphere, rich texture, cinematic rendering, no distortion, "
    "sober and dignified Chinese public-sector editorial photography style, "
    "globally sourced landscape photography suitable for reflective workplace essays, "
    "natural mountains, rivers, lakes, coastlines, forests, fields, roads, quiet towns, "
    "public parks, or distant architecture when suitable, "
    "elegant restrained color palette, clean layout for WeChat article reading, "
    "no flashy influencer style, no exaggerated visual effects"
)

LANDSCAPE_SCENE_GUIDANCE = (
    "outdoor landscape scene from any region of the world, environmental storytelling through scenery only, "
    "mountains, rivers, lakes, coastlines, forests, plains, fields, quiet streets, public parks, "
    "small towns, bridges, roads, distant architecture, or village surroundings chosen to match the article topic, "
    "natural daylight, balanced horizon, clear foreground middle ground and background, calm negative space, "
    "no indoor scene, no office desk, "
    "no laptop, no smartphone, no document close-up, no object still life, no portrait, "
    "no people as the main subject, no signboard, no plaque, no banner, no letters or symbols"
)

COVER_SCENE_GUIDANCE = (
    "wide horizontal WeChat cover composition, generous negative space for headline layout"
)

ILLUSTRATION_SCENE_GUIDANCE = (
    "horizontal editorial landscape composition for an article body image, rich spatial depth, "
    "distinct scenery from the cover while matching the same article topic"
)

NEGATIVE_PROMPT = (
    "worst quality, low quality, blurry, fuzzy, noisy, deformed, disfigured, "
    "extra limbs, distorted face, ugly, cartoon, anime, painting, illustration, "
    "vibrant neon color, exaggerated makeup, messy background, watermark, text, "
    "signature, frame, oversaturated, brand name, official seal, readable document text, "
    "Chinese characters, poster typography, UI screenshot, identifiable person, celebrity, "
    "uniform insignia, luxury office, internet celebrity style, over-beautified filter, "
    "logo, slogan, advertisement, collage, visual clutter"
)

MIN_STEPS = 30
CFG_MIN = 1.8
CFG_MAX = 2.5
DEFAULT_STEPS = 30
DEFAULT_CFG = 2.0
COVER_SIZE = (900, 380)
ILLUSTRATION_SIZE = (1200, 800)
LAYOUT_TOOL = "wenyan-mcp"
PUBLISH_THEME = "lapis"
PUBLISH_AUTHOR = "田间里的烟火"
LAYOUT_RULE = (
    f"最终排版：进入公众号草稿箱或发布前，统一使用 {LAYOUT_TOOL} 的 {PUBLISH_THEME} 主题"
    f"优化为清爽政务蓝 / 商务简约风，作者固定为“{PUBLISH_AUTHOR}”"
)


def positive_prompt(scene_prompt: str) -> str:
    """Return the complete FLUX positive prompt for one scene."""
    return f"{POSITIVE_BASE_PROMPT}. {scene_prompt.strip()}"


def spec_text() -> str:
    """Return the three-part spec used by the local workflow."""
    return "\n".join(
        (
            f"模型：{MODEL_NAME}",
            "",
            "正向 Prompt:",
            POSITIVE_BASE_PROMPT,
            "",
            "全部图片风景约束（全球可选）:",
            LANDSCAPE_SCENE_GUIDANCE,
            "",
            "封面构图约束:",
            COVER_SCENE_GUIDANCE,
            "",
            "正文插图构图约束:",
            ILLUSTRATION_SCENE_GUIDANCE,
            "",
            "反向 Prompt:",
            NEGATIVE_PROMPT,
            "",
            "参数设置:",
            f"封面：{COVER_SIZE[0]}x{COVER_SIZE[1]}",
            f"正文插图：{ILLUSTRATION_SIZE[0]}x{ILLUSTRATION_SIZE[1]}",
            f"采样步数：{DEFAULT_STEPS}（最低 {MIN_STEPS}）",
            f"CFG：{DEFAULT_CFG}（范围 {CFG_MIN}-{CFG_MAX}）",
            "工作流：本地 ComfyUI，禁止切换为在线生图服务",
            "执行顺序：文章先通过 AIGC 检测，再生成全部风景图",
            f"排版主题：{LAYOUT_TOOL} / {PUBLISH_THEME}（蓝色系、清爽、商务简约，适合体制内长文阅读）",
            f"公众号作者：{PUBLISH_AUTHOR}",
            LAYOUT_RULE,
        )
    )
