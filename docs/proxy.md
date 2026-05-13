# Proxy Configuration

FlowScribe can use a local proxy such as Clash when accessing URL media. This is
useful when a site is reachable in your browser through a proxy but fails in the
terminal.

## Explicit Proxy Option

Prefer passing the proxy explicitly:

```powershell
flowscribe inspect "https://www.youtube.com/watch?v=aUL-VAt0gDI" --proxy "http://127.0.0.1:7890"
flowscribe url "https://www.youtube.com/watch?v=aUL-VAt0gDI" --proxy "http://127.0.0.1:7890" -o outputs
```

Common Clash ports are:

```text
http://127.0.0.1:7890
http://127.0.0.1:7897
socks5://127.0.0.1:7891
```

Use the port shown in your Clash client.

## Supported Proxy Schemes

```text
http://
https://
socks4://
socks5://
socks5h://
```

For most Clash setups, `http://127.0.0.1:7890` is the simplest choice.

## Environment Proxy

FlowScribe may also inherit standard environment variables used by Python,
`yt-dlp`, and ffmpeg:

```powershell
$env:HTTP_PROXY="http://127.0.0.1:7890"
$env:HTTPS_PROXY="http://127.0.0.1:7890"
flowscribe inspect "https://example.com/video"
```

The explicit `--proxy` option is easier to debug and is recommended when you are
testing a specific URL.

## Proxy And Safety Checks

FlowScribe still performs public URL safety validation before downloading media.
Proxy support is meant to fix normal network reachability issues, not to bypass
private-network protection, DRM, platform rules, or access restrictions.

If a URL requires login, combine proxy and cookies explicitly:

```powershell
flowscribe url "https://example.com/video" --proxy "http://127.0.0.1:7890" --cookies "D:\private\cookies.txt" -o outputs
```
