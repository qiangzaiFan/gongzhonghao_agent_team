# 体制类公众号图片生成规范

所有封面图和正文插图均使用本地 ComfyUI 的 FLUX.2 Klein 工作流生成。图片必须适配微信公众号图文排版，画质精细，构图干净，体制内文风素雅庄重，不使用花哨网红风格。封面和正文插图全部使用户外风景或环境叙事图，风景地点不限制在国内，世界各地的自然风景、城市风景、乡村风景都可以使用。

执行顺序固定为：先生成纯文字文章并通过本地 AIGC 门槛，再生成图片；AIGC 未通过时禁止启动 ComfyUI 生图。图片写入文章后，再刷新一次最终 AIGC 报告。进入公众号草稿箱或发布前，最后排版统一使用 `wenyan-mcp` 优化。

## 正向 Prompt

```text
masterpiece, best quality, ultra detailed, 8k, ultra realistic, sharp focus, intricate details, soft natural lighting, depth of field, clean composition, mild tone, peaceful atmosphere, rich texture, cinematic rendering, no distortion, sober and dignified Chinese public-sector editorial photography style, globally sourced landscape photography suitable for reflective workplace essays, natural mountains, rivers, lakes, coastlines, forests, fields, roads, quiet towns, public parks, or distant architecture when suitable, elegant restrained color palette, clean layout for WeChat article reading, no flashy influencer style, no exaggerated visual effects
```

在固定底词后追加与文章内容对应的具体风景场景。可以使用世界各地的山川、湖泊、海岸、森林、田野、道路、小镇街景、公园、桥梁、远景建筑或村庄周边，只要情绪和文章主题相符即可。写明自然光、前中后景和留白，不生成可读文字、标语、Logo、公章、标牌或横幅。

## 反向 Prompt

```text
worst quality, low quality, blurry, fuzzy, noisy, deformed, disfigured, extra limbs, distorted face, ugly, cartoon, anime, painting, illustration, vibrant neon color, exaggerated makeup, messy background, watermark, text, signature, frame, oversaturated, brand name, official seal, readable document text, Chinese characters, poster typography, UI screenshot, identifiable person, celebrity, uniform insignia, luxury office, internet celebrity style, over-beautified filter, logo, slogan, advertisement, collage, visual clutter
```

## 参数设置

- 模型：ComfyUI FLUX.2 Klein
- 工作流：本地 ComfyUI，地址默认 `http://127.0.0.1:8188`
- 公众号封面：`900x380`
- 文章内插图：`1200x800`
- 采样步数：至少 `30`
- CFG：`1.8` 到 `2.5`，默认 `2.0`
- 输出：PNG；生成后按目标比例居中裁切，保证适配图文排版

## 全图风景规则

封面和正文插图都必须是横向户外风景或环境叙事图。可使用全球任意地区的自然风景、城市边缘风景、乡村道路、田野、树木、海岸、湖泊、山谷、公园、桥梁、小镇街景和远景建筑，并根据文章主题变化天气、时段、道路关系和空间层次。禁止室内办公桌、电脑、手机、文件特写、静物摆拍和人物主体。封面保留较大标题留白，正文图使用与封面不同的风景构图。

## 最终排版

本地 Markdown 成稿写入图片后，发布或进入公众号草稿箱前统一使用 `wenyan-mcp` 做图文排版优化，默认主题固定为清爽政务蓝 / 商务简约风的 `lapis`：白底、深蓝标题、浅灰分割、少装饰、重留白，文章作者固定为“田间里的烟火”。使用 `daily_tizhi.py --publish` 或 `publish_existing_article.py` 时会走该流程；手动处理体制内文章时也不得绕过这一步。
