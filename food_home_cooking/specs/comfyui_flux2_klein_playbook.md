# ComfyUI / FLUX.2 Klein 本地生图复刻手册

这份文档记录当前项目里已经跑通的本地图片生成方案：Windows Portable ComfyUI + `--lowvram` + FLUX.2 Klein 4B FP8 + Qwen 文本编码器 + FLUX2 VAE + 4x-UltraSharp 放大。适合你自己手动复刻、调 prompt、生成候选图，再挑选最终图。

## 目录结构

当前项目在：

```text
D:\workSpace\自媒体\gongzhonghao_agent_team
```

ComfyUI Portable 默认安装在项目外层：

```text
D:\workSpace\自媒体\ComfyUI_windows_portable
```

项目内相关文件：

```text
food_home_cooking\
  bootstrap_comfyui.ps1                  # 安装、下载模型、启动 ComfyUI
  comfy_model_profiles.json              # 模型配置
  generate_article_images.py             # 项目封装好的 ComfyUI API 客户端
  workflows\food_flux2_klein_api.json    # FLUX.2 Klein API 工作流
  workflows\food_sdxl_lightning_api.json # SDXL Lightning 兜底工作流
  images\ai\                             # 最终图片
  images\ai\candidates\                  # 候选图，已在 .gitignore 中忽略
  reviews\image_candidates\              # 候选联系表和 manifest，已忽略
```

## 1. 首次安装

进入美食项目目录：

```powershell
cd D:\workSpace\自媒体\gongzhonghao_agent_team\food_home_cooking
```

安装 ComfyUI Portable 和所需模型：

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap_comfyui.ps1 -InstallRuntime -InstallModels
```

脚本会下载并放置这些文件：

```text
D:\workSpace\自媒体\ComfyUI_windows_portable\ComfyUI\models\
  diffusion_models\flux-2-klein-4b-fp8.safetensors
  text_encoders\qwen_3_4b.safetensors
  vae\flux2-vae.safetensors
  upscale_models\4x-UltraSharp.pth
  checkpoints\sdxl_lightning_4step.safetensors
```

如果你已经安装过，再运行这条命令会跳过已有文件。下载中断时可以重新执行。

## 2. 启动 ComfyUI

先确认项目 Python 依赖可用。`generate_article_images.py` 至少需要 Pillow：

```powershell
cd D:\workSpace\自媒体\gongzhonghao_agent_team
python -m pip install -r .\requirements-imagegen.txt
```

如果你固定使用项目虚拟环境，也可以：

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-imagegen.txt
```

再回到美食目录：

```powershell
cd .\food_home_cooking
```

启动低显存模式：

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap_comfyui.ps1 -Start
```

重启服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap_comfyui.ps1 -Restart
```

脚本会生成并运行：

```text
D:\workSpace\自媒体\ComfyUI_windows_portable\start_food_comfyui.cmd
```

里面实际启动命令是：

```cmd
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --lowvram
```

浏览器打开：

```text
http://127.0.0.1:8188
```

注意：本项目主要走 ComfyUI HTTP API，不依赖前端手动拖节点。前端能打开说明服务基本正常。

## 3. 验证服务和模型

确认端口是否通：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 8188
```

确认启动参数里有 `--lowvram`：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 20 |
  ConvertTo-Json -Depth 8
```

你应该能看到类似：

```json
"argv": [
  "ComfyUI\\main.py",
  "--windows-standalone-build",
  "--lowvram"
]
```

确认模型列表识别正常：

```powershell
$data = Invoke-RestMethod -Uri 'http://127.0.0.1:8188/object_info' -TimeoutSec 60

function Get-ComfyOptions($entry) {
  if ($entry -is [System.Array] -and $entry.Count -ge 2 -and $entry[0] -eq 'COMBO') {
    $optsProp = $entry[1].PSObject.Properties['options']
    if ($optsProp) { return @($optsProp.Value) }
  }
  if ($entry -is [System.Array] -and $entry.Count -gt 0) { return @($entry[0]) }
  return @($entry)
}

$checks = @(
  @{Class='UNETLoader'; Field='unet_name'; Wanted='flux-2-klein-4b-fp8.safetensors'},
  @{Class='CLIPLoader'; Field='clip_name'; Wanted='qwen_3_4b.safetensors'},
  @{Class='VAELoader'; Field='vae_name'; Wanted='flux2-vae.safetensors'},
  @{Class='UpscaleModelLoader'; Field='model_name'; Wanted='4x-UltraSharp.pth'},
  @{Class='CheckpointLoaderSimple'; Field='ckpt_name'; Wanted='sdxl_lightning_4step.safetensors'}
)

foreach ($check in $checks) {
  $node = $data.PSObject.Properties[$check.Class].Value
  $entry = $node.input.required.PSObject.Properties[$check.Field].Value
  $options = Get-ComfyOptions $entry
  $found = $options -contains $check.Wanted
  "{0}.{1}: found={2} wanted={3}" -f $check.Class, $check.Field, $found, $check.Wanted
}
```

