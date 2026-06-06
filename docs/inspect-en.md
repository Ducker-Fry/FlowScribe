[中文](inspect.md) | English

# Inspect Command

`flowscribe inspect` checks a local media file or public URL before transcription. It does not transcribe and does not download URL media.

Use it when you want to know:

- whether a local file has an audio stream
- whether a URL is a direct media URL or a supported page URL
- whether a page exposes audio-only media
- whether FlowScribe will stream combined media and extract audio
- basic duration, format count, and selected strategy

## Inspect A Local File

```powershell
flowscribe inspect "D:\media\lecture.mp4"
```

Example:

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

If `Ready for transcription` is `no`, the file has no audio stream.

## Inspect A Public URL

```powershell
flowscribe inspect "https://tv.cctv.com/2026/05/12/VIDEBtNAQbQRT5vvxRFP28FR260512.shtml"
```

Example shape:

```text
FlowScribe inspect
===================
Type: url
Source: https://tv.cctv.com/...
Kind: video-page-url
Title: ...
Duration: 00:02:16.000
Formats: 1
Audio-only stream: no
Combined media stream: yes
Planned strategy: stream lowest combined media and extract audio
Selected format:
  id: hls-460
  ext: mp4
  protocol: m3u8
  resolution: 480x270
  audio codec: unknown
  video codec: unknown
  bitrate: 461.0
  size: 7.5 MiB
Note: no standalone audio stream was found; FlowScribe will stream combined media and save only extracted audio.
```

## JSON Output

```powershell
flowscribe inspect "D:\media\lecture.mp4" --json
flowscribe inspect "https://example.com/video" --json
```

## Cookies

For login-required sources you are allowed to access, pass a Netscape-format cookie file:

```powershell
flowscribe inspect "https://example.com/video" --cookies "D:\private\cookies.txt"
flowscribe url "https://example.com/video" --cookies "D:\private\cookies.txt" -o outputs
```

See [cookies-en.md](cookies-en.md).

## Network Family

Some proxy or DNS environments may need explicit IPv4:

```powershell
flowscribe inspect "https://www.youtube.com/watch?v=aUL-VAt0gDI" --network-family ipv4
flowscribe url "https://www.youtube.com/watch?v=aUL-VAt0gDI" --network-family ipv4
```

## Proxy

If a URL works only through a local proxy:

```powershell
flowscribe inspect "https://www.youtube.com/watch?v=aUL-VAt0gDI" --proxy "http://127.0.0.1:7890"
flowscribe url "https://www.youtube.com/watch?v=aUL-VAt0gDI" --proxy "http://127.0.0.1:7890" -o outputs
```

See [proxy-en.md](proxy-en.md).

## How To Read The Strategy

- `download audio directly`
- `stream URL with ffmpeg and extract audio`
- `download audio-only stream`
- `stream lowest combined media and extract audio`
- `stream selected page media and extract audio`
- `unsupported: no usable audio or combined media stream`

## Common URL Failures

Common causes:

- unsupported site
- login-only media
- missing or expired cookies
- DRM or protected media
- network or proxy issues
- anti-bot rules
- outdated `yt-dlp`

If needed:

```powershell
python -m pip install -U yt-dlp
```
