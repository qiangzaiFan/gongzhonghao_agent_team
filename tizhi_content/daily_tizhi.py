#!/usr/bin/env python3
"""Generate tizhi_content articles and optionally publish them to WeChat drafts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ARTICLES_DIR = BASE_DIR / "articles"
COVER_DIR = BASE_DIR / "images" / "covers"
ILLUSTRATION_DIR = BASE_DIR / "images" / "illustrations"
FOOD_DIR = ROOT_DIR / "food_home_cooking"
if str(FOOD_DIR) not in sys.path:
    sys.path.insert(0, str(FOOD_DIR))

import generate_article_images as comfy_images  # noqa: E402
from image_generation_spec import (  # noqa: E402
    CFG_MAX,
    CFG_MIN,
    COVER_SCENE_GUIDANCE,
    COVER_SIZE,
    DEFAULT_CFG,
    DEFAULT_STEPS,
    ENDPOINT,
    ILLUSTRATION_SIZE,
    ILLUSTRATION_SCENE_GUIDANCE,
    LANDSCAPE_SCENE_GUIDANCE,
    MIN_STEPS,
    NEGATIVE_PROMPT,
    POSITIVE_BASE_PROMPT,
    PUBLISH_AUTHOR,
    PUBLISH_THEME,
    MODEL_NAME,
    positive_prompt,
    spec_text,
)


DEFAULT_COMFY_ENDPOINT = ENDPOINT
TIZHI_BASE_PROMPT = POSITIVE_BASE_PROMPT
TIZHI_NEGATIVE_PROMPT = NEGATIVE_PROMPT


@dataclass(frozen=True)
class ArticleSeed:
    title: str
    slug: str
    summary: str
    cover_prompt: str
    illustration_prompt: str
    body: str


SEEDS: tuple[ArticleSeed, ...] = (
    ArticleSeed(
        title="体制内，别把临时帮忙变成长期兜底",
        slug="temporary-help-long-term-cover",
        summary="一次临时帮忙如果没有边界，很容易变成长期默认安排，最后消耗的是真正老实做事的人。",
        cover_prompt=(
            "A realistic wide landscape editorial photo for a restrained public-sector workplace essay. "
            "Scene: a quiet winding road through terraced fields in a misty mountain valley, with a modest "
            "distant civic building blended into the landscape, suggesting how temporary help can become a "
            "long-term responsibility through an ordinary environment. Natural warm daylight, "
            "restrained colors, balanced horizon, clear foreground and background layers, generous calm "
            "negative space for a WeChat headline. No indoor desk, laptop, smartphone, object still life, "
            "readable text, logos, official seals, or identifiable faces."
        ),
        illustration_prompt=(
            "A realistic northern European lakeside village landscape after harvest, two narrow footpaths "
            "meeting beside a small stone bridge, rows of trees leading toward a plain distant building, visually suggesting "
            "responsibility passing between work routes, soft late-afternoon light, restrained warm colors, "
            "blank building facade, no signage, no text, no vehicles, no identifiable people."
        ),
        body="""上午快下班时，隔壁科室有人拿着一摞材料过来，说他们下午要开会，表格差几项数据，能不能先帮着填一下。

这句话听起来很客气，也不算大事。我们办公室那位同事正在收拾桌面，听完还是把水杯放下，重新打开电脑。

他原本以为只是半小时的事。结果第二周，同样的表格又来了。

问题不在于帮一次忙，而在于很多“临时帮忙”，后来都会慢慢变成“默认由你兜底”。

## 01

体制内很多活，最开始并不会以正式任务的样子出现。

它往往是一句话：你熟一点，顺手帮看下；你上次做过，这次也麻烦你；你材料细，帮他们把一下关。

这些话都不难听，甚至带着一点信任。可人一旦接住了，后面就容易形成路径。

下次再遇到同类事情，大家第一反应不是重新分工，而是想起那个上次接住的人。

于是，一个人的可靠，慢慢变成了别人省事的理由。

那位同事后来跟我说，他不是不愿意帮忙。真正别扭的是，这件事没有人说清楚到底归谁，做完也不会出现在任何分工里。出了问题大家会来问，做得顺利却像本来就该这样。

这才是临时帮忙最容易伤人的地方。

它表面上只是多做一点，实际上改变了别人对你时间的预期。

## 02

为什么这种事在单位里常见？

