# 中文 | [English](proxy-en.md)

# 代理配置

FlowScribe 在访问 URL 媒体时可以使用本地代理，例如 Clash。

当某个站点在浏览器里能通过代理正常访问，但在终端里失败时，这个能力尤其有用。

## 显式传入代理

推荐优先显式传入 `--proxy`：

```powershell
flowscribe inspect "https://www.youtube.com/watch?v=aUL-VAt0gDI" --proxy "http://127.0.0.1:7890"
flowscribe url "https://www.youtube.com/watch?v=aUL-VAt0gDI" --proxy "http://127.0.0.1:7890" -o outputs
```

常见 Clash 端口：

```text
http://127.0.0.1:7890
http://127.0.0.1:7897
socks5://127.0.0.1:7891
```

请以你本地 Clash 客户端显示的端口为准。

## 支持的代理协议

```text
http://
https://
socks4://
socks5://
socks5h://
```

对大多数 Clash 场景，`http://127.0.0.1:7890` 是最简单的起点。

## 环境变量代理

FlowScribe 也可能继承 Python、`yt-dlp` 和 ffmpeg 常见的代理环境变量：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:7890"
$env:HTTPS_PROXY="http://127.0.0.1:7890"
flowscribe inspect "https://example.com/video"
```

但如果你是在排查某个具体 URL，显式 `--proxy` 通常更容易定位问题。

## 代理与安全检查

即便使用代理，FlowScribe 仍会继续做公开 URL 的安全校验。

代理支持的目标是解决正常的网络可达性问题，而不是绕过私有网络保护、DRM、平台规则或访问限制。

如果 URL 同时还需要登录态，可以显式同时传入代理和 cookies：

```powershell
flowscribe url "https://example.com/video" --proxy "http://127.0.0.1:7890" --cookies "D:\private\cookies.txt" -o outputs
```
