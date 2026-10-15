---
name: video-share-download
description: |
  Download the actual media file behind a short-video / social share link when
  plain HTTP fetching does not work, then verify the container before reporting
  success. Use when the user pastes a 抖音 / TikTok / 视频号 / Bilibili /
  Xiaohongshu share URL and asks to download, save, archive or keep the video
  ("帮我下载这个视频", "把这个视频存下来", "download this video"), and also when
  a share page turns out to return an empty or JavaScript-only body. Do NOT use
  for searching a platform's catalogue for popular works (use douyin-search), for
  analysing a video file already on disk, for generating or editing video, or for
  getting past a login / paywall / captcha / DRM gate.
---

# Video Share Download

## Inputs to collect

- the share link — it usually arrives wrapped in the platform's share blurb; pull
  the URL out of it
- destination directory — default to the session workspace on a **local** disk
- whether a watermark-free copy or the highest available quality is wanted
- if it is unclear the media is the user's own: note once, plainly, that this
  pulls publicly reachable media and is for personal / own-content use

## Procedure

1. **Check for a real downloader before doing any of this by hand.**
   Probe for `yt-dlp` first. On this machine it was absent but pip-installable into a
   scratch directory in seconds, so "not installed" is not the same as "unavailable".
   Treat it as a convenience for muxing and URL handling rather than a shortcut around
   the hard part: on Douyin it still refuses with "fresh cookies needed" until a
   browser has minted a session, so step 4 is unavoidable on an anti-bot platform
   either way. The point of the steps below is that they need nothing installed.

2. **Resolve the share link to its canonical form.**
   Short share URLs (`v.douyin.com/xxxx/`) 302 to a platform page whose
   `Location:` header carries the canonical URL *including the numeric content id*.
   Fetch without following redirects so the header stays visible:
   ```
   curl.exe -s -o NUL -D - -A "<browser UA>" "<short-url>"
   ```
   Keep that numeric id — it is the handle every later step keys on.