因为许多工作不是按人的精力安排，而是按“谁最稳妥”安排。

一个岗位新人多，怕出错；一个环节时间紧，怕返工；一个材料要得急，怕没人能接上。最后最容易被想到的，往往不是最应该负责的人，而是最让人放心的人。

对安排工作的人来说，这样确实省心。任务能往前推，风险也小一点。

可对被借用的人来说，问题会慢慢堆起来。自己的活没有减少，临时活却多了一层；本职工作出了纰漏，没人会因为他帮别人兜过底就少批评一句。

更麻烦的是，一旦你前几次都没说清楚，后面再拒绝，别人反而觉得你变了。

这不是某个人小心眼，而是单位协作里常见的惯性。谁好说话，事情就容易往谁那里流；谁每次都能补上，漏洞就不容易被看见。

很多能干的人，最后不是被难题累垮，而是被一堆没有名分的小事拖住。

## 03

遇到这种临时帮忙，不一定要马上拒绝。

真有紧急情况，同事之间互相搭一把，是正常的。关键是帮的时候要把边界一起说出来。

可以先问清楚：这次是临时支持，还是以后都由我们这边负责？今天我能帮你补到几点，后面谁来接？如果材料要署名，责任口径怎么写？

这些话听起来有点麻烦，却能把事情从人情里拉回工作里。

有些人不好意思问，怕显得计较。可不问清楚，最后计较的成本会更高。一次帮忙可以靠热心，长期兜底必须靠明确分工。

对管理者来说，也要看见这种隐形借调。一个人经常帮别的环节补洞，不能只夸他能干，还要问一句：为什么那个洞一直存在？

否则，单位里最稳的人会越来越忙，最需要补课的环节却一直没有被真正修好。

下午3点多，那份表格总算补完了。对方拿走时说，下次还得麻烦你。

那位同事笑了笑，只回了一句：下次你们先把口径定好，我可以帮看，但不能一直替做。

这句话不重，却把边界放在了桌面上。

人在单位里可以热心，但热心不该变成没有尽头的兜底。能帮一次，是情分；一直默认，是分工出了问题。""",
    ),
    ArticleSeed(
        title="单位里最消耗人的，是所有消息都要马上回",
        slug="always-reply-message",
        summary="群消息的即时回复看似提高效率，实际会把人的注意力切碎，让普通工作日变得一直紧绷。",
        cover_prompt=(
            "A realistic wide landscape editorial photo for a restrained workplace essay. "
            "Scene: a quiet coastal town street after morning rain, tree-lined sidewalk leading toward a "
            "modest distant community building, soft daylight and a few distant indistinct pedestrians, "
            "conveying the scattered rhythm of messages through a calm outdoor environment. Restrained "
            "colors, balanced horizon, clean layers, generous empty space for a WeChat headline. No indoor "
            "desk, laptop, smartphone, object still life, readable text, logos, official seals, or identifiable faces."
        ),
        illustration_prompt=(
            "A realistic quiet lakeside trail in Canada at dusk, several tree-lined paths branching across open wetlands, "
            "small distant buildings under soft cloudy light, visual rhythm suggesting scattered attention, "
            "calm muted green and gray palette, clear depth, no signage, no text, no vehicles, no identifiable people."
        ),
        body="""早上刚到办公室，电脑还没开完，手机已经响了三次。

一个群里问昨天的数有没有核完，一个群里通知临时填表，还有一个群里有人艾特全体，说看到请回复。

其实都不是特别急的事。可每一条消息都像一根小线，拽着人马上停下手里的动作。

体制内很多人的累，不是一天做了多少大事，而是一天被无数个“马上回一下”切得七零八碎。

## 01

消息最消耗人的地方，是它让人很难完整做完一件事。

刚准备写材料，群里来一条口径调整；刚打开表格，电话又问另一个数据；好不容易把思路接上，领导在另一个群里发了个问号。

这些事情单独看都不大，合在一起就很折磨。

因为人的注意力不是开关。每被打断一次，都要重新找回刚才写到哪里、想到哪一层、哪个数字还没核。

有时候一上午看起来坐在工位上没停，到了中午却发现，真正完整推进的事并不多。

更微妙的是，很多消息并没有要求你立刻处理，只是要求你立刻表示“我看见了”。

收到、好的、马上、已转、在核。

