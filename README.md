# SkillPort

**把技能打包、拖进 Agent，再说一句“安装这个包”。**

SkillPort 是建立在 [Agent Skills](https://agentskills.io/specification) 之上的技能包与社区分发项目：保留 `SKILL.md`，补充单技能/合集打包、完整性检查、按宿主安装、GitHub 社区目录与发布流程。

> **0.1.0 公开预览。** 官方仓库为 [wdnmdq1/SkillPort](https://github.com/wdnmdq1/SkillPort)，发行文件见 [Releases](https://github.com/wdnmdq1/SkillPort/releases)。工具与自动化检查已完成；Claude Code、Codex、Hermes 的真实拖拽及新会话调用尚未全部验收。第三方社区条目尚待收录；不要把这个项目宣传为已验证的“三端一拖安装”。

## 给使用者

使用官方发行包：下载一个技能 ZIP → 拖入当前 Agent → 发送“安装这个包”。Agent 读取 `INSTALL.md`，获取固定版本的官方安装工具，检查并安装；首次同时装入技能管家。必要权限由宿主处理。

本地预发布：使用同批提供的 `skillport.exe` 和技能 ZIP。Agent 需要能读取本地 ZIP，并能调用同目录的工具；若 ZIP 附件不可读，该客户端的拖拽验收仍为未通过，提供本地路径仅是备用方式。

安装目标仅限本地 Windows x64：

| Agent | 用户级目录 | 当前状态 |
| --- | --- | --- |
| Claude Code | `~/.claude/skills` | 目录适配已测；客户端未验收 |
| Codex | `~/.agents/skills` | 目录适配已测；客户端未验收 |
| Hermes 默认配置 | `~/.hermes/skills` | 目录适配已测；客户端未验收 |

同名同内容跳过；同名不同内容保留原文件并报冲突。技能依赖不会自动安装或配置。文件写入成功不等于 Agent 已识别。

## 给作者

复制 `templates/author`，让你的 Agent 按自己的任务改写 `hello-skill/SKILL.md`，并同步修改目录名和 `pack.json`。保留完整脚本、素材及参考文件，注明许可证和外部依赖。

```powershell
.\skillport.exe pack .\templates\author\pack.json --output .\hello-skill.zip
.\skillport.exe inspect .\hello-skill.zip
```

打包会排除常见凭据文件与缓存，并返回省略清单；作者仍需检查其他文件内是否含有私密信息。社区包没有自己的可执行安装器，也不允许覆盖内置 `skillport` 管家。

向 GitHub 社区提交 PR，添加固定版本的技能包链接和完整来源信息；维护者审核后收录。详见 [贡献指南](CONTRIBUTING.md) 和 [包规范](docs/SPEC.md)。

## 工具接口

所有命令返回 JSON；成功退出 0，部分安装失败/冲突退出 1，输入、下载或校验失败退出 2。

```powershell
.\skillport.exe inspect .\skillport-starter-0.1.0.zip
.\skillport.exe install .\skillport-starter-0.1.0.zip --agent codex
.\skillport.exe list --agent codex
.\skillport.exe search 摘要
.\skillport.exe get skillport/brief --package-version 0.1.0 --agent codex
```

目标为 `claude-code`、`codex`、`hermes`。只有存在唯一可信宿主环境标记时才自动选择；否则明确指定，不能根据已有目录猜测。`--home` 仅用于隔离的开发测试，不是让普通用户选择安装目录的入口。源码开发版和未绑定仓库的本地构建在 search/get 时必须显式提供 `--registry <目录文件或GitHub地址>`；官方发行工具内置公开目录地址。

## 开发与发布

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python tools/check_submission.py .
python -m pip install -r requirements-build.txt
python tools/build_release.py --output dist
```

开发需要 Python 3.12+；Windows 独立程序不要求用户装 Python。正式发布流程会配置真实仓库地址，打包固定版本的工具、管家包、两个示例包、合集、索引和 SHA256SUMS。详见 [发布说明](docs/RELEASE.md)。

[自动检查结果](docs/VALIDATION.md) · [客户端测试步骤](docs/COMPATIBILITY.md) · [安全边界](SECURITY.md)

代码与自带示例：MIT。社区技能保持各自许可证。