3. **Probe the share page for real data before drawing any conclusion.**
   Download the HTML and search it for the platform's data keys (`play_addr`,
   `_ROUTER_DATA`, `RENDER_DATA`, or the id from step 2).
   - Real data present → parse it directly, jump to step 5.
   - A body of only a few hundred bytes → usually a bare redirect stub. Follow it
     once (it lands on the desktop page) and re-probe before concluding anything.
   - A body of tens of KB with no data keys, made of one long obfuscated JavaScript
     VM (ByteDance's `_$jsvmprt`, `__pace` and relatives) → **this is an anti-bot
     shell. The obstruction is structural, not a request-header problem.** No
     permutation of User-Agent / Referer / Cookie changes it. Go to step 4 instead
     of brute-forcing headers.

4. **Let a real browser run the page, then capture the data request.**
   Probe what is actually available before improvising — a CLI browser driver is
   usually already on PATH, and it covers this whole step. On this machine
   `playwright-cli` was present with `requests` / `response-body` / `eval`
   subcommands, which is precisely the "list requests, save a response body" pair
   needed here. Naming the candidate first saves several wasted probes.
   Navigate to the canonical URL and let the JavaScript run.
   Two facts make the DOM useless here: the media URL does not exist until an XHR
   returns it, and a live `<video>` element normally exposes a `blob:` URL from a
   media-source extension, which means nothing outside the page. So read the
   network layer:
   - Find the request: list network requests filtered to `xhr`/`fetch` and look
     for the one whose path is the platform's content-detail endpoint, identified
     by carrying the numeric id from step 2 as a query parameter. Cross-check with
     `performance.getEntriesByType('resource')` evaluated in the page.
   - **Write that response body straight to a file.** Re-fetching the URL from
     inside the page tends to return the anti-bot HTML instead of JSON, because the
     signature and cookie pair are bound to the original call.
   - An empty request list means recording began after load — reload with capture
     active.

5. **Extract the media URL structurally, and treat resolution and watermark as two
   separate decisions.**
   Field names drift between platform versions (`download_addr`, `play_addr`,
   `play_addr_h264`, `bit_rate[].play_addr`, …). Walk the parsed JSON for any object
   carrying a `url_list` array rather than grepping for one name, and read the
   `width` / `height` that sits beside each candidate.

   **Do not rank candidates by bitrate, and do not trust the declared dimensions.**
   On Douyin the watermark-free `download_addr` yields the *larger* file (62.19 MB,
   ~576 kbps measured) at **720×1280**, while the watermarked `play_addr` yields the
   *smaller* file (52.45 MB, ~488 kbps measured) at **1080×1920**. Ranking by bitrate
   picks the worse picture while looking like the premium choice. And the `width` /
   `height` sitting beside `download_addr` read `720×720` — a third value matching
   neither rendition. Declared fields are not measurements; only step 7 produces real
   ones. Pick by measuring both candidates when the choice matters.

   Decide deliberately and state it:
   - resolution first → take the candidate that step 7 measures as the largest
   - watermark-free first → take the download field and say what resolution that cost

   Read `video.has_watermark` (or the platform's equivalent) and report the delivered
   file's watermark status explicitly — "best picture" is not a synonym for "clean".
   For a request as vague as "download this video", best picture is the safer default;
   raise the tradeoff only when the two axes genuinely conflict for the user.

   Keep every candidate URL — CDN hosts rotate, and one host can 403 while a sibling
   serves the identical object.

6. **Download with the request context the CDN expects.**
   Send `Referer: https://<platform-domain>/` plus an ordinary desktop browser UA;
   the CDN answers 403 on mismatched context. Validate that `Content-Type` is
   `video/*`, `audio/*` or `application/octet-stream` **before** accepting the
   bytes — a `200` carrying the anti-bot page is the common silent failure, and it
   is precisely what step 7 exists to catch. Walk the URL list on failure; if every
   entry fails the URLs have expired, so return to step 4 and re-extract rather
   than retrying the same URLs.

7. **Verify the container, then report measured numbers.**
   ```
   node scripts/verify-media.js <file> --expect-duration <seconds>
   ```
   "HTTP 200" plus "the file exists" is not evidence — a truncated download
   satisfies both. The script walks the ISO-BMFF box tree, reports measured
   duration / resolution / track handlers / codec, and exits non-zero when `mdat`
   runs past end-of-file, when the bytes are not an mp4 at all, or when the duration
   disagrees with the metadata beyond tolerance.

   Compare the **measured resolution** against the `width`/`height` the metadata
   advertised. A mismatch is the signal that you received a different rung of the
   quality ladder than you believed — on Douyin the metadata says 1080×1920 while
   the watermark-free download is genuinely 720×1280, and nothing else in the
   pipeline notices that. Report what the script measured, not what the API claimed.

8. **Clean up intermediates and deliver.**
   Remove the saved page HTML and raw JSON with the recoverable-delete launcher —
   a single `rm -- "<literal path1>" "<literal path2>"` at top level. `Remove-Item` is
   blocked by the runtime's delete guard, and a PowerShell variable inside the argument
   is passed through unexpanded, producing a misleading "No such file" naming the
   literal `$var`. Deliver the media file with its absolute local path and the
   measured facts.

## Output contract

- the media file on a local disk, plus its absolute path
- measured facts: duration, resolution, track handlers / codec, size, average
  bitrate, watermark status
- one explicit line stating how it was verified
- when verification fails, the outcome is reported as a failure — never dressed up
  as a completed download

## Failure handling

- **Login / paywall / captcha wall** → stop and report. Do not try to defeat it;
  ask the user for the file or for an authenticated session they control.
- **DRM or encrypted segments** → the stream will not extract. Say so plainly
  instead of shipping a short or silent file.
- **Only a DASH / fragmented rendition is offered, and no muxer is available** →
  separate video-only and audio-only streams cannot be combined by hand. Check whether
  a combined progressive variant (`play_addr`) exists first and prefer it; otherwise
  report that the resolution chosen needs a muxer you do not have, rather than
  delivering one bare track.
- **`<video>` plays but the download 403s** → in order of likelihood: missing
  Referer/UA, then an expired URL, then a regional or risk block.
- **Metadata duration ≠ file duration** → investigate before delivering. A few
  seconds' gap is normal segment padding; a large gap means a partial file or the
  wrong variant.
- **Network drives are read-only** (`X:` `Z:` `G:` `H:` and any UNC path) → write
  the output to a local disk and report that path. Do not write to them, including
  via shell redirect or a copy-out step.

## Examples

Input: `【抖音精选】…15分钟讲透君子不器… https://v.douyin.com/t2pVNVwLlOk/ 帮我下载这个视频`

Observed path: 302 → `iesdouyin.com/share/video/<id>/` → a 183-byte redirect stub
→ `www.douyin.com/video/<id>` → 72.9 KB `_$jsvmprt` JS shell with zero occurrences
of `play_addr` → browser renders the page → the `aweme/v1/web/aweme/detail/` XHR
returns HTTP 200 → read the candidate `url_list` entries → GET with
`Referer: https://www.douyin.com/` → `200 video/mp4`, 62.19 MB → verify: measured
905.023 s against 902 s claimed (delta 3.023 s, inside tolerance), `vide` + `soun`
tracks, `mdat` ends exactly at EOF, and measured resolution **720×1280** where the
metadata advertised 1080×1920 — the watermark-free rung is the lower-resolution one.

## Windows (win32) platform notes

- Shell is PowerShell. Invoke `curl.exe` explicitly (bare `curl` is an alias), and
  keep `&` inside quoted URLs out of unquoted shell arguments.
- `Remove-Item` is blocked by the runtime's delete guard. Use the recoverable-delete
  launcher with **literal full paths** — a PowerShell variable placed inside the
  argument is passed through unexpanded, so the command fails with a misleading
  "No such file" pointing at the unexpanded name.
- Use `python`, not `python3`. Pass `-Encoding UTF8` to file-reading cmdlets, and
  prefer the Read/Write tools for file content.
- **Console output is decoded through the local code page (GBK / cp936 on this
  machine), which mangles CJK on screen.** On PowerShell 7.6.6 a controlled
  byte-for-byte test found `node x.js > f.json` and `cmd /c … > f.json` produce
  *identical, correct* UTF-8 files, so the mangling seen so far has been confined to
  console display. A file that really was corrupted would show this signature: the
  substituted `?` truncates a JSON string early and `JSON.parse` throws while claiming
  the file is damaged. When that happens, do not assume the source is bad — switch to a
  byte-transparent capture (`curl -o`, a tool's own `--output`/`--filename` argument, or
  `fs.writeFileSync`) and re-test before touching the data.
- Mojibake on the console is display-only. Mojibake **inside a file** is real
  corruption — fix the capture path rather than working around the parse error.

## References

- `references/douyin.md` — endpoint paths, response field map, anti-bot markers and
  known traps. Verified 2026-10-15; re-verify if the platform shifts.