这些回复像工作里的小票据，证明你没有失联，也证明这件事已经被你接住了。可回复越快，新的事情也越容易继续压过来。

时间久了，人会形成一种条件反射。手机一亮，心里先紧一下。

## 02

为什么单位里会越来越依赖即时回复？

一方面，是工作链条确实变快了。上面要进度，中间要留痕，下面要执行，群消息成了最省事的传递方式。

另一方面，即时回复给人一种确定感。

一个人回了“收到”，安排工作的人心里就踏实一点；一个群里一排“收到”，这件事好像已经推进了一半。

但这里有个容易被忽略的问题：回复不等于完成，看到也不等于有条件马上做。

有些任务需要查资料，有些数据要等别的口径，有些材料必须静下来写。它们不是靠多催两句就能变快的。

如果所有消息都被要求立刻回应，真正需要深一点处理的工作，反而会被挤到下班后。

白天忙着回复、转发、确认、解释，晚上没人打断了，才开始写那份最重要的材料。

看起来是个人效率问题，实际上是工作节奏被切碎后的结果。

在一些单位，谁回复慢一点，就容易被认为不上心。可一个人如果一直盯着手机，他也很难把需要质量的活做好。

## 03

要改变这种状态，普通人不能指望群消息突然变少。

能做的，是把“马上看到”和“马上完成”分开。

收到任务时，如果确实需要时间，可以回得具体一点：收到，10点前核完第一版；这个数据要等业务口确认，下午3点前反馈；我先处理手头会议材料，半小时后看这个表。

这样的回复不是拖延，而是把自己的工作顺序说清楚。

它比一个简单的“马上”更稳，也能减少后面反复催问。

对安排工作的人来说，也可以少发一些没有截止点的催促。能写清楚时间、责任人和结果形式，就别只写“抓紧”“尽快”“看到回复”。

消息越清楚，大家越不用来回猜。

真正高效的单位，不是每个人都秒回，而是重要事情有明确节奏，普通事情不随便打断。

下午快下班时，那个早上一直响的群终于安静下来。我看见同事把手机翻过来，开始补上午没写完的材料。

他盯着屏幕想了好一会儿，才把第一句话敲出来。

