# 通义万相同人设图池玩法

> v3 提示：当前唯一母图为 `images/persona/master/persona_master_glam_v3.png`，人设是 28-32 岁、精致日常妆容、轻熟妩媚的虚构成年女性。下文出现的“22 岁/青春靓丽”属历史提示词，不再手工复制；`sync_wanxiang_persona_pool.py` 会自动升级为 v3 表述。

这份说明是当前主路线：先不折腾本地 ComfyUI 节点，用通义万相「主体库」做同一虚拟女生的长期封面图池。

目标只有一个：公众号封面长期像同一个人，同时保持 iPhone 原相机朋友圈随拍质感。

## 总流程

```text
生成基准正脸图
  -> 上传通义万相主体库
  -> 调用同一主体生成生活场景
  -> 下载原图
  -> 保留高分辨率横图，必要时再裁切
  -> 人工筛选
  -> 保存到 images/persona/scenes/
  -> 运行同步脚本加入 image_pool.txt
```

## 1. 生成基准形象

先用文生图生成 1 张干净的正面基准照。

要求：

- 亚洲成年女性，约 26-30 岁。
- 正面或轻微 15 度侧脸，五官无遮挡。
- 齐肩黑发或深棕发，发型简单稳定。
- 柔光棚拍或干净自然光。
- 真实皮肤纹理，不要过度磨皮。
- 不要墨镜、帽子、口罩、夸张首饰。
- 服装可以是白T、浅色衬衫、牛仔外套、运动短袖、卫衣、清爽裙装或轻薄针织，但必须是日常外穿，不是内衣。
- 整体是青春靓丽、清爽明亮、元气自然的成年女性生活照，不做明显性暗示动作。
- 不要透明衣物、内衣特写、露点、裸露敏感部位或低俗挑逗姿势。

建议保存：

```text
emotion_women/images/persona/master/persona_master_wanxiang_source.png
emotion_women/images/persona/master/persona_master_wanxiang_preview.jpg
```

基准图提示词：

```text
正面高清人像，22 岁亚洲成年女性，齐肩黑发，自然淡妆，五官无遮挡，白色T恤搭配浅色牛仔外套，阳光露齿笑，青春活力，清爽明亮，元气自然，白天自然光，干净背景，真实皮肤纹理，iPhone 原相机质感，清晰照片，不像影楼写真
```

反向约束：

```text
低俗，露点，裸露敏感部位，透明衣物，内衣特写，色情姿势，挑逗动作，浓妆，塑料皮肤，过度磨皮，夸张滤镜，畸形五官，遮挡脸，墨镜，帽子，口罩，影楼写真，AI感，水印，文字
```

## 2. 上传主体库

在通义万相里：

1. 打开「主体库」。
2. 上传 `persona_master_wanxiang_source.png`。
3. 命名虚拟角色，例如：

```text
情感号_青春靓丽_01
```

注意：

- 不使用真实人物姓名。
- 不把真人照片、明星照片、网红照片当主体。
- 后续所有封面场景都调用这个主体。

## 3. 生成场景图

### 自动生成优先

如果已经有 DashScope / 阿里云百炼 API Key，推荐直接跑脚本生成、下载、校验并入池：

```powershell
python emotion_women\sync_wanxiang_persona_pool.py --generate-wanxiang
```

脚本默认会：

- 使用 `images/persona/master/persona_master_natural_source.png` 作为同一人设参考图。
- 调用 `wan2.6-image` 生成场景图。
- 把输出保存为 `images/persona/scenes/*.jpg`。
- 校验尺寸、横图比例和文件可读性。
- 把合格图片自动写入 `image_pool.txt` 对应的 `COVER_*` 段。

第一次建议先试 1 张：

```powershell
python emotion_women\sync_wanxiang_persona_pool.py --generate-wanxiang --limit 1
```

本地凭证不要提交到 Git。可以在 `emotion_women/.env` 写：

```text
DASHSCOPE_API_KEY=你的DashScope API Key
```

如果使用阿里云百炼新版专属域名，也可以补充：

```text
DASHSCOPE_WORKSPACE_ID=你的WorkspaceId
DASHSCOPE_REGION=cn-beijing
```

或者直接指定完整 API 前缀：

```text
DASHSCOPE_BASE_URL=https://你的WorkspaceId.cn-beijing.maas.aliyuncs.com/api/v1
```

### 手动生成备用

优先按下面清单补图：

```text
emotion_women/images/persona/wanxiang_scene_backlog.md
```

也可以先导出一份更方便复制的生成任务表：

```powershell
python emotion_women\sync_wanxiang_persona_pool.py --export-prompts
```

导出的文件：

```text
emotion_women/images/persona/wanxiang_generation_tasks.md
```

