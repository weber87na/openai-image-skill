# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""透過 OpenAI Images API 產生靜態圖片或原生動畫 GIF，以 uv 執行。"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import math
import os
from pathlib import Path
import re
import socket
import struct
import sys
import tempfile
from typing import Any
from urllib import error, request

API_URL = "https://api.openai.com/v1/images/generations"
DEFAULT_MODEL = "gpt-image-2.6-sunburst"
FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp", ".gif": "gif"}


class ImageError(Exception):
    """可直接呈現給使用者的錯誤。"""


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ImageError("拒絕 API 重新導向，避免將憑證傳送到其他位置。")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    prompt = result.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--prompt", help="圖片或動畫的描述")
    prompt.add_argument("--prompt-file", type=Path, help="UTF-8 提示詞檔案")
    result.add_argument("--output", type=Path, required=True, help="輸出路徑，格式預設從副檔名判斷")
    result.add_argument("--format", choices=("png", "jpeg", "webp", "gif"))
    result.add_argument("--model", default=None, help="預設 OPENAI_IMAGE_MODEL 或 GPT Image 2.6 Sunburst")
    result.add_argument("--size", help="auto 或 WIDTHxHEIGHT；省略時由 API 決定")
    result.add_argument("--quality", choices=("auto", "low", "medium", "high"))
    result.add_argument("--complexity", choices=("low", "medium", "high"))
    result.add_argument("--background", choices=("auto", "opaque", "transparent"))
    result.add_argument("--frames", type=int, help="原生 GIF 影格數，2–16，預設 9")
    result.add_argument("--frame-duration-ms", type=int, help="GIF 每格毫秒數，20–655350，預設 200")
    result.add_argument("--timeout", type=float, default=300, help="請求逾時秒數，預設 300")
    result.add_argument("--dry-run", action="store_true", help="只顯示請求內容，不連網、不讀取金鑰、不寫檔")
    result.add_argument("--overwrite", action="store_true", help="允許取代既有輸出檔案")
    return result


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.prompt_file is not None:
        try:
            prompt = args.prompt_file.read_text(encoding="utf-8-sig").strip()
        except (OSError, UnicodeError) as exc:
            raise ImageError("無法讀取 UTF-8 提示詞檔案。") from exc
    else:
        prompt = args.prompt.strip()
    if not prompt or len(prompt) > 32000:
        raise ImageError("提示詞長度必須為 1–32000 字元。")
    suffix_format = FORMATS.get(args.output.suffix.lower())
    if suffix_format is None:
        raise ImageError("輸出副檔名必須為 .png、.jpg、.jpeg、.webp 或 .gif。")
    output_format = args.format or suffix_format
    if output_format != suffix_format:
        raise ImageError("--format 必須與輸出副檔名一致；不可只把靜態圖片改名成 GIF。")
    model = (args.model or os.environ.get("OPENAI_IMAGE_MODEL") or DEFAULT_MODEL).strip()
    if not model:
        raise ImageError("模型名稱不可為空白。")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ImageError("--timeout 必須為正數且有限。")
    if args.size and args.size != "auto":
        match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", args.size)
        if not match:
            raise ImageError("--size 必須為 auto 或 WIDTHxHEIGHT；實際尺寸上限依模型及格式而定。")
        width, height = map(int, match.groups())
        if width % 16 or height % 16 or not 1 / 3 <= width / height <= 3:
            raise ImageError("尺寸必須為 16 的倍數，長寬比須介於 1:3 與 3:1；GIF 另有模型尺寸限制。")
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "n": 1, "output_format": output_format}
    for name in ("size", "quality", "complexity", "background"):
        value = getattr(args, name)
        if value is not None:
            payload[name] = value
    if args.background == "transparent" and output_format not in {"png", "webp"}:
        raise ImageError("API 的透明背景參數僅搭配 PNG 或 WebP；GIF 請省略 --background transparent。")
    if output_format == "gif":
        frames = 9 if args.frames is None else args.frames
        duration = 200 if args.frame_duration_ms is None else args.frame_duration_ms
        if not 2 <= frames <= 16:
            raise ImageError("--frames 必須介於 2 與 16。")
        if not 20 <= duration <= 655350:
            raise ImageError("--frame-duration-ms 必須介於 20 與 655350；API 會四捨五入至 10 ms。")
        payload.update(frame_count=frames, frame_duration_ms=duration)
    elif args.frames is not None or args.frame_duration_ms is not None:
        raise ImageError("--frames 與 --frame-duration-ms 僅適用於 GIF。")
    return payload


def call_api(payload: dict[str, Any], key: str, timeout: float) -> dict[str, Any]:
    req = request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            raw = response.read()
    except error.HTTPError as exc:
        detail = ""
        try:
            body = json.loads(exc.read())
            api_error = body.get("error", {}) if isinstance(body, dict) else {}
            if isinstance(api_error, dict):
                detail = str(api_error.get("message", ""))
        except (ValueError, OSError):
            pass
        detail = detail.replace(key, "[REDACTED]")[:1000]
        hints = {
            400: "請檢查模型、格式及 GIF 尺寸限制；不會自動改用逐格合成。",
            401: "請確認 OPENAI_API_KEY。",
            403: "請確認模型、組織驗證與 GIF preview 存取權限。",
            404: "請確認完整模型 ID 與帳號的模型存取權限。",
            429: "請檢查額度或速率限制；本工具不會自動重送付費請求。",
        }
        hint = hints.get(exc.code, "請求可能已被處理；檢查後再決定是否重送。")
        raise ImageError(f"OpenAI HTTP {exc.code}：{detail or 'API 拒絕請求。'} {hint}") from None
    except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise ImageError("OpenAI 連線失敗或逾時；請求可能已被處理。不自動重試，以免重複計費。") from exc
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ImageError("API 回傳非 JSON 資料；不會寫入輸出檔案。") from exc
    if not isinstance(result, dict):
        raise ImageError("API 回應格式不正確。")
    return result


