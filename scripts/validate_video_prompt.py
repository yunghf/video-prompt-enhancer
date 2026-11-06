#!/usr/bin/env python3
"""Multi-model video prompt validator for the video-prompt-enhancer skill.

Deterministic checks per target model:
  h3      - Base 3-field / Ref2VA 6-segment shape, shot timeline, alignment line,
            audio-field dialogue leakage, reference-tag consistency
  seedance- duration/ratio legality, prompt conciseness (heuristic)
  wan3    - duration/ratio legality, multi-shot timestamp timeline
  kling3  - 镜头 n, m, words; format (shot count, per-shot seconds, sum == total,
            per-shot length, half-width punctuation)
  libtv   - duration/ratio legality, {{Image N}} references with action notes,
            named-negative-word heuristic (anti-summoning rule)

Usage:
  python validate_video_prompt.py <prompt-file> --model <h3|seedance|wan3|kling3|libtv>
                                  [--duration SS] [--ratio R]

Exit code: 0 = pass, 1 = at least one FAIL, 2 = usage/read error.
"""

import argparse
import re
import sys

# ---------------------------------------------------------------- model tables

MODELS = {
    "h3": {
        "durations": set(range(4, 16)),  # 4-15s integer seconds
        "ratios": None,                  # constrained by alignment/frames, not a flag
        "default_duration": None,
    },
    "seedance": {
        "durations": {5, 10},
        "ratios": {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"},
        "default_duration": 5,
    },
    "wan3": {
        "durations": set(range(2, 31)) | {-1},  # 2-30s or smart
        "ratios": {"16:9", "4:3", "1:1", "3:4", "9:16", "adaptive"},
        "default_duration": None,
    },
    "kling3": {
        "durations": set(range(3, 16)),  # 3-15s
        "ratios": {"16:9", "9:16", "1:1"},
        "default_duration": None,
    },
    "libtv": {
        "durations": set(range(4, 16)),  # 4-15s, 8s production default
        "ratios": {"16:9", "9:16", "1:1"},
        "default_duration": 8,
    },
}

# ------------------------------------------------------------ H3 (existing) spec

BASE_FIELDS = [
    "integrated_multimodal_description",
    "overall_soundscape",
    "non_diegetic_music",
]
REF2VA_SEGMENTS = [
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
]
AUDIO_FIELDS = ("overall_soundscape", "non_diegetic_music")

ALIGN_LINE_RE = re.compile(
    r"^(For the target video, at 0\.00 seconds|How the reference pictures align)",
    re.IGNORECASE,
)
SS_RE = re.compile(r"\b(\d+\.\d{2})-second mark\b")
CUT_RE = re.compile(r"\[\s*Shot\s+(\d+)\s*\][^\n]*?\bAt\s+(\d{1,2}:\d{2}(?:\.\d{1,3})?)")
TAG_RE = re.compile(r"<\s*(Subject|Picture|Video|Audio)\s+(\d+)\s*>", re.IGNORECASE)

DIALOGUE_PATTERNS = [
    re.compile(r"\b(says?|said|asks?|asked|replies?|replied|shouts?|shouted|whispers?|whispered|sings?|sang|screams?|screamed|calls?|called)\b\s*[:,\"].{0,40}\"", re.IGNORECASE),
    re.compile(r"[\"“][^\"”]{2,120}[\"”]"),
    re.compile(r"^[^a-zA-Z]{0,6}(说|问道|问|喊|叫道|低声说|唱道|喊道|喊道：|说：)[:：]?"),
    re.compile(r"(说|问|喊|唱)(道|道：|：|:)[\"“「]"),
]

# ------------------------------------------------------------- shared utilities

DIMENSION_KEYWORDS = {
    "主体": ["主体", "人物", "角色", "少年", "少女", "女孩", "女人", "男子", "男孩", "男人", "孩子", "老人", "厨师", "学生", "白领", "猫", "狗", "兔子", "鸟", "鱼", "它", "他", "她", "subject", "woman", "man", "girl", "boy", "cat", "dog"],
    "动作": ["动作", "转身", "走", "跑", "跳", "拿起", "放下", "举起", "回头", "看向", "微笑", "走向", "坐下", "站起来", "飘落", "闪烁", "奔", "walk", "runs?", "turns?", "looks"],
    "场景氛围": ["场景", "环境", "背景", "街道", "教室", "房间", "森林", "草原", "草地", "花园", "海", "天空", "黄昏", "夜晚", "清晨", "雨", "雪", "氛围", "setting", "street", "room", "forest", "night", "dusk"],
    "运镜": ["镜头", "运镜", "推近", "推远", "拉远", "横移", "摇摄", "环绕", "跟拍", "俯拍", "仰拍", "特写", "全景", "中景", "近景", "camera", "push", "pan", "track", "orbit", "close-up", "wide shot"],
    "光影": ["光", "逆光", "侧光", "顶光", "黄昏", "黄金时刻", "蓝调", "色调", "调色", "暖", "冷", "影", "light", "lighting", "golden hour", "warm", "cool"],
    "风格": ["风格", "电影感", "写实", "动画", "水墨", "赛博朋克", "胶片", "质感", "绘本", "cinematic", "anime", "realistic", "documentary", "watercolor"],
    "音频": ["环境音", "音效", "台词", "旁白", "BGM", "配乐", "音乐", "voiceover", "audio", "ambience", "sound"],
}


def parse_segments(text, field_names):
    """Split prompt into name -> block, supporting both inline and standalone field headers."""
    blocks = {}
    lines = text.splitlines()
    header_re = re.compile(r"^\s*(" + "|".join(field_names) + r")\s*:\s*(.*)$")
    current = None
    for line in lines:
        m = header_re.match(line)
        if m:
            current = m.group(1)
            blocks.setdefault(current, [])
            if m.group(2).strip():
                blocks[current].append(m.group(2))
            continue
        if current is not None:
            blocks[current].append(line)
    return {k: "\n".join(v) for k, v in blocks.items()}


def ts_to_secs(ts):
    parts = ts.split(":")
    return int(parts[0]) * 60 + float(parts[1])


# ------------------------------------------------------------------- H3 checks


def check_h3(text, duration, report):
    segments = parse_segments(text, BASE_FIELDS + REF2VA_SEGMENTS)
    mode = "ref2va" if re.search(r"^\s*subject_definitions\s*:", text, re.M) else "base"

    # shape
    if mode == "base":
        ok = all(f in segments for f in BASE_FIELDS) and not segments.get("subject_definitions")
        report("PASS" if ok else "FAIL", "h3-shape", "Base 恰好三字段且顺序正确" if ok else "Base 字段缺失/多余（应为三字段且无 Ref2VA 段）")
    else:
        bad = [s for s in REF2VA_SEGMENTS if not segments.get(s, "").strip()]
        report("PASS" if not bad else "FAIL", "h3-shape", "Ref2VA 六段非空" if not bad else "Ref2VA 空段/缺失: %s" % ", ".join(bad))

    # alignment line
    has_align = any(ALIGN_LINE_RE.match(l.strip()) for l in text.splitlines())
    ss = SS_RE.findall(text)
    if has_align:
        bad = [v for v in ss if not re.fullmatch(r"\d+\.\d{2}", v)]
        if bad:
            report("FAIL", "h3-align", "尾帧 S.SS 非两位小数: %s" % ", ".join(bad))
        elif not ss:
            report("FAIL", "h3-align", "对齐指令存在但缺少 'S.SS-second mark' 锚点")
        else:
            report("PASS", "h3-align", "对齐指令存在且 S.SS 两位小数 (%s)" % ", ".join(ss))
    else:
        report("WARN", "h3-align", "未发现对齐指令行；T2VA 不需要，I2VA/FL2VA/L2VA 必须在首字段前补充")

    # timeline
    desc = segments.get("integrated_multimodal_description") or segments.get("detailed_description") or text
    m1 = re.search(r"\[\s*Shot\s+1\s*\](.{0,80})", desc, re.S)
    shot1_ts = re.search(r"\bAt\s+\d{1,2}:\d{2}(\.\d{1,3})?", m1.group(1)) if m1 else None
    report("PASS" if not shot1_ts else "FAIL", "h3-shot1",
           "[Shot 1] 开头无时间戳" if not shot1_ts else "[Shot 1] 开头误带时间戳 %s" % shot1_ts.group(0))

    cuts = CUT_RE.findall(desc)
    cut_secs = [(int(n), ts_to_secs(t)) for n, t in cuts]
    prev, bad = -1.0, None
    for n, s in cut_secs:
        if s <= prev:
            bad = "Shot %s 切点 %.3fs 未严格递增（前一个 %.3fs）" % (n, s, prev)
            break
        prev = s
    report("PASS" if not bad else "FAIL", "h3-timeline",
           "切点严格递增（%d 个带时间戳镜头）" % len(cut_secs) if not bad else bad)

    dur = float(duration) if duration is not None else (float(ss[-1]) if ss else None)
    if dur is not None:
        over = [(n, s) for n, s in cut_secs if s > dur + 1e-9]
        report("PASS" if not over else "FAIL", "h3-bounds",
               "全部切点落在时长内" if not over else "切点越界（>%.2fs）: %s" % (dur, ", ".join("Shot %s@%.3f" % x for x in over)))
    else:
        report("WARN", "h3-bounds", "无时长信息，跳过越界检查")

    # audio field boundaries
    for field in AUDIO_FIELDS:
        body = segments.get(field)
        if not body:
            continue
        hit = next((l for l in body.splitlines() if any(p.search(l) for p in DIALOGUE_PATTERNS)), None)
        report("PASS" if not hit else "WARN", "h3-audio-%s" % field,
               "%s 未检出对白特征" % field if not hit else "%s 疑似混入对白: '%s'" % (field, hit.strip()[:80]))

    # Ref2VA tag consistency
    if mode == "ref2va":
        defs = segments.get("subject_definitions", "")
        defined = {(k.lower(), int(n)) for k, n in TAG_RE.findall(defs)}
        used = {}
        for name, body in segments.items():
            if name == "subject_definitions":
                continue
            for k, n in TAG_RE.findall(body or ""):
                used.setdefault((k.lower(), int(n)), []).append(name)
        undef = {k: v for k, v in used.items() if k not in defined}
        if undef:
            report("FAIL", "h3-tags", "标签未定义先用: " + "; ".join("<%s %s> used in %s" % (k[0].title(), k[1], ",".join(v)) for k, v in undef.items()))
        else:
            report("PASS", "h3-tags", "标签定义与使用一致")


# --------------------------------------------------------- shared param checks


def check_params(model, text, duration, ratio, report):
    cfg = MODELS[model]
    if duration is not None:
        try:
            d = float(duration)
        except ValueError:
            report("FAIL", "param-duration", "duration 无法解析为数字: %s" % duration)
            d = None
        if d is not None:
            ok = (d == int(d) and int(d) in cfg["durations"]) if model != "wan3" else (d in cfg["durations"] or d == -1)
            report("PASS" if ok else "FAIL", "param-duration",
                   "duration=%s 合法" % d if ok else "duration=%s 不在 %s 合法集 %s" % (d, model, sorted(cfg["durations"]) if model != "wan3" else "2-30 或 -1"))
    else:
        report("WARN", "param-duration", "未提供 --duration，跳过时长合法性检查（%s 合法集: %s）" % (model, sorted(cfg["durations"]) if model != "wan3" else "2-30 或 -1"))
    if ratio is not None:
        ok = ratio in (cfg["ratios"] or set())
        if cfg["ratios"] is None:
            report("WARN", "param-ratio", "%s 无独立比例参数（由素材/对齐行决定），--ratio %s 仅作记录" % (model, ratio))
        else:
            report("PASS" if ok else "FAIL", "param-ratio",
                   "ratio=%s 合法" % ratio if ok else "ratio=%s 不在合法集 %s" % (ratio, sorted(cfg["ratios"])))


def check_dimensions(text, report):
    low = text.lower()
    hit, miss = [], []
    for dim, words in DIMENSION_KEYWORDS.items():
        if any(w in low for w in words):
            hit.append(dim)
        else:
            miss.append(dim)
    # 比例/时长以参数形式给出，这里只看文本内可检出维度
    if len(hit) >= 5:
        report("PASS", "dim-coverage", "八维度文本命中 %d/7：%s" % (len(hit), "、".join(hit)))
    else:
        report("WARN", "dim-coverage", "八维度命中偏低（%d/7）：%s；缺失维度 %s——若为精简提示词可忽略" % (len(hit), "、".join(hit), "、".join(miss)))


# ------------------------------------------------------------ kling3 checks


def check_kling3(text, duration, report):
    # shot starts tolerate half- or full-width commas during detection, delimiters are checked separately
    starts = list(re.finditer(r"镜头\s*(\d+)\s*([,，])\s*([\d.]+)\s*([,，])", text))
    if not starts:
        report("WARN", "kling-format", "未检出'镜头 n, m, words;'多镜头语法；单镜头直述式提示词可忽略，多镜头必须用该格式")
        return
    numbers = [int(m.group(1)) for m in starts]
    secs = [float(m.group(3)) for m in starts]
    short = [n for n, s in zip(numbers, secs) if s < 1]
    total = sum(secs)
    ok_numbering = numbers == list(range(1, len(numbers) + 1))
    too_long = []
    for i, m in enumerate(starts):
        wstart = m.end()
        wend = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        # words run to the next ";" or the text end; trim a trailing delimiter run
        seg = text[wstart:wend]
        semi = seg.find(";")
        if semi >= 0:
            seg = seg[:semi]
        if len(seg.strip()) > 512:
            too_long.append((numbers[i], len(seg.strip())))
    fw_comma = any(m.group(2) == "，" or m.group(4) == "，" for m in starts)
    boundary_bad = []
    for i, m in enumerate(starts):
        if i == 0:
            continue
        prev_end = starts[i - 1].end()
        gap = text[prev_end:m.start()]
        gm = re.search(r"([;；,，])\s*$", gap)
        if gm and gm.group(1) in ("；", "，"):
            boundary_bad.append(gm.group(1))
        elif not gm:
            boundary_bad.append("无分隔符")
    report("PASS" if ok_numbering else "FAIL", "kling-numbering", "分镜序号连续从 1 开始（共 %d 镜）" % len(numbers) if ok_numbering else "分镜序号不连续: %s" % numbers)
    report("PASS" if len(numbers) <= 6 else "FAIL", "kling-count", "分镜数 %d ≤ 6" % len(numbers) if len(numbers) <= 6 else "分镜数 %d 超过 6 个上限" % len(numbers))
    report("PASS" if not short else "FAIL", "kling-shotsec", "各分镜 ≥1s" if not short else "分镜时长 <1s: %s" % short)
    report("PASS" if not too_long else "FAIL", "kling-shotlen", "各分镜 ≤512 字符" if not too_long else "分镜超 512 字符: %s" % too_long)
    report("PASS" if not fw_comma else "FAIL", "kling-delim",
           "镜头语法用半角逗号/分号分隔" if not fw_comma else "镜头语法出现全角逗号分隔（须半角 ,）")
    report("PASS" if not boundary_bad else "FAIL", "kling-boundary",
           "镜间分隔符合法" if not boundary_bad else "镜间分隔需半角分号;，检出: %s" % boundary_bad)
    if duration is not None:
        d = float(duration)
        report("PASS" if abs(total - d) < 1e-6 else "FAIL", "kling-sum",
               "分镜时长和 %g s = 总时长 %g s" % (total, d) if abs(total - d) < 1e-6 else "分镜时长和 %g s ≠ 总时长 %g s" % (total, d))
    else:
        report("WARN", "kling-sum", "未提供 --duration，分镜时长和 %g s 无法核对" % total)
    report("PASS", "kling-format", "多镜头语法 '镜头 n, m, words;' 完整（%d 镜）" % len(numbers))


# ------------------------------------------------------------- wan3 checks


def check_wan3(text, duration, report):
    stamps = re.findall(r"\[\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s*\]", text)
    if not stamps:
        report("WARN", "wan3-shots", "未检出 [MM:SS - MM:SS] 时间戳分镜；单镜头可忽略")
        return
    bad, prev = None, -1.0
    for a, b in stamps:
        sa, sb = ts_to_secs(a), ts_to_secs(b)
        if sb <= sa:
            bad = "时间戳区间非正: [%s - %s]" % (a, b)
            break
        if sa < prev - 1e-9:
            bad = "镜头起点 %.2fs 与前一段重叠/倒退（前一终点 %.2fs）" % (sa, prev)
            break
        prev = sb
    report("PASS" if not bad else "FAIL", "wan3-timeline", "时间戳分镜连续无重叠（%d 镜）" % len(stamps) if not bad else bad)
    if duration is not None:
        d = float(duration)
        end = ts_to_secs(stamps[-1][1])
        report("PASS" if abs(end - d) < 1e-6 else "FAIL", "wan3-bounds",
               "末镜结束 %.2fs = 总时长 %g s" % (end, d) if abs(end - d) < 1e-6 else "末镜结束 %.2fs ≠ 总时长 %g s" % (end, d))


# ------------------------------------------------------------- libtv checks


def check_libtv(text, duration, report):
    refs = re.findall(r"\{\{\s*(Image|Video|Audio)\s*(\d+)\s*\}\}", text, re.I)
    if not refs:
        report("WARN", "libtv-refs", "未检出 {{Image N}}/{{Video N}}/{{Audio N}} 引用；纯文生节点可忽略")
    else:
        orphan = []
        for kind, n in refs:
            for m in re.finditer(r"\{\{\s*%s\s*%s\s*\}\}" % (kind, n), text, re.I):
                tail = text[m.end():m.end() + 30]
                if not re.search(r"(锚定|锁定|确定|参考|作为|是|为|在|按|用|从|存放|呈现|复刻|对应|的)", tail):
                    orphan.append("{{%s %s}}" % (kind, n))
                    break
        report("PASS" if not orphan else "WARN", "libtv-refs",
               "全部引用均带作用说明" if not orphan else "引用缺作用说明（应写'{{Image 1}} 锚定…'式）: %s" % ", ".join(sorted(set(orphan))))
    negatives = re.findall(r"(不要|不能|禁止|别出现|避免出现|without|no [a-z]+ in frame)", text)
    report("PASS" if not negatives else "FAIL", "libtv-negative",
           "未检出点名负面词" if not negatives else "检出点名负面词（触发反召唤，应改为正面穷举'画面里有且仅有…'）: %s" % "、".join(sorted(set(negatives))))
    if duration is not None and float(duration) > 12:
        report("WARN", "libtv-drift", "duration=%ss > 12s，长镜头后半易漂移，需在提示词中声明'全程同一场景、按图不变'" % duration)


# ---------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description="Validate a structured video-generation prompt.")
    ap.add_argument("file", help="path to the prompt text file")
    ap.add_argument("--model", required=True, choices=["h3", "seedance", "wan3", "kling3", "libtv"])
    ap.add_argument("--duration", help="requested length in seconds (e.g. 8 or 8.00; -1 = smart)")
    ap.add_argument("--ratio", help="aspect ratio (e.g. 16:9)")
    args = ap.parse_args()

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print("ERROR: cannot read %s (%s)" % (args.file, e))
        return 2

    results = []

    def report(status, cid, msg, extra=None):
        results.append((status, cid, msg))

    print("=== video prompt validation (model=%s, duration=%s, ratio=%s) ===" % (
        args.model, args.duration or "unspecified", args.ratio or "unspecified"))

    check_dimensions(text, report)
    check_params(args.model, text, args.duration, args.ratio, report)
    if args.model == "h3":
        check_h3(text, args.duration, report)
    elif args.model == "kling3":
        check_kling3(text, args.duration, report)
    elif args.model == "wan3":
        check_wan3(text, args.duration, report)
    elif args.model == "libtv":
        check_libtv(text, args.duration, report)
    elif args.model == "seedance":
        words = len(re.findall(r"[A-Za-z0-9']+|[\u4e00-\u9fff]", text))
        if words > 120:
            report("WARN", "seedance-length", "词/字数约 %d，超出 Seedance 推荐的 15-40 词量级，压 Formula 精简" % words)
        else:
            report("PASS", "seedance-length", "词/字数约 %d，在简洁区间内" % words)

    for status, cid, msg in results:
        print("[%-4s] %-16s %s" % (status, cid, msg))
    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    print("=== %d pass, %d warn, %d fail ===" % (len(results) - len(fails) - len(warns), len(warns), len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
