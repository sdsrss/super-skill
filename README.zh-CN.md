<!-- SEO: Claude Code Agent Skills 包管理器 — 为 ~/.claude/skills 与 ~/.agents/skills (Codex) 提供版本管理、回滚、来源追溯、完整性校验。 -->

# super-skill

**为你的 Claude Code 与 Codex Agent Skills 提供版本管理、回滚与来源追溯。**
super-skill 是一个 git 支撑的技能包管理器,管理 `~/.claude/skills`(以及 Codex 的
`~/.agents/skills`)里的技能:把每个技能纳入版本历史、告诉你它从哪来、一条命令回滚任一技能、
校验注册表是否被篡改——并内置脱敏的会话捕获与安全门控的晋级流程。

[English](README.md) · **简体中文**

---

## 为什么需要 super-skill

Agent Skill 本质只是目录里的 Markdown 文件。那个目录没有历史:改了 `SKILL.md`,上一版就没了;
你无法知道某个技能从哪来、为何在此、是否被悄悄改过——也没有撤销。

super-skill 把技能当作软件包对待:**可版本化、可审计、可回滚。**

## 亮点

- **一条命令回滚**——技能退化了?`super-skill rollback <id>` 切回上一版并重新落地到技能目录。
- **来源与审计**——`super-skill explain <id>` 用不可变审计链回答*这个技能为何存在、从哪来、怎么撤销*。
- **篡改检测**——`super-skill doctor` 用晋级时记录的哈希重新校验每个存储版本;`--fix` 从 git 恢复可恢复的版本。
- **落盘前脱敏**——会话捕获在*写入之前*剥离密钥与私有路径;密钥值永不进入日志。
- **安全门控晋级**——候选须过两道硬门(指令层对抗扫描 + 确定性 eval-lite)才能成为技能。
- **随 Agent 而行**——一个 Claude Code 插件、一个 Codex 安装包、一个 host-agnostic CLI,同一条 `super-skill` 命令驱动。

## 安装

### Claude Code(插件)

```
/plugin marketplace add sdsrss/super-skill
/plugin install super-skill
```

提供斜杠命令(`/super-skill:status`、`:mine`、`:doctor`、`:candidates`、`:seed`)、
一个在你要求版本化/解释/回滚技能时 Claude 会调用的 `super-skill` 技能,以及捕获 hooks。
插件驱动 CLI,故也需安装 CLI:

### CLI

```bash
uv tool install super-skill-cli      # 或: pipx install super-skill-cli
super-skill status                   # 命令就是 super-skill
```

PyPI 分发名为 **`super-skill-cli`**(裸名 `super-skill` 被一个无关包占用),安装后的命令仍是
`super-skill`。免安装单次运行:`uvx --from super-skill-cli super-skill status`。

### Codex

Codex 直接读取 `~/.agents/skills` 里的开放标准 `SKILL.md`,无需 marketplace:

```bash
pipx install super-skill-cli
codex/install.sh                     # 把元技能装进 ~/.agents/skills
```

用 `SUPER_SKILL_HOST_SKILLS=~/.agents/skills` 让 CLI 指向 Codex 目录。详见
[`codex/README.md`](codex/README.md)。

## 功能

| 命令 | 作用 |
|---|---|
| `seed` | 把现有 `~/.claude/skills` 纳入版本管理——对宿主只读,按内容哈希幂等。 |
| `status` / `list` | 注册表概览(技能、版本、事件、候选)与技能列表。 |
| `show <id>` | 某技能的 frontmatter、版本历史与内容哈希。 |
| `explain <id>` | 来源链 + 审计记录 + 精确回滚命令。 |
| `rollback <id> [--to vN]` | 切换活动版本并重新落地到宿主。 |
| `doctor` / `doctor --fix` | 完整性校验(哈希、活动指针、宿主同步);`--fix` 从 git 恢复版本、重落地漂移,再复验。 |
| `capture` | 把一条宿主事件追加进脱敏 WAL——从 stdin 读 hook JSON,绝不让会话失败。 |
| `mine` | 挖掘跨 ≥3 个去重会话复现的任务家族;攒够新会话时提醒你挖掘。 |
| `candidate draft/show/approve/reject` | 把挖掘到的家族变成技能:草拟 → 评审 → 两道硬门 → 晋级并落地。 |
| `hooks-config` | 打印接线会话捕获的 `settings.json` hooks 块。 |

