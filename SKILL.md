---
name: video-prompt-enhancer
description: "Expands a one-line idea into a validated, model-specific video prompt delivered as files (prompt.txt + meta.md). Asks for the target model first, enhances eight dimensions (subject, action, atmosphere, camera, lighting, style, ratio, duration), adapts to the native format and parameter limits, then validates. Supports MiniMax H3, Seedance 1.0, Wan 3.0, Kling 3.0/Omni and LibTV. Use for video prompts, prompt enhancement, text-to-video or image-to-video, or when those models are mentioned. 中文触发：视频提示词、提示词增强、提示词优化、文生视频、图生视频、通义万相、可灵、LibTV。"
compatibility: "Requires Python 3.8+ (standard library only) to run the bundled validator; no network access or third-party packages. If the host cannot execute shell commands, skip Step 3 script validation and use references/acceptance-checklist.md instead."
metadata:
  version: "2.1.1"
  origin: "Adapted to the Agent Skills open standard (agentskills.io/specification)"
  canonical-models: "h3, seedance, wan3, kling3, libtv"
  language: "zh-CN"
---

# 视频提示词增强器 / Video Prompt Enhancer

## 定位

用户给的往往只有一句创意（"一只猫在屋顶看日落"）。本系统把它增强为含八维度信息的结构化提示词，按目标模型的格式规范与参数边界输出，并**落成成果文件**交付。五个模型、同一套方法论：**先问模型 → 八维度展开 → 模型适配 → 校验 → 成果文件**。

## 运行环境约定（宿主无关）

本技能遵循 Agent Skills 开放标准（agentskills.io/specification），不依赖任何特定 AI 宿主或专有 API。

1. **路径基准**：下文所有相对路径（`models/`、`references/`、`scripts/`、`examples/`）都相对于**本 SKILL.md 所在目录**，记作 `SKILL_DIR`。不要假设进程当前工作目录就是技能目录。
2. **所需能力**：读文件、写文件、执行一条本地命令。宿主用何种工具名实现（Read/Write/Bash、file_read/shell 等）均可。
3. **无命令执行能力时**：跳过 Step 3 的脚本校验，改为逐项核对 `references/acceptance-checklist.md`，并在 meta.md 注明"未运行机器校验，采用人工清单"。其余步骤要求不变。
4. **自动化调用**：Step 0 要求确认目标模型。若调用方是 API、流水线或另一个 agent，只要在请求或配置中给出模型名即视为已确认，直接进入 Step 1，不必等待交互回复。

## 支持模型与适配要点

| 模型 | 格式特征 | 时长 | 比例 | 详细规范 |
|---|---|---|---|---|
| MiniMax H3 | 具名字段文档：Base 三字段 / Ref2VA 六段 + 首尾帧对齐指令 | 4–15s 整数秒 | 由对齐行约束 | `models/minimax-h3.md` |
| Seedance 1.0（火山方舟） | 自然语言公式 `[主体]+[环境]+[风格]+[运镜]+[光照]+[情绪]`，多动作按时序，参数以 `--rt/--dur/--rs` 或 JSON 字段给出 | 5 / 10s | 16:9 / 9:16 / 1:1 / 4:3 / 3:4 / 21:9 | `models/seedance.md` |
| Wan 3.0（通义万相） | 长文本分镜格式，每镜 4–6s 带时间戳，原生音频（台词/BGM/音效）写进提示词 | 2–30s 或 -1 智能时长 | 16:9 / 4:3 / 1:1 / 3:4 / 9:16 | `models/wan3.md` |
| 可灵 3.0 / 3.0 Omni | 固定多镜头格式 `镜头 n, m, words;`（n 序号、m 秒数），`@素材` 引用，旁白内联 | 3–15s 自由控制 | 16:9 / 9:16 / 1:1 等 | `models/kling3.md` |
| LibTV | 节点工作流提示词，`{{Image N}}` 引用上游节点，质感词锁死，正面穷举（不写负面词） | 4–15s（8s 生产默认） | 16:9 为主 | `models/libtv.md` |

## 工作流

### Step 0：询问/确认目标模型（硬前置）

技能启动后的**第一件事**：向用户（或调用方）确认要为哪个模型创建提示词，给出五选一：

1. MiniMax H3
2. Seedance 1.0（火山方舟）
3. Wan 3.0（通义万相）
4. 可灵 3.0 / 3.0 Omni
5. LibTV

- 用户或调用方已在请求/配置中明确指定模型 → 跳过本步直接进入 Step 1。
- 用户表示不确定 → 给一句选型建议让用户确认：短视频信息流→Seedance/可灵；叙事长镜头→Wan 3.0；精确首尾帧/素材编辑→H3；节点化批量工作流→LibTV。
- **未得到模型答案前，不展开八维度、不写任何提示词内容。**

### Step 1：八维度展开

无论目标模型是什么，先把用户的一句话创意展开成八维度素材表（主体 / 动作 / 氛围 / 运镜 / 光影 / 风格 / 比例 / 时长）。展开质量标准、每维度的提法与反面案例见 `references/enhancement-dimensions.md`。**先展开、后裁剪**：按模型边界扔掉该模型不支持的维度（如 H3 的比例由对齐行与素材决定，不需要比例词）。用户未给比例/时长时取该模型默认值，并在成果 meta 中注明假设。

