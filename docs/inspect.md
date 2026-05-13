# Inspect Command

`flowscribe inspect` checks a local media file or public URL before transcription.
It does not transcribe and does not download URL media.

Use it when you want to know:

- Whether a local file has an audio stream.
- Whether a URL is a direct audio/video URL or a supported video page.
- Whether a page has an audio-only stream.
- Whether FlowScribe will need to stream combined media and extract audio.
- Basic duration, format count, and selected strategy.

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

For GUI, scripts, or debugging:

```powershell
flowscribe inspect "D:\media\lecture.mp4" --json
flowscribe inspect "https://example.com/video" --json
```

## Network Family

By default, FlowScribe uses automatic address-family resolution and blocks private,
loopback, reserved, and other unsafe addresses. Some DNS or proxy environments may
return an unusual blocked IPv6 address for a public video site. In that case, use
IPv4 explicitly:

```powershell
flowscribe inspect "https://www.youtube.com/watch?v=aUL-VAt0gDI" --network-family ipv4
flowscribe url "https://www.youtube.com/watch?v=aUL-VAt0gDI" --network-family ipv4
```

This still keeps the public-address safety check for IPv4 addresses.

## How To Read The Strategy

`download audio directly`

The URL looks like a direct audio file, such as `.mp3` or `.m4a`.

`stream URL with ffmpeg and extract audio`

The URL looks like a direct video file. FlowScribe asks `ffmpeg` to read the URL
and save only extracted audio.

`download audio-only stream`

The page exposes a standalone audio stream. FlowScribe downloads that audio stream.

`stream lowest combined media and extract audio`

The page does not expose standalone audio. FlowScribe selects the smallest combined
media stream and extracts audio without saving the original video.

`stream selected page media and extract audio`

The page extractor exposes one selected playable stream but does not describe audio
and video codecs clearly. FlowScribe follows the selected page media URL and saves
only extracted audio.

`unsupported: no usable audio or combined media stream`

FlowScribe could not find a usable stream. The source may be video-only, protected,
unsupported, or require login.

## Common URL Failures

If inspection fails, FlowScribe now reports likely causes:

- Unsupported site.
- Login-only media.
- DRM or protected media.
- Network or proxy issue.
- Site anti-bot rules.
- Outdated `yt-dlp` extractor.

Try opening the URL in a browser, using a public direct media URL, or updating
dependencies with:

```powershell
python -m pip install -U yt-dlp
```