`UpscaleModelLoader.model_name` 在新版 ComfyUI 里可能返回 `COMBO`，真正的模型名在 `options` 里，这是正常的。

## 4. 模型参数

当前 `flux2_klein` 配置在 `comfy_model_profiles.json`：

```json
{
  "UNET": "flux-2-klein-4b-fp8.safetensors",
  "CLIP": "qwen_3_4b.safetensors",
  "VAE": "flux2-vae.safetensors",
  "UPSCALER": "4x-UltraSharp.pth",
  "STEPS": 4,
  "CFG": 1.0
}
```

工作流关键节点：

```text
UNETLoader              -> flux-2-klein-4b-fp8.safetensors
CLIPLoader              -> qwen_3_4b.safetensors, type=flux2
VAELoader               -> flux2-vae.safetensors
Flux2Scheduler          -> steps=4, width=960, height=640
EmptyFlux2LatentImage   -> 960x640, batch_size=1
KSamplerSelect          -> euler
ImageUpscaleWithModel   -> 4x-UltraSharp.pth
ImageScale              -> 1536x1024, crop=center
SaveImage               -> filename_prefix
```

低显存建议：

- `batch_size` 保持 `1`。
- 一次只跑 1 张候选，或者用脚本循环排队。
- 宽高先用 `960x640`，不要直接上 1536。
- 需要最终发布图时再放大到 `1536x1024`。

## 5. 路线 A：用文章流水线生成

这是最省心的方式，适合给 Markdown 文章批量补图。

预览 prompt，不联系 ComfyUI：

```powershell
python .\generate_article_images.py .\articles\20260727_一个人12元早餐.md --dry-run
```

只跑第 1 个图位：

```powershell
python .\generate_article_images.py .\articles\20260727_一个人12元早餐.md --limit-slots 1 --candidate-count 1 --semantic-check off
```

覆盖已有最终图：

```powershell
python .\generate_article_images.py .\articles\20260727_一个人12元早餐.md --limit-slots 1 --candidate-count 3 --overwrite --semantic-check off
```

关闭 SDXL 兜底，只排查 FLUX.2 Klein：

```powershell
python .\generate_article_images.py .\articles\20260727_一个人12元早餐.md --limit-slots 1 --no-fallback
```

输出位置：

```text
images\ai\<最终文件名>.jpg
images\ai\candidates\<文章名>\slot-xx-candidate-y.png
reviews\image_candidates\<文章名>.jpg
reviews\image_candidates\<文章名>.json
images\ai\SOURCES.md
```

## 6. 路线 B：自己写 prompt 生成任意单张图

如果你不想先写文章，只想手动调 prompt，用这个方式。进入目录：

```powershell
cd D:\workSpace\自媒体\gongzhonghao_agent_team\food_home_cooking
```

把下面整段复制到 PowerShell 运行。你主要改三个地方：

- `$Prompt`
- `$NegativeExtra`
- `$OutName`

