#!/usr/bin/env python3
"""Register and validate reference metadata, including 100k+ title retention."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from pathlib import Path
from urllib import error, request
from urllib.parse import urlparse


READ_COUNT_THRESHOLD = 100_000
DEFAULT_TIMEOUT = 20


class ReferenceValidationError(ValueError):
    pass


def _parse_scalar(value: str) -> object:
    value = value.strip()
    if not value:
        return ""
    if value[0:1] in {"'", '"'} and value[-1:] == value[0]:
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def load_record(path: Path) -> dict[str, object]:
    record: dict[str, object] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ReferenceValidationError(f"无效记录行：{raw_line}")
        key, value = line.split(":", 1)
        record[key.strip()] = _parse_scalar(value)
    return record


def _quote_yaml(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_record(path: Path, record: dict[str, object]) -> None:
    keys = (
        "source_url",
        "source_title",
        "read_count",
        "proof",
        "verified_at",
        "keep_title",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(f"{key}: {_quote_yaml(record.get(key, ''))}" for key in keys) + "\n",
        encoding="utf-8",
    )


def normalize_title(title: str) -> str:
    title = html.unescape(title)
    title = re.sub(r"\s*[-–—|]\s*微信公众平台\s*$", "", title)
    return re.sub(r"\s+", "", title).strip("'\"“”")


def extract_page_title(markup: str) -> str:
    for meta in re.finditer(r"<meta\b[^>]*>", markup, re.I):
        tag = meta.group(0)
        if re.search(r"(?:property|name)\s*=\s*['\"]og:title['\"]", tag, re.I):
            found = re.search(r"content\s*=\s*(['\"])(.*?)\1", tag, re.I | re.S)
            if found:
                return html.unescape(found.group(2)).strip()
    js_title = re.search(r"\bmsg_title\s*=\s*(['\"])(.*?)\1", markup, re.S)
    if js_title:
        return html.unescape(js_title.group(2)).strip()
    title = re.search(r"<title[^>]*>(.*?)</title>", markup, re.I | re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else ""


def fetch_page_title(url: str) -> str:
    user_agent = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1 astrology-reference/1.0"
    )
    req = request.Request(url, headers={"User-Agent": user_agent, "Accept": "text/html"})
    try:
        with request.urlopen(req, timeout=DEFAULT_TIMEOUT) as response:
            raw = response.read(1_000_000)
            charset = response.headers.get_content_charset() or "utf-8"
    except error.HTTPError as exc:
        raise ReferenceValidationError(f"来源链接无法访问：HTTP {exc.code}") from exc
    except (error.URLError, TimeoutError) as exc:
        raise ReferenceValidationError(f"来源链接无法访问：{exc}") from exc
    return extract_page_title(raw.decode(charset, errors="replace"))


def resolve_proof(record_path: Path, value: object) -> Path:
    proof = Path(str(value)).expanduser()
    if proof.is_absolute():
        return proof
    return (record_path.parent / proof).resolve()


def validate_record(
    record: dict[str, object],
    record_path: Path,
    *,
    expected_title: str | None = None,
    check_url: bool = True,
) -> list[str]:
    errors: list[str] = []
    required = {"source_url", "source_title", "read_count", "proof", "verified_at", "keep_title"}
    missing = sorted(required - set(record))
    if missing:
        errors.append("缺少字段：" + "、".join(missing))
        return errors

    keep_title = record.get("keep_title") is True
    if expected_title is not None and normalize_title(str(record.get("source_title", ""))) != normalize_title(expected_title):
        errors.append("文章标题与参考记录的 source_title 不一致")

    if not keep_title:
        return errors

    url = str(record.get("source_url", ""))
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append("keep_title=true 时 source_url 必须是可访问的 HTTP/HTTPS 链接")

    read_count = record.get("read_count")
    if not isinstance(read_count, int) or isinstance(read_count, bool):
        errors.append("read_count 必须是整数")
    elif read_count < READ_COUNT_THRESHOLD:
        errors.append(f"阅读数 {read_count} 低于原标题保留线 {READ_COUNT_THRESHOLD}")

    source_title = str(record.get("source_title", "")).strip()
    if not source_title:
        errors.append("source_title 不能为空")

    verified_at = str(record.get("verified_at", "")).strip()
    try:
        dt.date.fromisoformat(verified_at)
    except ValueError:
        errors.append("verified_at 必须是 YYYY-MM-DD 日期")

    proof_value = str(record.get("proof", "")).strip()
    if not proof_value:
        errors.append("keep_title=true 时 proof 不能为空")
    elif not resolve_proof(record_path, proof_value).is_file():
        errors.append(f"阅读量证明不存在：{resolve_proof(record_path, proof_value)}")

    if check_url and not errors:
        try:
            page_title = fetch_page_title(url)
        except ReferenceValidationError as exc:
            errors.append(str(exc))
        else:
            if not page_title:
                errors.append("来源页面可访问，但无法提取页面标题")
            elif normalize_title(page_title) != normalize_title(source_title):
                errors.append(f"页面标题与 source_title 不一致：{page_title}")
    return errors


def default_record_path(title: str) -> Path:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower() or "reference"
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    return Path(__file__).parent / "benchmarks" / f"{stamp}_{cleaned[:48]}.yaml"


def register(args: argparse.Namespace) -> int:
    record = {
        "source_url": args.source_url,
        "source_title": args.source_title,
        "read_count": args.read_count,
        "proof": str(Path(args.proof).expanduser().resolve()) if args.proof else "",
        "verified_at": args.verified_at,
        "keep_title": args.keep_title,
    }
    output = args.out or default_record_path(args.source_title)
    errors = validate_record(
        record,
        output,
        expected_title=args.source_title,
        check_url=not args.skip_url_check,
    )
    if errors:
        print("参考记录未通过：", file=sys.stderr)
        print("\n".join(f"- {item}" for item in errors), file=sys.stderr)
        return 1
    write_record(output, record)
    print(f"已写入参考记录：{output}")
    print("原标题权限：" + ("允许" if args.keep_title else "不允许"))
    return 0


def validate(args: argparse.Namespace) -> int:
    if not args.record.is_file():
        print(f"参考记录不存在：{args.record}", file=sys.stderr)
        return 1
    record = load_record(args.record)
    errors = validate_record(
        record,
        args.record,
        expected_title=args.article_title,
        check_url=not args.skip_url_check,
    )
    if errors:
        print("参考记录未通过：")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    print("参考记录通过")
    print("原标题权限：" + ("允许" if record.get("keep_title") is True else "不允许"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="登记和校验星座文章参考来源")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register", help="登记一条参考记录")
    register_parser.add_argument("--source-url", required=True)
    register_parser.add_argument("--source-title", required=True)
    register_parser.add_argument("--read-count", required=True, type=int)
    register_parser.add_argument("--proof")
    register_parser.add_argument("--verified-at", default=dt.date.today().isoformat())
    register_parser.add_argument("--keep-title", action="store_true")
    register_parser.add_argument("--skip-url-check", action="store_true")
    register_parser.add_argument("--out", type=Path)
    register_parser.set_defaults(func=register)

    validate_parser = subparsers.add_parser("validate", help="校验已有参考记录")
    validate_parser.add_argument("record", type=Path)
    validate_parser.add_argument("--article-title")
    validate_parser.add_argument("--skip-url-check", action="store_true")
    validate_parser.set_defaults(func=validate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
