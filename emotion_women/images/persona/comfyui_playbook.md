# ComfyUI 同人设图池玩法（备用）

这份说明只作为备用路线保留。当前主路线是通义万相主体库锁脸，见：

```text
emotion_women/images/persona/wanxiang_playbook.md
```

如果先不想折腾本地节点，不需要继续读本文件。

本文件只服务一个目标：当通义万相不够用时，用 ComfyUI 给情感女性公众号做“同一个女人”的长期封面图池。

## 你要理解的核心

ComfyUI 不是一个普通修图软件，它是一个“节点流程编辑器”。

可以把它理解成：

```text
输入图/提示词
  -> 生成场景
  -> 统一人脸
  -> 修脸
  -> 放大/必要时裁切
  -> 保存图片
```

每个步骤都是一个节点，节点之间用线连起来。

## 对你最有用的两种玩法

### 玩法 1：先生成图，再统一脸

最适合当前机器和公众号生产。

```text
场景提示词 -> 生成一张咖啡馆/夜路/办公室图
母图脸 -> ReActor/FaceFusion -> 把场景图里的脸统一成母图脸
```

优点：

- 同脸更稳。
- 不需要一开始就上很重的 PhotoMaker。
- 适合 RTX 3060 Ti 8GB。

缺点：

- 偶尔有换脸痕迹，需要人工筛。

### 玩法 2：用 InstantID / PuLID / PhotoMaker 直接生成同脸图

```text
母图/参考图 + 场景提示词 -> 直接生成同脸场景图
```

优点：

- 更像“原生照片”，不是后期换脸。

缺点：

- 显存更吃紧。
- 节点安装和模型配置更麻烦。
- 当前先不推荐作为第一步。

## 第一次启动怎么玩

### 1. 下载并解压

推荐目录：

```text
D:\workSpace\frontEnd\自媒体\ComfyUI_windows_portable
```

官方 Portable 版自带 `python_embeded`，所以不需要系统 Python。

启动：

```text
run_nvidia_gpu.bat
```

打开：

```text
http://127.0.0.1:8188
```

不要关启动出来的黑窗口，关了 ComfyUI 就停了。

## 第一张测试图

先不要做人设，先确认能生图。

最小节点逻辑：

```text
Load Checkpoint
  -> CLIP Text Encode Positive
  -> CLIP Text Encode Negative
  -> Empty Latent Image
  -> KSampler
  -> VAE Decode
  -> Save Image
```

参数建议：

```text
checkpoint: SD1.5 写实模型
width: 768
height: 512
steps: 20
cfg: 6.5
sampler: dpmpp_2m
scheduler: karras
batch_size: 1
```

正向提示词：

```text
photorealistic lifestyle photo of an adult East Asian woman sitting in a cozy cafe, natural skin texture, warm window light, emotional editorial photography
```

反向提示词：

```text
low quality, blurry, plastic skin, doll face, watermark, text, extra fingers, bad hands, explicit, lingerie, nude
```

如果这一步能出图，说明基础环境通了。

## 做同一人设的推荐流程

### 阶段 1：准备 source face

使用：

```text
emotion_women/images/persona/master/persona_master_natural_900x600.jpg
```

这张图的作用是 source face，不一定直接做封面。

### 阶段 2：生成场景底图

先生成 5 张底图：

```text
persona_cafe_base.jpg
persona_night_street_base.jpg
persona_home_base.jpg
persona_office_base.jpg
persona_car_window_base.jpg
```

底图只要求：

- 氛围好
- 构图好
- 穿搭符合要求
- 脸可以暂时不像

### 阶段 3：ReActor 统一脸

安装 ReActor 后，核心节点：

```text
Load Image(source face)
Load Image(target scene)
ReActorFaceSwap
Save Image
```

对应关系：

```text
source_image = persona_master_natural_900x600.jpg
input_image = persona_cafe_base.jpg
output = persona_cafe_fixed_900x600.jpg
```

先只修咖啡馆这一张。确认自然后，再批量。

## 你这个账号的图池标准

最终入池图建议是横图：

```text
最低 900x600，推荐 1536x1024 / 1280x853 / 1200x800 / 900x600
```

路径：

```text
emotion_women/images/persona/scenes/persona_cafe_900x600.jpg
emotion_women/images/persona/scenes/persona_night_street_900x600.jpg
emotion_women/images/persona/scenes/persona_home_900x600.jpg
emotion_women/images/persona/scenes/persona_office_900x600.jpg
emotion_women/images/persona/scenes/persona_car_window_900x600.jpg
```

## 显存设置建议

RTX 3060 Ti 8GB：

- 先用 SD1.5。
- 不要 batch，多张图一张一张跑。
- 先用 768x512，满意后再放大或裁切。
- SDXL 可以试，但容易慢或爆显存。
- InstantID/PhotoMaker 放到第二阶段。

## 常见坑

### 出图不像同一个人

不要继续调 prompt。用 ReActor/FaceFusion 统一脸。

### 脸像但假

降低脸修复强度，或者不要开太强的 face restore。

### 爆显存

降低分辨率，batch_size 改 1，换 SD1.5。

### 图太像写真

提示词加：

```text
candid lifestyle photography, natural expression, not a studio glamour portrait
```

反向加：

```text
glamour studio, over-posed, heavy retouching, influencer selfie
```

## 入池前最后检查

一张图只有同时满足这些条件才入池：

- 像同一个人
- 眼神自然
- 肤色和脖子融合自然
- 不像换脸
- 不低俗
- 适合公众号封面
- 横图，至少 900x600