统一提示词骨架：

```text
调用主体库：情感号_青春靓丽_01，iPhone14 原相机实拍，22 岁亚洲成年女性，齐肩黑发，[白T/浅色衬衫/牛仔外套/运动短袖/卫衣/清爽裙装]，[场景动作]，[环境光线]，青春活力，阳光明亮，元气笑容，朋友帮忙随手拍，真实皮肤纹理，背景轻微虚化，高清照片，不像影楼写真
```

### 咖啡店

```text
调用主体库：情感号_青春靓丽_01，iPhone14 原相机实拍，22 岁亚洲成年女性，齐肩黑发，白色T恤搭配浅色牛仔外套，在明亮咖啡店窗边吃巴斯克蛋糕，手边有冰美式，自然光虚化背景，露齿笑，青春活力，阳光明亮，朋友帮忙随手拍，真实皮肤纹理，高清照片，不像影楼写真
```

建议文件名：

```text
emotion_women/images/persona/scenes/persona_wanxiang_cafe_cake_1536x1024.jpg
```

### 徒步山路

```text
调用主体库：情感号_青春靓丽_01，iPhone14 原相机实拍，22 岁亚洲成年女性，户外徒步，宽松浅色运动短袖搭配运动长裤，白天山路，头发被风轻轻吹起，挥手大笑，元气满满，朋友帮忙随手拍，真实皮肤纹理，高清照片
```

建议文件名：

```text
emotion_women/images/persona/scenes/persona_wanxiang_hiking_sunset_1536x1024.jpg
```

### 下班通勤

```text
调用主体库：情感号_青春靓丽_01，iPhone14 原相机实拍，22 岁亚洲成年女性，白色短袖衬衫搭配浅色半裙，早晨写字楼门口，手里拿着帆布包和咖啡，阳光明亮，表情轻松有活力，初入职场清爽感，朋友帮忙随手拍，真实皮肤纹理，高清照片
```

建议文件名：

```text
emotion_women/images/persona/scenes/persona_wanxiang_commute_night_1536x1024.jpg
```

### 居家窗边

```text
调用主体库：情感号_青春靓丽_01，iPhone14 原相机实拍，22 岁亚洲成年女性，居家窗边给绿植浇水，白色T恤搭配浅色针织开衫，桌上有书和水果，清晨阳光，笑容自然，青春活力，清爽生活感，真实皮肤纹理，高清照片
```

建议文件名：

```text
emotion_women/images/persona/scenes/persona_wanxiang_home_window_1536x1024.jpg
```

### 办公室

```text
调用主体库：情感号_青春靓丽_01，iPhone14 原相机实拍，22 岁亚洲成年女性，明亮共享办公区，白衬衫外搭浅色针织背心，整理文件和笔记本电脑，窗外阳光，表情专注又有活力，初入职场清爽感，真实皮肤纹理，高清照片
```

建议文件名：

```text
emotion_women/images/persona/scenes/persona_wanxiang_office_window_1536x1024.jpg
```

## 4. 入池尺寸

导出图片后统一处理：

- 不强制裁剪为 `900x600`。
- 保留高分辨率横图，最低 `900x600`。
- 推荐尺寸：`1536x1024`、`1280x853`、`1200x800`、`900x600`。
- 宽高比建议 `1.25-1.95`，最稳是 `3:2` 附近。
- 如果人物脸部太靠边、公众号封面可能裁脸，再手动裁成安全横图。
- 保存为 JPG。
- 优先放入 `images/persona/scenes/`。
- 文件名必须和任务表里的目标文件名一致。
- 运行同步脚本自动加入 `image_pool.txt` 的对应 `COVER_*` 段。

同步命令：

```powershell
python emotion_women\sync_wanxiang_persona_pool.py --sync
```

如果要同时重新导出任务表并同步已下载图片：

```powershell
python emotion_women\sync_wanxiang_persona_pool.py
```

## 5. 入池检查

一张图只有同时满足这些条件才入池：

- 像同一个人。
- 眼神自然，不僵硬。
- 脸、脖子、手的肤色自然统一。
- 不像影楼写真，不像网红自拍。
- 可以清爽露肩、自然肩颈线条或轻微露肤，但必须是成年女性、日常外穿和自然姿态。
- 不露点，不露敏感部位，不透明衣物，不内衣特写，不低俗挑逗。
- 没有文字、水印、明显 AI 瑕疵。
- 本地尺寸至少 `900x600`，横图比例适合公众号封面。

## 6. 当前决策

当前阶段：

- 主路线：通义万相主体库。
- 新文章封面必须优先使用 `images/persona/scenes/` 里的人设图。
- 备用路线：ComfyUI/ReActor。
- 不安装本地节点，不折腾显存和模型依赖。
