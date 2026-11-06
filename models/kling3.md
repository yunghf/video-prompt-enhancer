# 可灵 3.0 / 3.0 Omni 适配规范

依据可灵 AI 官方 API 文档与《Kling VIDEO 3.0 Omni Guide》整理。覆盖文生视频、图生视频、首尾帧、Omni 多参考与多镜头能力。

## 多镜头固定格式（自定义分镜）

```
镜头 n, m, words; 镜头 n, m, words; ...
```

- `n`：分镜序号，最少 1 个、最多 6 个分镜。
- `m`：该分镜时长（秒），**每个分镜 ≥ 1 秒，所有分镜之和必须等于本次生成的总时长**（总时长 3–15 秒自由控制）。
- `words`：该分镜提示词，**最大 512 字符**。
- 用半角 `;` 与半角逗号分隔，符号不可用全角。

Omni 画布中也可使用 `Shot 1 (1s): ...` / `[00:00 - 00:02] ...` 的标注写法，等价于 API 的镜头语法，按所用产品形态选择其一。

## 参考与主体

- `@图片/主体/视频` 引用素材：`@image_1`、`@Zhang`、`@video_1`（Omni），或 `@Element1`/`@kling` 元素。
- **命名避坑**：不同主体名不能互相包含（`@Zhang` vs `@ZhangSan`）；主体名不要与正文内容雷同（`@gmail` vs 正文里的邮箱）。
- first_frame / last_frame 首尾帧图生视频；图片宽高比需在 1:2.5 ~ 2.5:1 之间。
- Omni 元素支持视频角色参考（3–8 秒视频提取外观+声线）。

## 时长与风格

- 单次生成 3–15 秒自由设定；API prompt 长度上限 3072 字符，建议 ≤ 2500。
- 官方示例的语言风格：**电影化、参数化**——先给"镜头/景别/机位/运动"，再给"色调分级/氛围"，最后叙事情节按秒推进。示例骨架：

```
Ultra-wide medium-long shot with horizontal tracking opening, low-angle stabilizer movement near the ground, high-contrast romantic cinematic color grading with cold blue night and silvery starry sky, poetic realism atmosphere; the subject is a young woman in a dark green long dress running at full speed on moonlit garden grass...; at the 4-second mark, ...; at the 8-second mark, ...; in the final 3 seconds, ...
```

## 音频

- 原生音频 + 口型同步；旁白/台词直接内联写（`with a voiceover: "..."` / 分镜内写台词引文）。
- 角色声线可绑定到主体，绑定后无需在提示词中重复。

## 高频违规

1. **分镜时长和 ≠ 总时长**：这是 API 直接报错的结构性问题。
2. **单分镜超 512 字符**：拆镜或压缩。
3. **全角标点**：`镜头 1，3，…；` 必须用半角 `,` 和 `;`。
4. **主体名包含/雷同**：见上文命名避坑。
5. **静态帧描述进 i2v**：图生视频写"发生什么"，不写首帧里已经有什么。
