[中文](cookies.md) | English

# Cookies For Login-Required URL Media

Some video pages expose playable media only after normal browser login. FlowScribe supports an explicit `--cookies` option for those cases.

## When To Use Cookies

Use cookies only when anonymous access fails because the site requires login, age confirmation, region confirmation, or a similar session state:

```powershell
flowscribe inspect "https://example.com/watch/123" --cookies "D:\private\cookies.txt"
flowscribe url "https://example.com/watch/123" --cookies "D:\private\cookies.txt" -o outputs --format txt,md,json
```

If a site works without cookies, do not pass cookies.

## Cookie File Format

The file should be a Netscape `cookies.txt` file, the same format accepted by `yt-dlp`.

## Safety Rules

- do not commit cookie files to Git
- do not paste cookie contents into issues, logs, screenshots, or prompts
- keep cookies outside the repository when possible
- refresh or delete them when the session expires
- cookies do not bypass DRM or access restrictions

FlowScribe's `.gitignore` blocks common cookie file patterns, but you should still check `git status` before committing.

## Error Hints

FlowScribe may suggest:

```text
retry with --cookies path\to\cookies.txt
```

This means anonymous access did not expose the media. It does not guarantee the source will work.

## Recommended Workflow

1. inspect first
2. if the source exposes usable media, run `flowscribe url`
3. if it still fails, refresh the cookie file, update `yt-dlp`, or choose a source you can access directly