```powershell
$Prompt = @'
Photorealistic casual mobile phone food photo in an ordinary Chinese home kitchen, natural window light.
One-person breakfast on a simple kitchen counter.
Main visual center: one white ceramic bowl of clear noodle soup with thin noodles, leafy green vegetables, and one fried egg on top.
Left/front: half a pan-seared corn cob, golden yellow kernels clearly separated, only a few tiny light brown sear marks, not burned.
Right/front: a normal shallow ceramic side plate holding a generous serving of dressed smashed cucumber chunks, with light dressing sheen and a few natural seasoning specks, not plain raw cucumber cubes.
Back/right: a plain glass filled with opaque milky-white soy milk, not tea or coffee.
Everyday home breakfast, natural imperfect details, appetizing but not restaurant plating, 3:2 landscape.
No people, no hands, no text, no logo, no watermark, no rice, no meat rice bowl.
'@

$NegativeExtra = @'
burnt corn, black corn, heavily charred corn, mushy corn, plain raw cucumber cubes, dry cucumber, tiny cucumber garnish, rigid symmetrical garnish, brown drink, tea, coffee, cocoa, milk tea, transparent water, rice, meat rice bowl, restaurant table, western breakfast, bread
'@

$OutName = 'manual-breakfast-01.jpg'

$code = @"
from __future__ import annotations

from pathlib import Path
import random

import generate_article_images as p

prompt = r'''$Prompt'''
p.NEGATIVE_PROMPT = p.NEGATIVE_PROMPT + ', ' + r'''$NegativeExtra'''
profile = 'flux2_klein'
seed = random.SystemRandom().randint(1, 2**63 - 1)

profiles = p.load_profiles()
client = p.ComfyClient(p.DEFAULT_ENDPOINT, timeout=60)
stats = client.preflight()
print('ComfyUI connected:', stats.get('devices', [{}])[0].get('name', 'unknown'))
print('Seed:', seed)

candidate_root = p.CANDIDATE_DIR / 'manual'
candidate_root.mkdir(parents=True, exist_ok=True)
filename_prefix = 'food_home_cooking/manual/' + Path('$OutName').stem
workflow = p.render_workflow(
    profiles,
    profile,
    prompt=prompt,
    seed=seed,
    filename_prefix=filename_prefix,
)

prompt_id = client.queue(workflow)
images = client.wait_for_images(prompt_id, max_wait_seconds=900, poll_seconds=1.5)
candidate_path = candidate_root / (Path('$OutName').stem + '-candidate.png')
client.download_image(images[-1], candidate_path)

scorer = p.OptionalSemanticScorer('off')
score, metrics, warnings, _, _ = p.score_candidate(
    candidate_path,
    prompt=prompt,
    semantic_scorer=scorer,
)

final_path = p.AI_IMAGE_DIR / '$OutName'
p.postprocess_to_final(candidate_path, final_path)

print('Candidate:', candidate_path)
print('Final:', final_path)
print('Score:', score)
print('Metrics:', metrics)
print('Warnings:', warnings)
"@

$code | python -
```

生成后看：

```text
food_home_cooking\images\ai\manual-breakfast-01.jpg
food_home_cooking\images\ai\candidates\manual\manual-breakfast-01-candidate.png
```

## 7. 路线 C：自己批量跑候选再挑

思路是同一个 prompt 连续跑多个 seed，再生成联系表。

```powershell
$Prompt = @'
Photorealistic casual mobile phone food photo in an ordinary Chinese home kitchen.
One bowl of tomato egg noodles on a simple kitchen counter, natural window light, ordinary ceramic bowl, clear food texture, home cooking, no people, no text.
'@

$OutSlug = 'manual-tomato-noodles'
$Count = 4

$code = @"
from __future__ import annotations

from pathlib import Path
import random

import generate_article_images as p

prompt = r'''$Prompt'''
profile = 'flux2_klein'
profiles = p.load_profiles()
client = p.ComfyClient(p.DEFAULT_ENDPOINT, timeout=60)
client.preflight()

candidate_root = p.CANDIDATE_DIR / '$OutSlug'
candidate_root.mkdir(parents=True, exist_ok=True)
scorer = p.OptionalSemanticScorer('off')
candidates = []

for index in range(1, $Count + 1):
    seed = random.SystemRandom().randint(1, 2**63 - 1)
    filename_prefix = f'food_home_cooking/$OutSlug/candidate-{index}'
    workflow = p.render_workflow(
        profiles,
        profile,
        prompt=prompt,
        seed=seed,
        filename_prefix=filename_prefix,
    )
    print(f'Queue candidate {index}, seed={seed}')
    prompt_id = client.queue(workflow)
    images = client.wait_for_images(prompt_id, max_wait_seconds=900, poll_seconds=1.5)
    candidate_path = candidate_root / f'candidate-{index}.png'
    client.download_image(images[-1], candidate_path)
    score, metrics, warnings, semantic_score, ocr_text = p.score_candidate(
        candidate_path,
        prompt=prompt,
        semantic_scorer=scorer,
    )
    candidates.append(
        p.Candidate(
            slot_index=1,
            candidate_index=index,
            profile=profile,
            seed=seed,
            prompt=prompt,
            path=str(candidate_path),
            score=score,
            metrics=metrics,
            warnings=warnings,
            semantic_score=semantic_score,
            ocr_text=ocr_text,
        )
    )
    print(index, score, candidate_path)

contact_sheet = p.REVIEW_DIR / '$OutSlug-contact.jpg'
p.make_contact_sheet(candidates, contact_sheet)
print('Contact sheet:', contact_sheet)
"@

$code | python -
```

打开联系表：

```text
food_home_cooking\reviews\image_candidates\manual-tomato-noodles-contact.jpg
```

挑中某张后，把候选后处理成最终 JPG：