有些工作不是不想快，而是需要一段不被打断的时间。单位里的效率，也不该只看谁回消息最快。""",
    ),
)


def slugify_title(title: str) -> str:
    return re.sub(r"[\\/:*?\"<>|，。、“”]", "", title)


def final_prompt(scene_prompt: str, *, is_cover: bool = False) -> str:
    composition = COVER_SCENE_GUIDANCE if is_cover else ILLUSTRATION_SCENE_GUIDANCE
    return positive_prompt(f"{scene_prompt}. {LANDSCAPE_SCENE_GUIDANCE}. {composition}")


def resize_center_crop(image_path: Path, size: tuple[int, int]) -> None:
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        target_w, target_h = size
        src_w, src_h = image.size
        scale = max(target_w / src_w, target_h / src_h)
        resized = image.resize((round(src_w * scale), round(src_h * scale)), Image.Resampling.LANCZOS)
        left = (resized.width - target_w) // 2
        top = (resized.height - target_h) // 2
        cropped = resized.crop((left, top, left + target_w, top + target_h))
        cropped.save(image_path)


def make_image_with_comfyui(
    prompt: str,
    output_path: Path,
    *,
    endpoint: str,
    model_profile: str,
    max_wait: int,
    poll_seconds: float,
    steps: int,
    cfg: float,
    final_size: tuple[int, int],
    filename_prefix: str,
    is_cover: bool = False,
) -> None:
    if output_path.is_file() and output_path.stat().st_size > 0:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    profiles = comfy_images.load_profiles()
    profile = dict(profiles[model_profile])
    variables = dict(profile.get("variables", {}))
    variables.update({"STEPS": steps, "CFG": cfg})
    profile["variables"] = variables
    profiles[model_profile] = profile
    comfy_images.NEGATIVE_PROMPT = TIZHI_NEGATIVE_PROMPT
    client = comfy_images.ComfyClient(endpoint, timeout=30)
    client.preflight()
    complete_prompt = final_prompt(prompt, is_cover=is_cover)
    print(f"\n图片：{output_path.name}")
    print("正向 Prompt：")
    print(complete_prompt)
    print("反向 Prompt：")
    print(TIZHI_NEGATIVE_PROMPT)
    print("参数设置：")
    print(
        f"model={MODEL_NAME}, steps={steps}, cfg={cfg}, "
        f"size={final_size[0]}x{final_size[1]}, endpoint={endpoint}"
    )
    workflow = comfy_images.render_workflow(
        profiles,
        model_profile,
        prompt=complete_prompt,
        seed=abs(hash((filename_prefix, prompt))) % 1_000_000_000,
        filename_prefix=filename_prefix,
    )
    prompt_id = client.queue(workflow)
    images = client.wait_for_images(
        prompt_id,
        max_wait_seconds=max_wait,
        poll_seconds=poll_seconds,
    )
    client.download_image(images[-1], output_path)
    resize_center_crop(output_path, final_size)


def make_article_images_with_comfyui(
    seed: ArticleSeed,
    cover_path: Path,
    illustration_path: Path,
    *,
    endpoint: str,
    model_profile: str,
    max_wait: int,
    poll_seconds: float,
    steps: int,
    cfg: float,
) -> None:
    make_image_with_comfyui(
        seed.cover_prompt,
        cover_path,
        endpoint=endpoint,
        model_profile=model_profile,
        max_wait=max_wait,
        poll_seconds=poll_seconds,
        steps=steps,
        cfg=cfg,
        final_size=COVER_SIZE,
        filename_prefix=f"tizhi_content/covers/{seed.slug}",
        is_cover=True,
    )
    make_image_with_comfyui(
        seed.illustration_prompt,
        illustration_path,
        endpoint=endpoint,
        model_profile=model_profile,
        max_wait=max_wait,
        poll_seconds=poll_seconds,
        steps=steps,
        cfg=cfg,
        final_size=ILLUSTRATION_SIZE,
        filename_prefix=f"tizhi_content/illustrations/{seed.slug}",
    )


def approved_seed_body(seed: ArticleSeed) -> str:
    """Prefer the latest unchanged article body that already passed the local gate."""
    pattern = f"*-{slugify_title(seed.title)}.md"
    for candidate in sorted(ARTICLES_DIR.glob(pattern), reverse=True):
        report_path = BASE_DIR / "reviews" / "auto" / f"{candidate.stem}.json"
        if not report_path.is_file():
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if not report.get("passed") or report.get("article_sha256") != digest:
            continue
        text = candidate.read_text(encoding="utf-8", errors="ignore")
        body = re.sub(r"\A---.*?---\s*", "", text, count=1, flags=re.DOTALL)
        body = re.sub(r"(?m)^!\[[^\]]*\]\([^)]+\)\s*$", "", body)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        if body:
            return body
    return seed.body


def render_article_markdown(
    seed: ArticleSeed,
    today: date,
    *,
    cover_ref: str | None = None,
    illustration_ref: str | None = None,
) -> str:
    body = approved_seed_body(seed)
    if illustration_ref:
        body = body.replace("\n## 02\n", f"\n![]({illustration_ref})\n\n## 02\n", 1)
    cover = f"\n![]({cover_ref})\n" if cover_ref else ""
    return f'''---
title: "{seed.title}"
date: {today.isoformat()}
status: draft
summary: "{seed.summary}"
---
{cover}
{body}
'''


def run_aigc_gate(article_path: Path, *, force: bool = True) -> bool:
    command = [sys.executable, str(BASE_DIR / "ai_detector.py"), str(article_path)]
    if force:
        command.append("--force")
    return subprocess.run(command, cwd=BASE_DIR, text=True).returncode == 0


def render_article(
    seed: ArticleSeed,
    today: date,
    *,
    endpoint: str,
    model_profile: str,
    max_wait: int,
    poll_seconds: float,
    steps: int,
    cfg: float,
    overwrite: bool,
) -> tuple[Path, Path, Path] | None:
    article_path = ARTICLES_DIR / f"{today.isoformat()}-{slugify_title(seed.title)}.md"
    cover_path = COVER_DIR / f"{today.strftime('%Y%m%d')}_{seed.slug}-landscape.png"
    illustration_path = ILLUSTRATION_DIR / f"{today.strftime('%Y%m%d')}_{seed.slug}-landscape.png"
    if article_path.exists() and not overwrite:
        print(f"文章已存在，跳过生成：{article_path}")
        return article_path, cover_path, illustration_path

    article_path.write_text(render_article_markdown(seed, today), encoding="utf-8")
    print(f"生图前 AIGC 检测：{article_path.name}")
    if not run_aigc_gate(article_path):
        print(f"AIGC 未通过，已停止生图：{article_path}", file=sys.stderr)
        return None

    make_article_images_with_comfyui(
        seed,
        cover_path,
        illustration_path,
        endpoint=endpoint,
        model_profile=model_profile,
        max_wait=max_wait,
        poll_seconds=poll_seconds,
        steps=steps,
        cfg=cfg,
    )
    relative_cover = Path("..", "images", "covers", cover_path.name).as_posix()
    relative_illustration = Path("..", "images", "illustrations", illustration_path.name).as_posix()
    content = render_article_markdown(
        seed,
        today,
        cover_ref=relative_cover,
        illustration_ref=relative_illustration,
    )
    article_path.write_text(content, encoding="utf-8")
    print(f"图片写入后刷新 AIGC 报告：{article_path.name}")
    if not run_aigc_gate(article_path):
        print(f"最终 AIGC 未通过，禁止发布：{article_path}", file=sys.stderr)
        return None
    return article_path, cover_path, illustration_path


def generate_articles(
    count: int,
    today: date,
    *,
    endpoint: str,
    model_profile: str,
    max_wait: int,
    poll_seconds: float,
    steps: int,
    cfg: float,
    overwrite: bool,
) -> tuple[list[Path], int]:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    selected = SEEDS[:count]
    paths: list[Path] = []
    failures = 0
    for seed in selected:
        rendered = render_article(
            seed,
            today,
            endpoint=endpoint,
            model_profile=model_profile,
            max_wait=max_wait,
            poll_seconds=poll_seconds,
            steps=steps,
            cfg=cfg,
            overwrite=overwrite,
        )
        if rendered is None:
            failures += 1
            continue
        article_path, _cover_path, _illustration_path = rendered
        paths.append(article_path)
    return paths, failures


def publish_article(path: Path, *, verbose: bool, skip_ai_check: bool) -> int:
    command = [
        sys.executable,
        str(BASE_DIR / "publish_existing_article.py"),
        str(path),
        "--theme",
        PUBLISH_THEME,
        "--author",
        PUBLISH_AUTHOR,
    ]
    if verbose:
        command.append("--verbose")
    if skip_ai_check:
        command.append("--skip-ai-check")
    return subprocess.run(command, cwd=BASE_DIR, text=True).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="生成体制内文章，可选发布到公众号草稿箱")
    parser.add_argument("--count", type=int, default=2, choices=range(1, len(SEEDS) + 1))
    parser.add_argument(
        "--show-image-spec",
        action="store_true",
        help="只显示本地 ComfyUI FLUX.2 Klein 的正向、反向提示词和参数设置",
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--comfy-endpoint", default=DEFAULT_COMFY_ENDPOINT)
    parser.add_argument("--comfy-profile", default="flux2_klein", choices=("flux2_klein",))
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--cfg", type=float, default=DEFAULT_CFG)
    parser.add_argument("--max-wait", type=int, default=600)
    parser.add_argument("--poll-seconds", type=float, default=1.5)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="覆盖同名文章并重新执行 AIGC 后生图")
    parser.add_argument(
        "--skip-ai-check",
        action="store_true",
        help="只跳过发布脚本的重复检测；生图前 AIGC 门槛始终执行",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.show_image_spec:
        print(spec_text())
        return 0
    if args.steps < MIN_STEPS:
        parser.error(f"--steps 必须至少为 {MIN_STEPS}")
    if not CFG_MIN <= args.cfg <= CFG_MAX:
        parser.error(f"--cfg 必须在 {CFG_MIN} 到 {CFG_MAX} 之间")

    today = date.fromisoformat(args.date)
    paths, failures = generate_articles(
        args.count,
        today,
        endpoint=args.comfy_endpoint,
        model_profile=args.comfy_profile,
        max_wait=args.max_wait,
        poll_seconds=args.poll_seconds,
        steps=args.steps,
        cfg=args.cfg,
        overwrite=args.overwrite,
    )
    print("已生成文章：")
    for path in paths:
        print(path)

    if not args.publish:
        return 1 if failures else 0

    failed = failures
    for path in paths:
        code = publish_article(path, verbose=args.verbose, skip_ai_check=args.skip_ai_check)
        if code != 0:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
