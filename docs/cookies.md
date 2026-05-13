# Cookies For Login-Required URL Media

Some video pages only expose playable media after you log in. FlowScribe supports
an explicit `--cookies` option for these cases. It passes a Netscape-format
`cookies.txt` file to `yt-dlp` and then continues with the normal audio-first
transcription pipeline.

FlowScribe does not collect, generate, or store cookies for you. You choose the
file explicitly for each command that needs it.

## When To Use Cookies

Use cookies only when a public URL fails because the site requires a normal
logged-in browser session, age/region confirmation, or similar access state:

```powershell
flowscribe inspect "https://example.com/watch/123" --cookies "D:\private\cookies.txt"
flowscribe url "https://example.com/watch/123" --cookies "D:\private\cookies.txt" -o outputs --format txt,md,json
```

If a site works without cookies, prefer not passing cookies.

## Cookie File Format

The file should be a Netscape `cookies.txt` file, the same format accepted by
`yt-dlp`. Browser cookie export tools can usually export this format.

Keep the file private. It may contain active login session data.

## Safety Rules

- Do not commit cookie files to Git.
- Do not paste cookie contents into issues, logs, screenshots, or prompts.
- Store cookies outside the repository when possible.
- Refresh or delete the file if the site says the session expired.
- Cookies do not bypass DRM, paid access, or platform rules.

FlowScribe's `.gitignore` blocks common cookie paths such as:

```text
cookies.txt
*.cookies.txt
/cookies/
/.cookies/
```

These ignore rules reduce accidental commits, but you should still check
`git status` before committing.

## Error Hints

When URL inspection or download fails, FlowScribe may suggest:

```text
retry with --cookies path\to\cookies.txt
```

That means the extractor could not access the media with anonymous access. It is
not a guarantee that cookies will work; the source may still be unsupported,
protected, DRM-restricted, or blocked by network/proxy conditions.

## Recommended Workflow

1. Inspect first:

   ```powershell
   flowscribe inspect "https://example.com/watch/123" --cookies "D:\private\cookies.txt"
   ```

2. If inspect shows usable audio or combined media, transcribe:

   ```powershell
   flowscribe url "https://example.com/watch/123" --cookies "D:\private\cookies.txt" -o outputs --preset zh --format txt,md,json
   ```

3. If it still fails, update `yt-dlp`, refresh the cookie file, or use a source
   you are allowed to access directly.
