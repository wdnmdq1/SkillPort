# 0.1.0 本地验证结果

2026-10-24，Windows x64；构建 Python 3.14.7、PyYAML 6.0.3、PyInstaller 6.22.3。

## 已通过

- 19 项单元测试：三目标目录、单技能/合集/管家包、中文与空格路径、首次目录创建、重复安装、冲突保留、失败清理、依赖状态、UTF-8 输出、自包含开发管家、网络目录匹配、恶意路径、CRC、摘要、重解析点、重复条目、错误类型、缓存与凭据排除、确定性打包。
- 五个本地作者配置的打包与静态校验：四个官方包配置和作者模板。未执行任何技能脚本。
- GitHub Actions 文件通过 YAML 解析；尚未在线运行 Actions。
- Windows 独立程序可以启动、显示版本、inspect。子进程 PATH 只保留 Windows System32，测试不依赖系统 Python。
- 三目标分别通过独立 exe 的隔离安装、二次安装、已安装管家 exe 再运行、冲突保护。每个目标保留了完整的参考文档、素材和许可证。
- 社区搜索→固定版本下载→校验→安装的代码路径通过模拟传输测试；这不等于真实公网社区链路验收。

## 未完成

- 三个客户端的实际拖拽、必要权限交互、新会话发现与调用，仍为 not-tested；详见 COMPATIBILITY.md。
- 真实 GitHub 贡献 PR、审核、线上 Release 下载和社区搜索尚未验收；本地预发布索引为空。
- Windows 程序尚未代码签名；没有宣称安全认证。

检查完成后没有向用户原有的 Claude、Codex 或 Hermes 技能目录写入文件，没有改动原有配置与会话。

## 可重复验证

开发环境运行 `python -m unittest discover -s tests -v`、`python tools/check_submission.py .`。

Windows 独立程序运行 `python tools/smoke_release.py <发行目录> --output <发行目录>/portable-smoke.json`，分别验证三种目录。该脚本只使用临时 home；host_recognition 保持 not-tested。
