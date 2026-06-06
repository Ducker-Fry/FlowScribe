[中文](proxy.md) | English

# Proxy Configuration

FlowScribe can use a local proxy such as Clash when accessing URL media.

## Explicit Proxy Option

```powershell
flowscribe inspect "https://www.youtube.com/watch?v=aUL-VAt0gDI" --proxy "http://127.0.0.1:7890"
flowscribe url "https://www.youtube.com/watch?v=aUL-VAt0gDI" --proxy "http://127.0.0.1:7890" -o outputs
```

Common Clash ports:

```text
http://127.0.0.1:7890
http://127.0.0.1:7897
socks5://127.0.0.1:7891
```

## Supported Proxy Schemes

```text
http://
https://
socks4://
socks5://
socks5h://
```

## Environment Proxy

FlowScribe may also inherit standard environment proxy variables:

```powershell
$env:HTTP_PROXY="http://127.0.0.1:7890"
$env:HTTPS_PROXY="http://127.0.0.1:7890"
flowscribe inspect "https://example.com/video"
```

Explicit `--proxy` is usually easier to debug.

## Proxy And Safety Checks

Proxy support is for reachability problems, not for bypassing private-network protection, DRM, platform rules, or access restrictions.

If a URL also requires login, combine proxy and cookies explicitly:

```powershell
flowscribe url "https://example.com/video" --proxy "http://127.0.0.1:7890" --cookies "D:\private\cookies.txt" -o outputs
```