```powershell
$code = @"
from pathlib import Path
import generate_article_images as p

source = p.CANDIDATE_DIR / 'manual-tomato-noodles' / 'candidate-2.png'
target = p.AI_IMAGE_DIR / 'manual-tomato-noodles-final.jpg'
p.postprocess_to_final(source, target)
print(target)
"@

$code | python -
```

## 8. Prompt 写法

FLUX.2 Klein 对具体物体约束比较吃 prompt。建议用英文写细节，尤其是颜色、容器、份量、火候、不要替换成什么。

推荐结构：

```text
Scene: 普通家庭厨房 / 餐桌 / 台面
Main subject: 主要视觉中心
Supporting objects: 配菜、饮品、小物件
Local details: 颜色、份量、容器、火候、调味、纹理
Style: 手机随手拍、自然光、家常、不广告
Avoid: 人、手、文字、水印、品牌、错误替代物
```

好用句式：

```text
ordinary Chinese home kitchen, natural window light
casual mobile phone food photo
simple ceramic bowl, normal shallow side plate
clear food texture, natural imperfect details
not restaurant plating, not menu photography
```

局部物体约束示例：

```text
soy milk: opaque milky-white soy milk, not tea, not coffee, not milk tea
smashed cucumber: generous serving on a shallow side plate, light dressing sheen, a few natural seasoning specks, not plain raw cucumber cubes
pan-seared corn: golden yellow kernels clearly separated, only a few tiny light brown sear marks, not burned, no black patches
```

负面 prompt 不要只写泛泛的 `bad quality`。要写你真正怕它画错的东西：

```text
brown drink, tea, coffee, milk tea, burnt corn, black corn, plain raw cucumber cubes, tiny garnish, rice, meat rice bowl, text, watermark, people, hands
```

## 9. 人工选图标准

自动分数只看亮度、清晰度、尺寸、饱和度和 OCR，不懂“豆浆颜色对不对”这种语义细节。最终仍要人工看。

发布前逐张检查：

- 主体是否和文章一致。
- 饮品颜色是否对，比如豆浆不能像茶或咖啡。
- 配菜份量是否正常，不能只是边角点缀。
- 局部细节是否自然，有纹理、火候和调味线索。
- 玉米、煎蛋、青菜、面条等有没有糊、塑料感或畸形。
- 是否有文字、水印、品牌、人物、手部。
- 是否过度餐厅广告化。

## 10. 常见问题

### 连接不上 `127.0.0.1:8188`

检查是否启动：

```powershell
Get-Process python -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Path,StartTime
Get-NetTCPConnection -LocalPort 8188 -ErrorAction SilentlyContinue
```

重新启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap_comfyui.ps1 -Restart
```

### 模型列表看不到文件

先确认文件是否在模型目录：

```powershell
Get-ChildItem D:\workSpace\自媒体\ComfyUI_windows_portable\ComfyUI\models -Recurse |
  Where-Object { $_.Name -match 'flux|qwen|vae|UltraSharp|sdxl' } |
  Select-Object FullName,Length
```

然后重启 ComfyUI。

### 放大模型查询只看到 `COMBO`

这是新版 ComfyUI 的字段格式。要看：

```text
UpscaleModelLoader.input.required.model_name[1].options
```

不是只看第一个元素。

### 显存爆了或生成失败

先保持这些设置：

- `--lowvram`
- `batch_size=1`
- `960x640` 起图
- `steps=4`
- `cfg=1.0`

关闭其它占 GPU 的程序，重启 ComfyUI 后再跑。如果 FLUX.2 Klein 仍失败，可以用项目脚本让它自动降级到 `sdxl_lightning`。

### 画面对但细节不对

不要只加“高质量”。直接写局部约束：

```text
The cucumber side dish has a light dressing sheen and a few seasoning specks, not plain raw cucumber cubes.
The corn kernels are golden and clear, with only a few light brown sear marks, not burned or black.
The soy milk is opaque milky white, not tea or coffee.
```

每轮只改 1-2 个问题，再生成 3-4 张候选挑图。

## 11. 最小复刻流程

从零到一张图，最短路径：

```powershell
cd D:\workSpace\自媒体\gongzhonghao_agent_team\food_home_cooking
powershell -ExecutionPolicy Bypass -File .\bootstrap_comfyui.ps1 -Start
Test-NetConnection -ComputerName 127.0.0.1 -Port 8188
python .\generate_article_images.py .\articles\20260727_一个人12元早餐.md --dry-run --limit-slots 1
python .\generate_article_images.py .\articles\20260727_一个人12元早餐.md --limit-slots 1 --candidate-count 3 --overwrite --semantic-check off
```

如果你只想随便生成一张不绑定文章的图，用第 6 节的 PowerShell 片段。
