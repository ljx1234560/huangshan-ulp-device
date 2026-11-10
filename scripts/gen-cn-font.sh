#!/usr/bin/env bash
# 中文字体子集生成：GB2312 一级常用字(3755) + CJK 标点 + ASCII -> LVGL C 数组。
# 产物：src/ui/fonts/ui_font_cn_16.c（正文）与 ui_font_cn_20.c（标题）。
# 依赖：python（标准库即可）、node/npx（lv_font_conv 经 npm 拉取）。
# 用法：bash scripts/gen-cn-font.sh [字体文件路径]
#   默认字体 C:/Windows/Fonts/Deng.ttf（等线，Windows 自带）。
# 版权提示：等线为 Windows 附带字体，仅限课程开发演示；
#   公开演示/发布前请换 OFL 开源字体重新生成，例如：
#   思源黑体 https://github.com/adobe-fonts/source-han-sans (SIL OFL 1.1)
set -euo pipefail

FONT="${1:-/c/Windows/Fonts/Deng.ttf}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$SCRIPT_DIR/../src/ui/fonts"
WORK_DIR="$(mktemp -d)"

mkdir -p "$OUT_DIR"

python - "$WORK_DIR/symbols.txt" <<'PYEOF'
import sys

chars = []
# GB2312 一级汉字区：0xB0A1-0xD7F9
for row in range(0xB0, 0xD8):
    for col in range(0xA1, 0xFF):
        try:
            chars.append(bytes([row, col]).decode("gb2312"))
        except Exception:
            pass
punct = ("，。！？：；、“”‘’（）《》…—～·％＋－【】")
seen, out = set(), []
for c in chars + list(punct):
    if c not in seen:
        seen.add(c)
        out.append(c)
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write("".join(out))
print("symbols:", len(out))
PYEOF

SYMBOLS="$(cat "$WORK_DIR/symbols.txt")"

npx --yes lv_font_conv \
  --no-compress --no-prefilter --bpp 4 \
  --size 16 --font "$FONT" -r 0x20-0x7F --symbols "$SYMBOLS" \
  --format lvgl --lv-font-name ui_font_cn_16 \
  -o "$OUT_DIR/ui_font_cn_16.c"

npx --yes lv_font_conv \
  --no-compress --no-prefilter --bpp 4 \
  --size 20 --font "$FONT" -r 0x20-0x7F --symbols "$SYMBOLS" \
  --format lvgl --lv-font-name ui_font_cn_20 \
  -o "$OUT_DIR/ui_font_cn_20.c"

rm -rf "$WORK_DIR"
echo "done: $OUT_DIR"