状态存于 `~/.super-skill/`——一个真正的 git 仓库,所以**审计与回滚就是 git。**

## 差异对比

|  | 裸 `~/.claude/skills` | super-skill |
|---|:---:|:---:|
| 每个技能的版本历史 | ✗ | ✓(git DAG) |
| 一条命令回滚 | ✗ | ✓ |
| 来源追溯 / "为何在此" | ✗ | ✓ |
| 篡改 / 漂移检测 | ✗ | ✓(`doctor`) |
| 捕获时密钥脱敏 | ✗ | ✓(落盘前) |
| 安全门控晋级 | ✗ | ✓(两道硬门) |
| 同时支持 Claude Code 与 Codex | 手动 | ✓ 一个 CLI |

super-skill 是**包管理器,不是技能生成器**:它管理、版本化、审计你已有或已批准的技能——不会替你
写技能,也不会背着你改技能行为。每条写入路径都显式且可逆;你的技能目录仅在 `approve`、`rollback`、
`doctor --fix` 时被写入(`seed` 只读取、从不修改它)。

## 使用

```bash
# 把当前技能纳入版本管理
super-skill seed
super-skill status

# 查看某技能的来源与撤销方式
super-skill explain my-skill

# 撤销一次错误改动
super-skill rollback my-skill

# 检查是否被篡改;修复可恢复的漂移
super-skill doctor
super-skill doctor --fix

# 把重复劳动变成技能(需先接线捕获——见 hooks-config)
super-skill mine
super-skill candidate draft
super-skill candidate show <id>      # 编辑草稿,然后:
super-skill candidate approve <id>
```

## 配置

| 环境变量 | 默认 | 用途 |
|---|---|---|
| `SUPER_SKILL_HOME` | `~/.super-skill` | 注册表 + 控制状态(git 仓库)。 |
| `SUPER_SKILL_HOST_SKILLS` | `~/.claude/skills` | 要 seed/落地的技能目录(Codex 设为 `~/.agents/skills`)。 |
| `SUPER_SKILL_MINE_REMINDER` | `3` | `status` 提醒挖掘前的去重未挖掘会话数阈值。 |

## 范围

super-skill 刻意停在**包管理器**形态(里程碑 M0 + WS)。自学习闭环——自动优化、蒸馏、晋级技能
(里程碑 M1–M5)——是**暂缓的研究轨道**:对真实使用的测量未达到能证明其价值的阈值,故 v1 定格为
带审计与回滚的包管理器。它不会自动进化你的技能,本文也不暗示它会。

## 常见问题

**super-skill 会运行或改变我技能的行为吗?**
不会。它管理文件(版本、审计、回滚、完整性),从不擅自编辑技能内容。批准候选晋级的是*你*评审过的草稿。

**它会不打招呼就动 `~/.claude/skills` 吗?**
三条命令会写:`approve`(晋级已评审候选)、`rollback`、`doctor --fix`。`seed` 只把技能读入注册表、
从不修改它们;`status`/`list`/`show`/`explain`/`doctor` 均为只读。

**捕获的会话里我的密钥安全吗?**
脱敏在*任何写入之前*运行:密钥值与私有路径永不进日志。捕获默认关闭,需你接线(`super-skill hooks-config`)。

**插件必须依赖 PyPI 才能用吗?**
插件调用 PATH 上的 `super-skill` CLI。从 PyPI 安装:
`uv tool install super-skill-cli`(或 `pipx install super-skill-cli`)。

**支持 Codex 吗?**
支持——同一个 CLI 加一个面向 `~/.agents/skills` 的 `codex/` 安装包。CLI *内部的* Codex Target
Adapter 是后续项;把技能分发给 Codex 无需额外步骤,因为它们本就在 `~/.agents/skills`。

## 开发

使用 [uv](https://docs.astral.sh/uv/),Python 3.12。

```bash
uv sync                       # 虚拟环境 + 依赖
uv run pytest                 # 测试
uv run ruff check .           # lint
uv run mypy super_skill/      # 类型检查
```

## 许可证

[MIT](LICENSE) © sdsrss
