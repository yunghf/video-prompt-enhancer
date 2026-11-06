# video-prompt-enhancer

一份符合 [Agent Skills 开放标准](https://agentskills.io/specification) 的可移植技能包：把一句创意增强为可直接投喂目标模型的结构化视频提示词，并交付 `prompt.txt` + `meta.md`。

- **支持模型**：MiniMax H3 / Seedance 1.0 / Wan 3.0 / 可灵 3.0 / LibTV
- **依赖**：Python 3.8+（仅标准库）；无网络访问、无第三方包、无宿主专有 API

## 安装

克隆或下载后，把**整个** `video-prompt-enhancer/` 目录放进 agent 会扫描的 skills 目录。不要只复制 `SKILL.md`——模型规范、验收清单和校验脚本都在子目录里。目录名必须与 frontmatter 的 `name` 一致，请保持 `video-prompt-enhancer` 不要改名。

直接克隆到技能目录即可（以 Claude Code 用户级为例）：

```bash
git clone https://github.com/yunghf/video-prompt-enhancer.git ~/.claude/skills/video-prompt-enhancer
```

| Agent | 用户级（全局） | 项目级 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex CLI | `~/.agents/skills/` | `.agents/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| Windsurf | `~/.codeium/windsurf/skills/` | `.windsurf/skills/` |
| GitHub Copilot | — | `.github/skills/` |
| WorkBuddy | `~/.workbuddy/skills/` | 项目 `.workbuddy/skills/` |

> 各客户端版本可能调整扫描路径，以对应产品文档为准。安装后**重开一个会话**，让 agent 重新发现技能。

以 Codex CLI 用户级为例：

```bash
mkdir -p ~/.agents/skills
cp -R video-prompt-enhancer ~/.agents/skills/
```

## 目录结构

```
video-prompt-enhancer/
├── SKILL.md                          # 标准 frontmatter + 宿主无关的主指令
├── README.md                         # 本文件（给人类维护者）
├── models/                           # 五个模型各一份适配规范，按需只读一份
│   ├── minimax-h3.md
│   ├── seedance.md
│   ├── wan3.md
│   ├── kling3.md
│   └── libtv.md
├── references/
│   ├── enhancement-dimensions.md     # 八维度展开方法论与正反例
│   └── acceptance-checklist.md       # 五类验收清单、变更记录模板、最小测试集
├── scripts/
│   └── validate_video_prompt.py      # 确定性校验，仅用 Python 标准库
└── examples/                         # 冒烟测试样例
    ├── seedance-pass.txt
    ├── kling3-pass.txt
    └── libtv-fail.txt
```

## 验证安装

在技能目录内执行（或把下面路径换成你的实际安装路径）：

```bash
SKILL_DIR="$(pwd)"
python3 "$SKILL_DIR/scripts/validate_video_prompt.py" "$SKILL_DIR/examples/seedance-pass.txt" --model seedance --duration 5 --ratio 16:9
python3 "$SKILL_DIR/scripts/validate_video_prompt.py" "$SKILL_DIR/examples/kling3-pass.txt"   --model kling3   --duration 10
python3 "$SKILL_DIR/scripts/validate_video_prompt.py" "$SKILL_DIR/examples/libtv-fail.txt"    --model libtv    --duration 8 --ratio 16:9
```

前两条应退出码 `0`（PASS），第三条应退出码 `1`（FAIL：检出点名负面词）。若三条都符合预期，说明脚本与 UTF-8 中文处理正常。

## 怎么用

在会话里提到「视频提示词 / 提示词增强 / 文生视频 / 图生视频」，或直接点名 MiniMax H3、Seedance、通义万相、可灵、LibTV，agent 会激活本技能。流程是：

1. **先确认目标模型**（硬前置；自动化调用方可在请求里直接给模型名跳过询问）
2. 八维度展开 → 按模型格式适配 → 运行校验
3. 交付 `<主题>-<模型>-prompt.txt`（纯提示词）与 `<主题>-<模型>-meta.md`（维度表、参数、校验摘要、变更记录）

成果文件默认写到当前工作目录，**不会**写进技能安装目录。若宿主没有命令执行能力，技能会降级为人工核对验收清单，并在 meta 中注明。

## 相对原版的改造

| 项 | 改动 |
|---|---|
| Frontmatter | 收敛为标准字段 `name` / `description` / `compatibility` / `metadata`；`description` 改为中英双语单行，含跨语言触发词；版本等移入 `metadata` |
| 宿主绑定 | 移除原 Step 4 中的 `~/.workbuddy/skills/...` 硬编码，改为通用的 `SKILL_DIR` 表述 |
| 路径基准 | 新增「运行环境约定」：明确所有相对路径以 SKILL.md 所在目录为基准；Step 3 命令改用 `SKILL_DIR` 绝对路径 + `python3` |
| 可移植性 | 新增无 shell 时的降级方案、自动化调用方跳过交互询问的约定、不依赖任何宿主专有 API |
| 安装元数据 | 排除 `_skillhub_meta.json`（WorkBuddy 市场安装记录，其它 agent 用不到） |
| 新增 | `README.md`、`examples/` 三个冒烟样例、SKILL.md 的「安装后自测」章节 |
| **未改动** | `models/*.md`、`references/*.md`、`scripts/validate_video_prompt.py` 逐字节复制，内容与行为不变 |

标准版 frontmatter 不再含 `display_name`，因此在 WorkBuddy 界面里可能显示为 `video-prompt-enhancer` 而非中文名；功能不受影响。

## 授权与使用边界

本仓库**公开可见，但未授予开源许可**。按 GitHub 默认规则，未附 `LICENSE` 即保留所有权利：他人可以浏览与 fork，但复制、修改、再分发或商用需取得版权人许可。

## 兼容性事实

- `scripts/validate_video_prompt.py` 仅使用 `argparse` / `re` / `sys`，Python 3.8+ 可直接运行，Windows / macOS / Linux 通用，UTF-8 读写。
- 技能不调用宿主专有 API、不访问网络、不硬编码输出路径，也不写入自身安装目录。
- 校验为启发式检查（含 WARN 项），语义约束仍需按 `references/acceptance-checklist.md` 人工补齐。