### Step 2：按目标模型适配

读取 `models/<model>.md`（以 `SKILL_DIR` 为基准；处理哪个模型只读那一份），将八维度素材翻译成该模型的格式：

- 字段顺序、分隔符、时间戳写法、引用语法严格遵循该模型规范。
- 时长/比例只取模型合法值；不确定时用规范文档中标注的默认值并在交付说明中注明。
- 模型特有红线见规范文件各节的"高频违规"（如 LibTV 负面词反召唤、Seedance 忌缩写、可灵分镜时长之和必须等于总时长）。

### Step 3：运行校验

```bash
python3 "$SKILL_DIR/scripts/validate_video_prompt.py" <prompt-file> --model <h3|seedance|wan3|kling3|libtv> [--duration SS] [--ratio R]
```

把 `SKILL_DIR` 替换为本技能目录的绝对路径。脚本仅依赖 Python 3.8+ 标准库，UTF-8 读写，无网络与第三方依赖；退出码 `0` = 通过 / `1` = 存在 FAIL / `2` = 用法或读文件错误。

机器可判部分（形状、时长/比例合法性、时间轴递增与越界、多镜头时长和、引用标签一致性、八维度覆盖启发式）全部进脚本；语义部分（约束保持、边界合理性）用 `references/acceptance-checklist.md` 的清单人工补齐。校验 FAIL 项必须先修复再进入 Step 4。宿主无法执行命令时按"运行环境约定"第 3 条降级。

### Step 4：产出成果文件

在校验通过后（或仅剩 WARN），把成果落成文件交付：

- **`<主题关键词>-<模型名>-prompt.txt`**：最终提示词本体，内容为可直接投喂目标模型的纯文本，不加任何元信息注释。
- **`<主题关键词>-<模型名>-meta.md`**：八维度展开表、所选模型与参数（时长/比例及来源：用户指定或默认假设）、校验脚本输出摘要、本轮变更记录（含锁定约束）。
- 保存位置默认取当前工作目录；调用方指定路径时从其指定。**禁止把成果文件写进技能安装目录**（即 `SKILL_DIR` 及其子目录）——那会污染技能包本身。文件命名中的模型名用 canonical 名（h3 / seedance / wan3 / kling3 / libtv）。

### Step 5：记录变更，支持回滚

每轮改动记录在 meta.md 的变更记录区：改了哪个维度/字段、为什么、预期影响哪个验收项、哪些锁定约束未动。多轮之间比较维度变化而非整段文案。变更记录模板与最小测试集方法见 `references/acceptance-checklist.md`。

## 关键红线（全模型通用）

- **未问模型不动笔**：必须先询问/确认目标模型，禁止在未知模型的情况下直接产出提示词。
- 参数边界优先：时长、比例、分辨率只取目标模型文档中的合法值，不臆造中间值。
- 一个镜头一个主动作：单镜头内堆多个不相关运动会稀释模型注意力。
- 主体称呼全篇一致：同一主体不换别名（"橘猫/小猫/它"混用会产生竞争语义）。
- 模型特有格式不可混用：H3 的字段文档、可灵的 `镜头 n, m, words;`、Wan 3.0 的时间戳分镜、LibTV 的 `{{Image N}}` 互不通用。
- 成果文件必须落地：提示词本体存 .txt（纯文本可投喂），元信息存 meta.md，不只在对话里贴一段文字。

## 安装后自测

用 `examples/` 下三个样例确认脚本可用（路径同样以 `SKILL_DIR` 为基准）：

```bash
python3 "$SKILL_DIR/scripts/validate_video_prompt.py" "$SKILL_DIR/examples/seedance-pass.txt" --model seedance --duration 5 --ratio 16:9    # 期望退出码 0
python3 "$SKILL_DIR/scripts/validate_video_prompt.py" "$SKILL_DIR/examples/kling3-pass.txt"   --model kling3   --duration 10               # 期望退出码 0
python3 "$SKILL_DIR/scripts/validate_video_prompt.py" "$SKILL_DIR/examples/libtv-fail.txt"    --model libtv    --duration 8 --ratio 16:9   # 期望退出码 1
```

第三个样例故意含点名负面词，用于确认脚本确实会拦截，退出码 1 属预期。

## Resources

### references/enhancement-dimensions.md
八维度展开方法论：每维度的提法、质量标准、正反例；"先展开后裁剪"原则；面向短视频/产品/角色叙事的维度侧重。

### models/*.md
五个模型各一份适配规范：格式骨架、参数表、示例、高频违规。处理对应模型时只读那一份。

### references/acceptance-checklist.md
五类验收清单（形状/参数/时间轴/边界/约束保持）+ 每轮变更记录模板 + 最小测试集构建法。

### scripts/validate_video_prompt.py
确定性校验：解析模式与字段形状、八维度覆盖、时长/比例合法性（按模型参数表）、切点时间轴、可灵多镜头时长和、H3 对齐行与标签一致性。退出码 0 通过 / 1 存在问题 / 2 用法或读文件错误。

### examples/*.txt
三个冒烟测试样例：两个应通过、一个应被拦截。供安装后验证脚本可独立运行。
