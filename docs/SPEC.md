# SkillPort Package Format 1

## 定位与包布局

这是分发层规范，不替代 [Agent Skills](https://agentskills.io/specification)。v1 只发行本地 Windows x64 包。

```text
example.zip
├── INSTALL.md
├── manifest.json
└── skills/
    └── hello-skill/
        ├── SKILL.md
        ├── scripts/
        ├── references/
        └── assets/
```

根文件仅允许 INSTALL.md、manifest.json，以及清单列出的技能文件。普通目录项允许存在，但不会被安装。管家由可信安装工具提供；社区不能提供名为 skillport 的技能。`skills: []` 表示仅安装内置管家的引导包。

## 清单接口

```json
{
  "format": "skillport/1",
  "id": "author/hello",
  "version": "0.1.0",
  "license": "MIT",
  "platforms": ["windows-x64"],
  "agents": ["claude-code", "codex", "hermes"],
  "skills": [{
    "name": "hello-skill",
    "path": "skills/hello-skill",
    "license": "MIT",
    "dependencies": [],
    "files": {
      "SKILL.md": "这里由打包工具生成该文件的64位小写SHA256"
    }
  }]
}
```

上面的摘要说明文字不是合法摘要；实际包由 `pack` 生成，不手写占位摘要。包标识为两个小写连字符 slug 组成的 namespace/name。版本为 major.minor.patch，可带小写预发布后缀。技能名与目录名一致，1–64 个小写字母、数字或连字符，不允许开头、结尾、连续连字符。manifest 中的 agents 只是作者声明。

每个技能的 files 精确列举所有相对文件路径和原始字节 SHA256；不进行换行转换。文件集合必须完全一致，校验失败整包拒绝。dependencies 是需要用户另行配置的外部软件、MCP、账号或服务的文字声明，不是自动执行的安装指令。

SKILL.md 使用安全 YAML frontmatter，至少有 name 与 description。description 为 1–1024 字符。metadata 如存在，必须是字符串键值。YAML 重复字段、自定义标签、锚点及别名拒绝，避免歧义与资源滥用。支持常见 Markdown 内联相对文件链接检查；动态拼接路径、引用式 Markdown 链接与运行时依赖仍需人工核对。

## 作者输入

`pack <config.json> --output <新ZIP>` 接受 id、version、license、agents，以及 skills 列表。每项 path 是相对配置文件的技能目录，另有 license、dependencies。不能引用配置目录之外的位置。工具会生成完整清单和安装引导。

相同输入产生相同 ZIP 字节；写入新文件，不覆盖已有产物。打包结果返回 omitted 清单。作者必须保留第三方许可证；包级许可证不能替代文件原有许可。

## 文件边界与安装行为

- ZIP 最大 25 MiB；最多 2048 项；单文件最大 10 MiB；解压后总计最大 100 MiB。超过 1 MiB 且压缩比大于 200 的文件拒绝。
- 相对路径使用 `/`，最多 220 字符；拒绝绝对路径、上级跳转、反斜杠、空段、控制字符、Windows 设备名、ADS、末尾空格/点，以及大小写或 Unicode 归一化后的重复路径。
- 拒绝符号链接、重解析点、特殊文件、加密 ZIP、重复条目、文件/目录冲突。读取 ZIP 校验 CRC，不调用 extractall。
- 排除常见凭据文件、私钥后缀、版本库和运行缓存。这个规则无法识别任意文件内的所有秘密，不构成泄密保证。
- 先验证整包，再逐技能暂存到目标目录同一磁盘，使用重命名提交。已有同名技能只做内容比较；有任何差异不覆盖、不合并。一个技能失败不妨碍合集其他技能。
- 安装不执行技能里的脚本、不配置 MCP、不触碰 Agent 配置文件、不自动获取依赖。

结果包含 files、host_recognized、dependencies。工具只能证明文件安装，host_recognized 保持 unverified；客户端新会话实际调用属于单独验收证据。

## 社区索引接口

`format: skillport-registry/1`，packages 中每项记录 id、version、description、author、license，以及：

- source：公开 repository 和完整 40 位 commit。
- archive：固定 GitHub Release ZIP 的 url 和 64 位 SHA256。
- compatibility：以 Agent 名为键，status 为 declared、not-tested、failed、verified。
- verified/failed 必须附 client_version、date、report；报告链接必须在 GitHub。验证必须说明系统、版本、入口、实际调用和证据。

索引可以更新，但每个条目的版本、来源和摘要必须锁定。安装按精确版本匹配，不自行猜“最新”。下载只允许 HTTPS GitHub 及其发行 CDN，限制大小并保留 TLS 校验。搜索不执行技能内容。
