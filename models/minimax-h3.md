# H3 提示词完整规范

## 1. 两种提示词形状

H3 把提示词训练成具名字段文档，形状由素材决定：

| 素材 | 形状 | 字段数 |
|---|---|---|
| 纯文本，或只有首帧/尾帧 | Base | 3 |
| 驱动图像、视频、音频参考 | Full-reference（Ref2VA） | 6 |

字段名是结构对齐的训练锚点，不可改名、不可换序。空字段写 `N/A`。

### 模式速查

| 模式 | 含义 | 对齐指令 |
|---|---|---|
| T2VA | 从文本生成完整视听时间线 | 不需要 |
| I2VA | 一张图作精确首帧，从它向前发展 | 需要 |
| FL2VA | 连接精确首帧到精确尾帧 | 需要 |
| L2VA | 推断合理开场，最终收敛到给定尾帧 | 需要 |
| Ref2VA | 图像/视频/主体/音频作可复用内容、编辑源、续接起点、结构参考或声音关系 | Full-reference 专属结构 |

## 2. Base 三字段

固定输出恰好三个字段，顺序固定：

```
integrated_multimodal_description: [Shot 1] ...
overall_soundscape: ...
non_diegetic_music: ...
```

### 字段职责边界

| 字段 | 负责 | 不负责 |
|---|---|---|
| `integrated_multimodal_description` | 视觉、动作、镜头、说话人、对白、歌唱、画内音，全部按时间轴组织 | — |
| `overall_soundscape` | 环境声、物理动作声、非语言人声 | 对白不能放这里 |
| `non_diegetic_music` | 角色听不到、只有观众听到的配乐 | 任何画内声音 |

- `overall_soundscape` 写成一段连续的 1–4 句英文，覆盖环境、物理动作、非语言人声，不重复对白。
- 即使用户未提声音，H3 也可能原生生成音频：显式描述想要的 ambience 与 music policy，不赌运气。

## 3. 关键帧对齐指令（硬前置）

I2VA / FL2VA / L2VA 必须在三个字段**之前**放一行精确对齐指令，后跟一个空行。

### I2VA

```
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

```

### FL2VA

```
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.

```

### L2VA

```
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.

```

规则：
- `N` 替换为实际最终镜号；`S.SS` 是有效时长，必须精确到两位小数。
- `S.SS` 等于本次实际请求生成的秒数。H3 输出通常为 4–15 秒的整数秒，尾帧行上的 `S.SS` 必须与该长度对齐，否则指令在时间上矛盾。

## 4. 时间轴与镜头

`integrated_multimodal_description` 内部按镜头推进：

- `[Shot 1]` 不写时间戳，直接以视觉风格和初始构图开始。
- 后续镜头编号递增，每个镜头以严格递增的切点时间开头：

```
[Shot 2] At 00:03.500, the camera cuts to ...
[Shot 3] At 00:06.250, the shot switches to ...
```

- 只在切镜能带来新主体、空间、状态、视角或时间信息时才切；小的距离或角度变化优先用运镜解决。
- 运镜写成句子里的自然动作，不堆叠标签。官方词汇：Zoom In/Out、Push In/Pull Out、Pan、Truck、Tilt、Pedestal、Arc、Tracking、Static、Shake、POV、Roll，可配合 `with small/large amplitude`、`at slow/fast speed`；中等幅度与常速是默认值，可不写。

## 5. Ref2VA 六段

六个非空段，顺序固定：

```
subject_definitions:
summary:
retention_analysis:
detailed_description:
overall_soundscape:
non_diegetic_music:
```

### 前四段职责

