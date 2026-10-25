# 发布到 GitHub

官方公开仓库为 [wdnmdq1/SkillPort](https://github.com/wdnmdq1/SkillPort)，于 2026-10-25 确定发布。代码与示例使用 MIT。保留预览版的实际验收边界，公开发行不代表三端客户端均已验证。

## 首次发布

1. 检查 README 与 COMPATIBILITY 仍准确，不把未测客户端标为 verified。
2. 运行单元测试及 `python tools/check_submission.py . --online`。
3. 将 pyproject.toml、src/skillport/__init__.py、examples/pack-*.json 的版本保持一致；当前为 0.1.0。
4. 推送 `v0.1.0` 标签，触发 Windows 发布工作流。
5. 工作流从实际 github.repository 和 github.sha 生成固定来源，构建独立 exe、四个数据包、社区索引、发布元数据和 SHA256SUMS，并附到 GitHub Release。

发布之前，本地 `python tools/build_release.py --output dist` 生成的 INSTALL.md 明确说明没有在线地址。正式构建使用：

```powershell
python tools/build_release.py --output dist --repository wdnmdq1/SkillPort --commit $(git rev-parse HEAD)
```

`dist` 必须为空。发布工作流先运行单元测试，再构建并用生成的 exe 执行 inspect 和隔离安装。GitHub Release 是发布动作，应由有权限的维护者推送标签启动。

## 依赖与可重复性

运行时依赖只有 PyYAML；Windows exe 包含运行时。构建依赖在 requirements-build.txt 固定版本。ZIP 使用固定排序、时间戳和文件属性，同一输入的包可重现。exe 不声称逐字节可重现，发布后以实际生成的 SHA256 为准。

本地构建和 CI 构建可以使用不同 Python 次版本；请记录构建版本。首版程序未签名，可能触发系统或安全软件提示；不要要求用户关闭安全软件。

## 社区目录

正式工具内配置 `https://github.com/<实际仓库>/releases/latest/download/index.json`。每次发布合并源码中的社区目录和本次官方包，归档 URL 固定版本、源码固定 commit、内容固定 SHA256。

目录为空时搜索应返回空列表，不能伪造结果。发布后的在线下载、第三方 PR 和真实客户端调用需另行验收；本地模拟传输不算线上链路通过。
