# 中文 | [English](inspect-en.md)

# Inspect 命令

`flowscribe inspect` 用来在正式转录前检查本地媒体文件或公开 URL。

它不会开始转录，也不会真正下载 URL 媒体。

适合这些场景：

- 先确认本地文件里有没有音频流
- 先确认一个 URL 是直链媒体，还是支持的视频页面
- 先确认页面是否提供音频流
- 先确认 FlowScribe 会采用什么处理策略
- 先看大致时长、格式数量和计划行为

## 检查本地文件

```powershell
flowscribe inspect "D:\media\lecture.mp4"
```

示例输出：

```text
FlowScribe inspect
===================
Type: local
Source: D:\media\lecture.mp4
Exists: yes
Duration: 00:12:34.000
Audio streams: 1
Video streams: 1
Format: mov,mp4,m4a,3gp,3g2,mj2
Size: 120.4 MiB
Ready for transcription: yes
```

如果 `Ready for transcription` 是 `no`，通常说明文件没有音频流。

## 检查公开 URL

```powershell
flowscribe inspect "https://tv.cctv.com/2026/05/12/VIDEBtNAQbQRT5vvxRFP28FR260512.shtml"
```

常见输出形态会包含：

- 来源类型
- 页面标题
- 时长
- 格式数量
- 是否存在音频专用流
- 是否存在音视频合并流
- 计划采用的处理策略

## JSON 输出

如果你要给 GUI、脚本或自动化流程使用：

```powershell
flowscribe inspect "D:\media\lecture.mp4" --json
flowscribe inspect "https://example.com/video" --json
```

## Cookies

某些站点登录后才会暴露可用媒体。对于你有合法访问权限的来源，可以显式传入 Netscape 格式的 cookies 文件：

```powershell
flowscribe inspect "https://example.com/video" --cookies "D:\private\cookies.txt"
flowscribe url "https://example.com/video" --cookies "D:\private\cookies.txt" -o outputs
```

详见 [cookies.md](cookies.md)。

## Network Family

默认情况下 FlowScribe 会自动选择地址族，同时继续阻止私有地址、回环地址和保留地址。

如果你的 DNS 或代理环境对某些公开视频站点存在异常 IPv6 返回值，可以显式指定 IPv4：

```powershell
flowscribe inspect "https://www.youtube.com/watch?v=aUL-VAt0gDI" --network-family ipv4
flowscribe url "https://www.youtube.com/watch?v=aUL-VAt0gDI" --network-family ipv4
```

## Proxy

如果某个 URL 必须走本地代理：

```powershell
flowscribe inspect "https://www.youtube.com/watch?v=aUL-VAt0gDI" --proxy "http://127.0.0.1:7890"
flowscribe url "https://www.youtube.com/watch?v=aUL-VAt0gDI" --proxy "http://127.0.0.1:7890" -o outputs
```

详见 [proxy.md](proxy.md)。

## 怎么理解策略字段

常见计划策略包括：

- `download audio directly`
- `stream URL with ffmpeg and extract audio`
- `download audio-only stream`
- `stream lowest combined media and extract audio`
- `stream selected page media and extract audio`
- `unsupported: no usable audio or combined media stream`

它们的核心意思是：FlowScribe 是直接取音频、还是要流式读取合并媒体后提取音频，或者当前根本找不到可用媒体。

## 常见 URL 失败原因

常见原因包括：

- 站点不受支持
- 媒体需要登录
- cookies 缺失或失效
- DRM 或保护性媒体
- 网络或代理问题
- 站点的反爬策略
- `yt-dlp` 提取器过旧

如果需要，可以先更新依赖：

```powershell
python -m pip install -U yt-dlp
```
