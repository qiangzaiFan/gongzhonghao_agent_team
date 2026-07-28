# 本地高画质配图流水线

## 目标

美食文章默认使用本地原创 AI 示意图，不抓取内容平台图片。主链路是：

```text
文章图片位 -> ComfyUI -> 3 张候选 -> 自动质检 -> 4x 放大 -> 1536x1024 JPG -> 回填 Markdown
```

默认主模型为 `FLUX.2 Klein 4B FP8`，显存不足或执行失败时降级到
`SDXL Lightning 4-step`，不再使用 SD1.5。

## 首次安装

ComfyUI Portable 安装在工作区外，避免把运行时、模型和缓存提交到当前项目：

```powershell
cd D:\workSpace\自媒体\gongzhonghao_agent_team\food_home_cooking
powershell -ExecutionPolicy Bypass -File .\bootstrap_comfyui.ps1 -InstallRuntime -InstallModels
```

模型会自动放到：

```text
D:\workSpace\自媒体\ComfyUI_windows_portable\
  models\diffusion_models\flux-2-klein-4b-fp8.safetensors
  models\text_encoders\qwen_3_4b.safetensors
  models\vae\flux2-vae.safetensors
  models\upscale_models\4x-UltraSharp.pth
  models\checkpoints\sdxl_lightning_4step.safetensors
```

启动本地服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap_comfyui.ps1 -Start
```

服务地址固定为 `http://127.0.0.1:8188`。启动器会传入 `--lowvram`，
适配 RTX 3060 Ti 8GB；生成时始终单张执行。

## 生成文章图片

```powershell
python .\generate_article_images.py .\articles\20260727_一个人12元早餐.md
```

默认行为：

- 每个 Markdown 图片位生成 3 个候选。
- 先用 `flux2_klein`；单个候选报错时自动尝试 `sdxl_lightning`。
- 输出候选联系表到 `reviews/image_candidates/`。
- 通过亮度、对比度、清晰度、饱和度、图片文字检测和可选 OpenCLIP 语义评分选图。
- 只在全部图位通过后才回写文章路径，最终图片保存到 `images/ai/`。

常用参数：

```powershell
# 只预览提示词和目标文件，不联系 ComfyUI
python .\generate_article_images.py .\articles\20260727_一个人12元早餐.md --dry-run

# 重新生成已存在图片
python .\generate_article_images.py .\articles\20260727_一个人12元早餐.md --overwrite

# 关闭 SDXL 降级，专门排查 FLUX.2 Klein
python .\generate_article_images.py .\articles\20260727_一个人12元早餐.md --no-fallback
```

## 图片规则

- AI 图一律使用 `../images/ai/<filename>.jpg` 相对路径。
- 最终输出固定 `1536x1024`，普通家庭厨房、手机随手拍感。
- 单个图位只描述一个明确场景；步骤图只出现一个锅或一个碗中的单一状态。
- 禁止人物、手部、品牌、文字、水印、平台 UI、复杂拼盘和广告摆盘。
- `images/ai/SOURCES.md` 记录本地模型配置、生成时间、候选编号和提示词摘要哈希。

## 质检

```powershell
python .\quality_gate.py .\articles\20260727_一个人12元早餐.md --image-mode ai
```

AI 模式会把以下情况作为失败：图片不存在、远程图片、路径逃出本目录、
损坏格式、分辨率低于 `1536x1024`、连续图片或误导性的“实拍”图片描述。
