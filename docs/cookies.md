# 中文 | [English](cookies-en.md)

# 登录态 URL 媒体的 Cookies 使用说明

有些视频页面只有在浏览器正常登录后才会暴露可播放媒体。FlowScribe 为这类情况提供显式的 `--cookies` 选项。

它会把 Netscape 格式的 `cookies.txt` 文件传给 `yt-dlp`，然后继续走正常的媒体准备和转录流程。

FlowScribe 不会替你采集、生成或保存 cookies。你需要对每条命令显式选择要使用的文件。

## 什么时候需要 Cookies

当公开 URL 因为登录态、年龄确认、地区确认或类似访问状态而失败时，再考虑使用 cookies：

```powershell
flowscribe inspect "https://example.com/watch/123" --cookies "D:\private\cookies.txt"
flowscribe url "https://example.com/watch/123" --cookies "D:\private\cookies.txt" -o outputs --format txt,md,json
```

如果某个站点在匿名状态下就能正常访问，就不要额外传 cookies。

## Cookies 文件格式

建议使用 Netscape `cookies.txt` 格式，这也是 `yt-dlp` 直接支持的格式。

浏览器的 cookies 导出工具一般都能导出这种格式。

## 安全规则

- 不要把 cookies 文件提交到 Git
- 不要把 cookies 内容贴到 issue、日志、截图或 prompt 里
- 尽量把 cookies 放在仓库之外
- 如果站点提示登录过期，及时刷新或删除该文件
- cookies 不能绕过 DRM、付费访问或平台规则

FlowScribe 的 `.gitignore` 已经屏蔽了一些常见 cookies 路径，例如：

```text
cookies.txt
*.cookies.txt
/cookies/
/.cookies/
```

但这不代表你可以不看 `git status`。

## 错误提示

当 URL 检查或下载失败时，FlowScribe 可能提示：

```text
retry with --cookies path\to\cookies.txt
```

这表示匿名访问没有拿到可用媒体，不代表 cookies 一定能解决问题。源站仍可能是未支持、受保护、被 DRM 限制，或受网络/代理问题影响。

## 推荐流程

1. 先用 `inspect` 检查：

   ```powershell
   flowscribe inspect "https://example.com/watch/123" --cookies "D:\private\cookies.txt"
   ```

2. 如果检查结果显示存在可用音频或合并媒体，再正式转录：

   ```powershell
   flowscribe url "https://example.com/watch/123" --cookies "D:\private\cookies.txt" -o outputs --preset zh --format txt,md,json
   ```

3. 如果仍然失败，再考虑更新 `yt-dlp`、刷新 cookies 文件，或更换你有合法直接访问权的来源。