def gif_info(data: bytes) -> dict[str, int]:
    if len(data) < 14 or data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ImageError("回傳資料不是 GIF。")
    width, height = struct.unpack_from("<HH", data, 6)
    if not width or not height:
        raise ImageError("GIF 畫布尺寸無效。")
    position = 13

    def consume(count: int) -> bytes:
        nonlocal position
        if position + count > len(data):
            raise ImageError("GIF 資料不完整。")
        chunk = data[position:position + count]
        position += count
        return chunk

    def subblocks() -> int:
        total = 0
        while True:
            length = consume(1)[0]
            if length == 0:
                return total
            consume(length)
            total += length

    packed = data[10]
    if packed & 0x80:
        consume(3 * (2 ** ((packed & 7) + 1)))
    frames = total_ms = delay_ms = 0
    while True:
        marker = consume(1)[0]
        if marker == 0x3B:
            if frames < 2:
                raise ImageError("API 回傳的是單格 GIF，不是動畫；不會假裝成功或自動重送。")
            return {"width": width, "height": height, "frames": frames, "duration_ms": total_ms}
        if marker == 0x21:
            label = consume(1)[0]
            if label == 0xF9:
                if consume(1)[0] != 4:
                    raise ImageError("GIF 控制區塊無效。")
                control = consume(4)
                delay_ms = struct.unpack_from("<H", control, 1)[0] * 10
                if consume(1) != b"\x00":
                    raise ImageError("GIF 控制區塊缺少結尾。")
            else:
                subblocks()
        elif marker == 0x2C:
            left, top, frame_width, frame_height, flags = struct.unpack("<HHHHB", consume(9))
            if not frame_width or not frame_height or left + frame_width > width or top + frame_height > height:
                raise ImageError("GIF 影格尺寸超出畫布。")
            if flags & 0x80:
                consume(3 * (2 ** ((flags & 7) + 1)))
            if not 2 <= consume(1)[0] <= 8:
                raise ImageError("GIF LZW 編碼設定無效。")
            if subblocks() == 0:
                raise ImageError("GIF 影格缺少影像資料。")
            frames += 1
            total_ms += delay_ms
            delay_ms = 0
        else:
            raise ImageError("GIF 區塊格式無效。")


def decode_image(response: dict[str, Any], output_format: str) -> tuple[bytes, dict[str, Any]]:
    items = response.get("data")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise ImageError("API 必須回傳一筆圖片資料。")
    encoded = items[0].get("b64_json")
    if not isinstance(encoded, str) or not encoded:
        raise ImageError("API 未回傳 b64_json；不會下載未驗證的 URL。")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ImageError("API 圖片的 Base64 編碼無效。") from exc
    info: dict[str, Any] = {"format": output_format, "bytes": len(data)}
    if output_format == "gif":
        info.update(gif_info(data))
    else:
        signatures = {
            "png": len(data) >= 33 and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR",
            "jpeg": len(data) >= 4 and data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"),
            "webp": len(data) >= 20 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
        }
        if not signatures.get(output_format, False):
            raise ImageError(f"API 回傳資料與要求的 {output_format} 格式不符。")
    return data, info


def check_output(output: Path, overwrite: bool) -> None:
    if output.is_dir():
        raise ImageError("輸出路徑是資料夾，請指定檔案名稱。")
    if output.exists() and not overwrite:
        raise ImageError("輸出檔案已存在；請換檔名，或明確使用 --overwrite。")
    for parent in output.parents:
        if parent.exists():
            if not parent.is_dir():
                raise ImageError("輸出路徑的父層不是資料夾。")
            break


def save_image(output: Path, data: bytes, overwrite: bool) -> None:
    check_output(output, overwrite)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".openai-image-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
        if overwrite:
            os.replace(temporary, output)
        else:
            # 硬連結以原子方式拒絕覆寫，不讓等待 API 期間新建的檔案遭到取代。
            os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_payload(args)
    if args.dry_run:
        return {"dry_run": True, "endpoint": API_URL, "request": payload, "output": str(args.output.resolve())}
    check_output(args.output, args.overwrite)
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ImageError("缺少 OPENAI_API_KEY。請在執行環境設定，不要貼到聊天或寫入專案。")
    if not all(33 <= ord(character) <= 126 for character in key):
        raise ImageError("OPENAI_API_KEY 含無效字元，請移除空白、換行或非 ASCII 字元。")
    response = call_api(payload, key, args.timeout)
    data, info = decode_image(response, payload["output_format"])
    save_image(args.output, data, args.overwrite)
    result = {"output": str(args.output.resolve()), "model": payload["model"], **info}
    if payload["output_format"] == "gif" and info["frames"] != payload["frame_count"]:
        result["warning"] = f"要求 {payload['frame_count']} 格，實際收到 {info['frames']} 格；以檔案內容為準。"
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run(args)
    except (ImageError, OSError, ValueError) as exc:
        # 不輸出追蹤堆疊、請求標頭或原始回應，避免洩漏憑證或巨量 Base64。
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
