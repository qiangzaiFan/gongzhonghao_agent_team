#!/usr/bin/env python3
"""Directly rewrite a linked article title and body without the emotion-agent template."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from daily_emotion_women import (
    ARTICLES_DIR,
    BASE_DIR,
    DEFAULT_OPENAI_MODEL,
    PUBLISH_THEME,
    EmotionWomenAutomation,
    choose_images,
    get_beijing_time,
    normalize_markdown,
    parse_json_object,
    run_preflight,
    slugify,
    truncate_for_log,
)
from rewrite_from_link import (
    cjk_len,
    compact_source_text,
    read_source,
    save_source_snapshot,
    shingle_overlap,
    source_preview,
    style_warnings,
)


MAX_DIRECT_SOURCE_CHARS = 16000
OVERLAP_WARN_THRESHOLD = 0.10


def build_direct_rewrite_messages(source_title: str, source_text: str, source_id: str) -> list[dict]:
    source_excerpt = compact_source_text(source_text, MAX_DIRECT_SOURCE_CHARS)

    system = """你是公众号文章原创改写编辑。
你的任务是基于用户提供的来源正文，重写标题和正文，让它成为一篇新的原创表达。
这不是情感 agent 爆款模板，不要套用固定框架，不要强行改成情感号故事文。
必须尊重原创边界：不得逐段换词，不得保留来源文章的连续表达、独特比喻、小标题和句式。只输出 JSON。"""

    user = f"""请对下面这篇来源文章做“直接原创改写”。

来源标识：{source_id}
来源标题：{source_title}

来源正文：
{source_excerpt}

## 硬性要求
1. 必须基于上面的来源正文改写；如果正文不足或像页面噪声，不要脑补。
2. 只做标题和正文改写，不使用 emotion-writer 模板，不写“爆款分析”，不套固定三段式。
3. 保留来源文章的核心主题、主要论点和信息关系，但改写为新的表达：
   - 标题必须重写；
   - 开头必须重写；
   - 小标题必须重写；
   - 段落顺序可以调整；
   - 例子、比喻、句式必须重写；
   - 不要出现 18 个字以上与来源相同的连续中文片段。
4. 不新增无法从来源支持的事实、名人名言、数据、案例。
5. 文章要像真人编辑后的公众号稿：语言自然、有节奏、少套话。
6. 不要提供规避平台检测的技巧；目标是提升原创度和可读性。

## 输出文章格式
- Markdown。
- frontmatter 只写 title。
- 正文 1000-2200 个中文字符。
- 至少 2 个二级小标题，方便公众号阅读。
- 可以有加粗重点句，但不要为了模板硬塞金句。
- 文末不要写“来源/参考资料/References”。

## 禁用表达
每个人都值得被爱、时间会治愈一切、我们应该认识到、综上所述、由此可见、正确的做法是、这告诉我们、在这个快节奏时代。

只输出 JSON：
{{
  "title": "改写后的标题",
  "topic_slug": "英文小写短横线 slug",
  "rewrite_notes": "说明改写时改动了哪些关键地方",
  "markdown": "完整 Markdown"
}}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def generate_direct_rewrite(source_title: str, source_text: str, source_id: str, model: str) -> dict:
    automation = EmotionWomenAutomation(article_count=1, provider="openai", openai_model=model)
    text = automation.openai_request(
        build_direct_rewrite_messages(source_title, source_text, source_id),
        use_web_search=False,
    )
    data = parse_json_object(text)
    if not isinstance(data.get("markdown"), str):
        raise RuntimeError(f"OpenAI 返回缺少 markdown：{truncate_for_log(json.dumps(data, ensure_ascii=False))}")
    return data


def save_direct_article(data: dict, source_text: str) -> tuple[Path, float]:
    title = str(data.get("title") or "").strip()
    markdown = str(data.get("markdown") or "")
    slug = slugify(str(data.get("topic_slug") or title), "direct-rewrite")
    timestamp = get_beijing_time().strftime("%Y%m%d_%H%M")
    path = ARTICLES_DIR / f"{timestamp}_direct-{slug}.md"
    suffix = 2
    while path.exists():
        path = ARTICLES_DIR / f"{timestamp}_direct-{slug}-{suffix}.md"
        suffix += 1

    image_urls = choose_images(1)[0]
    normalized = normalize_markdown(title, markdown, image_urls)
    overlap = shingle_overlap(source_text, normalized)
    path.write_text(normalized, encoding="utf-8")
    return path, overlap


def publish_path(article_path: Path, theme: str) -> tuple[bool, str]:
    result = subprocess.run(
        [
            sys.executable,
            str(BASE_DIR / "publish_existing_article.py"),
            str(article_path),
            "--theme",
            theme,
        ],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    return result.returncode == 0, output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从链接直接改写标题和正文，不使用情感 agent 爆款模板",
    )
    parser.add_argument("url", nargs="?", default="", help="原文链接")
    parser.add_argument(
        "--source-file",
        help="链接无法抓取时，传入复制好的原文 txt/md 文件",
    )
    parser.add_argument(
        "--openai-model",
        default=DEFAULT_OPENAI_MODEL,
        help=f"OpenAI API 模型，默认 {DEFAULT_OPENAI_MODEL}",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="生成并质检通过后发布到公众号草稿箱",
    )
    parser.add_argument(
        "--theme",
        default=PUBLISH_THEME,
        help=f"发布排版主题，默认 {PUBLISH_THEME}",
    )
    args = parser.parse_args()

    if not args.url and not args.source_file:
        parser.error("必须提供 url，或使用 --source-file 提供原文")

    start = time.perf_counter()
    ARTICLES_DIR.mkdir(exist_ok=True)
    source_id = args.url or str(args.source_file)

    print("读取来源正文...")
    source_title, source_text = read_source(args)
    snapshot_path = save_source_snapshot(source_title, source_text, source_id)
    print(f"来源标题：{source_title}")
    print(f"抽取正文：{len(source_text)} 字符，{cjk_len(source_text)} 个中文字符")
    print(f"来源快照：{snapshot_path}")
    print(f"正文预览：{source_preview(source_text)}")

    print("直接改写标题和正文...")
    data = generate_direct_rewrite(source_title, source_text, source_id, args.openai_model)
    path, overlap = save_direct_article(data, source_text)
    print(f"已保存：{path}")
    print(f"来源相似度指纹：{overlap:.2%}")
    if overlap >= OVERLAP_WARN_THRESHOLD:
        print("警告：与来源存在偏高的连续片段重合，建议人工继续改写。")

    warnings = style_warnings(path.read_text(encoding="utf-8"))
    if warnings:
        print("风格提示：")
        for warning in warnings:
            print(f"- {warning}")

    ok, output = run_preflight(path)
    if not ok:
        print("本地质检未通过：", file=sys.stderr)
        print(output, file=sys.stderr)
        return 1
    print(output)

    if args.publish:
        print("发布到公众号草稿箱...")
        published, publish_output = publish_path(path, args.theme)
        print(publish_output)
        if not published:
            return 1

    if data.get("rewrite_notes"):
        print(f"改写说明：{data['rewrite_notes']}")
    elapsed = time.perf_counter() - start
    print(f"完成，耗时 {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