- **`subject_definitions`**：定义被引用的内容及其标签。可复用的人物、动物、物体、场景、服装、道具、UI、风格、动作、表情、姿势均为 `<Subject N>`；`<Picture N>` 用于具体目标帧或镜头规划锚点；`<Video N>` 用于编辑源/续接起点/整体时间结构；`<Audio N>` 用于被复制或参考的音频信号。
- **`summary`**：概括任务类型、目标视频和主要参考关系。
- **`retention_analysis`**：记录每个被引用项出现在哪些镜头，以及状态是 `fully_preserved` / `partially_preserved` / `transferred` / `reused`。
- **`detailed_description`**：按播放顺序描述视觉、动作、镜头、声音、对白，具体到构图、主体位置、环境光照、状态变化、运镜，以及被引用内容实际出现或生效的时间点；不能退化成剧情摘要或参考关系列表。

### 标签规则

- 标签一旦分配，在全部六个段中含义保持一致。
- 高频违规：`<Picture N>` 若只用于标识另一被引用项的来源，应写在那一项定义内部，不单独占一行。
- 音频字段与 Base 同构：`overall_soundscape` 管环境与物理声，`non_diegetic_music` 管观众配乐。

## 6. 示例

### T2VA（Base，三字段）

```
integrated_multimodal_description: [Shot 1] A rainy Tokyo alley at night, neon signs reflecting off wet asphalt. The camera pushes in slowly past vending machines toward a small ramen shop. [Shot 2] At 00:04.500, the camera cuts inside the shop. A cook slides open the door and says, "Two bowls, coming up." Steam rises from the pot behind him.
overall_soundscape: Steady rain on pavement, distant traffic hum, the clack of geta sandals passing outside, and the hiss of noodles hitting broth.
non_diegetic_music: A sparse shamisen motif, low volume, serving as a quiet undercurrent under the natural street noise.
```

### FL2VA（对齐指令 + 三字段，请求 8 秒）

```
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 3) aligns with the 8.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] The exact opening composition of <Picture 1>: a red paper lantern swinging in still air above an empty stone stairway. The camera trucks right to reveal a corner of a bamboo grove. [Shot 2] At 00:02.750, wind begins to move the lantern as a figure in a straw hat climbs the first steps. [Shot 3] At 00:06.500, the camera finds the summit position matching <Picture 2>, the lantern now still again above the same stairway, the figure gone.
overall_soundscape: Wind rising through bamboo leaves, fabric rope creak of the lantern, soft footsteps on stone.
non_diegetic_music: A single sustained koto note entering at the wind gust, resolving as the lantern stills.
```

### Ref2VA（六段节选）

```
subject_definitions: <Subject 1> is the young woman shown in <Picture 1>, wearing a cream knit sweater and indigo overalls; her identity, wardrobe, and face must remain identical in every appearance. <Picture 2> is the kitchen layout of <Video 1>, referenced as the fixed room geometry. <Audio 1> is the original line delivery from <Video 1>, reused verbatim for the closing question.
summary: Re-stage the woman from <Picture 1> inside the kitchen of <Video 1>, ending on the exact final frame of <Picture 2>, reusing <Audio 1> for her closing line.
retention_analysis: <Subject 1> appears in Shot 1 through Shot 4, fully_preserved in identity and wardrobe. The geometry of <Video 1> is reused across all shots. <Audio 1> is transferred to Shot 4 only, timed to her final mouth movement.
detailed_description: [Shot 1] The woman from <Subject 1> stands at the exact left-side counter position established in <Video 1>, morning light entering from the window at frame-left, and turns toward the camera while asking the line delivered in <Audio 1>...
overall_soundscape: Refrigerator hum, kettle ticking, the soft set-down of a ceramic mug.
non_diegetic_music: None; the scene relies on room tone and the referenced vocal delivery.
```

## 7. 约束分层（编辑时用）

| 层 | 存放位置 |
|---|---|
| 身份/外观 | `<Subject N>` 定义 + `retention_analysis` |
| 时间/镜头 | `[Shot N]` + 切点时间 + 首尾帧对齐指令 |
| 声音 | `overall_soundscape`（物理/环境）与 `non_diegetic_music`（观众配乐）分离 |

某一层出问题时只改该层对应字段，避免牵动全部字段导致回归。
