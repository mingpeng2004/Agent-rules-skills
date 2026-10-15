# Douyin — concrete field map and traps

Verified 2026-10-15 against aweme id `7694152109259787574`. Treat this as a map of
*where to look*, not a frozen contract: Douyin renames and re-signs endpoints
regularly. If a step stops matching, relocate it the way described under
"Relocating the endpoint" rather than trusting the literal strings below.

## Canonical URL forms

| Form | Example |
|---|---|
| Short share | `https://v.douyin.com/<slug>/` |
| Resolved share page | `https://www.iesdouyin.com/share/video/<aweme_id>/?region=CN&mid=...` |
| After JS redirect | `https://www.douyin.com/video/<aweme_id>` |

The `aweme_id` is a 19-digit integer and is the only stable handle.

## The two anti-bot shapes

The share path can answer with either of two non-data bodies, and they are not the
same thing:

1. **A bare redirect stub** — around 183 bytes, no data keys at all. Follow it once
   and you land on `www.douyin.com/video/<id>`.
2. **The obfuscated JS-VM shell** — ~73 KB, `<title>` absent, `<body>` empty, and zero
   occurrences of `play_addr`, `video_id`, `aweme`, `_ROUTER_DATA` or `RENDER_DATA`.
   Identifying marker: `_$jsvmprt` (the VM bootstrap
   `(glb=...)?._$jsvmprt=function(b,e,f){...}`), sometimes with `__pace`.

The VM's only job is to compute anti-bot cookies and reload. It carries no media data,
which is why plain HTTP fetching of the share page can never succeed no matter how the
request is dressed up. Note the shell was observed on the **desktop** page in one run
and on the **share** page in another — probe whichever URL you actually landed on
rather than assuming.

**You only see the stub if you do not follow redirects.** `curl -L` consumes the 183-byte
stub silently and lands you straight on the 73 KB shell, so a run that always follows
redirects will never report the stub. Probe once with redirects disabled to see which
shape is actually in front of you.

## Data request

Path (regional hosts vary — `www.douyin.com`, `www-hj.douyin.com`, …):

```
/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&aweme_id=<ID>&...
```

It carries generated `msToken`, `a_bogus`, `x-secsdk-web-signature` and browser
cookies. **Do not try to construct this URL.** Capture the one the page issues —
that is the whole reason this step runs inside a browser.

## Response field map

Root: `aweme_detail`, or `aweme_list[0]` depending on the request flavour.

| Field | Meaning | Notes |
|---|---|---|
| `desc` | caption text | good cross-check that the right video was fetched |
| `author.nickname` | creator | |
| `video.duration` | **milliseconds** | 902004 = 15 min 2 s; easy to mistake for seconds |
| `video.width` / `video.height` | pixel dimensions | 1080 × 1920 — this is the **top** rung, not what every URL serves |
| `video.download_addr.url_list` | watermark-free | declares `720×720`, actually serves **720×1280** |
| `video.play_addr.url_list` | watermarked | combined progressive MP4 with audio, serves **1080×1920** |
| `video.play_addr_h264.url_list` | h264 variant | use when the default is HEVC and the target player cannot decode it |
| `video.bit_rate[].play_addr.url_list` | per-quality ladder | `bit_rate[0]` is the 1080p rung; higher rungs may be DASH-only |

`status_code: 0` means success.

## Declared fields are not measurements

Three different "resolution" numbers exist for this one video, and none of the
declared ones is the delivered one:

| Source | Says | Actually delivered |
|---|---|---|
| `video.width` × `video.height` | 1080 × 1920 | true only for the `play_addr` rung |
| `download_addr.width` × `.height` | **720 × 720** | the file is 720 × 1280 — matches neither |
| `verify-media.js` on the file | — | the only trustworthy value |

So "read the `width`/`height` next to the candidate" is not sufficient on its own: for
`download_addr` those fields are simply wrong. Use them to shortlist, then confirm with
step 7.

Likewise the `br` numbers in the URL query string (562 on the watermark-free URL, 476 on
the watermarked one) do **not** appear in `video.bit_rate[]`, which reports
`487777` for the 1080p rung. Don't cite a bitrate you have not actually read out of
the payload.

## The quality inversion — measured, not declared

Same video, both URL families downloaded and verified:

| URL family | declared `br` in URL | watermark | measured resolution | file size | measured avg bitrate |
|---|---|---|---|---|---|
| `download_addr` | 562 | none | **720×1280** | 62.19 MB | ~576 kbps |
| `play_addr` | 476 | yes | **1080×1920** | 52.45 MB | ~488 kbps |

The watermark-free download is both the larger file *and* the smaller picture, and it
also ran 3 s longer (905.023 s vs 902.005 s). Ranking candidates by bitrate therefore
selects the worse picture while looking like the "premium" choice.

Fetching the 1080p rung may require `ffmpeg` if the top gear is exposed as DASH with
separate video-only and audio-only streams; the combined progressive `play_addr` needs
no merge and was verified working without `ffmpeg` present. The page does fetch DASH in
practice, so this is a live branch, not a theoretical one.

## url_list ordering trap

Each `url_list` typically holds three entries:

1. a `*.douyinvod.com` CDN host (the real object)
2. a second CDN host, same object
3. a `https://www.douyin.com/aweme/v1/play/?...` application redirect

Entry 3 is a redirect endpoint that depends on the session cookies and is the
first thing to fail on a cookie-less download. Prefer entries 1–2; keep 3 as a
last resort rather than dropping it.

## Required download context

```
User-Agent: <ordinary desktop Chrome UA>
Referer:    https://www.douyin.com/
```

Accept `Content-Type: video/mp4`. The observed response was 200 / `video/mp4` /
65 215 849 bytes for `br=562` at 905 s — an average of ~576 kbps, which matches the
declared bitrate and is a useful sanity check that you got the variant you expected.

## Relocating the endpoint

If the path above no longer appears in the network list:

1. In the page, run
   `performance.getEntriesByType('resource').map(e => e.name)` and keep every URL
   whose query string contains the `aweme_id`.
2. Among those, pick the one whose response parsed into a JSON object containing a
   `video` key.
3. Save that response body to a file and inspect it — the field map above then tells
   you which key holds the media.

This is deliberately a procedure, not a literal string, so it survives renames.

## Measured reference values

Two files were downloaded from the same video, one per URL family. Both were verified
with `scripts/verify-media.js`:

| File | URL family | Metadata claimed | File measured |
|---|---|---|---|
| 62 158 849 B | `download_addr` | 902.004 s | 905.023 s (+3.019 s), 720×1280, `avc1`+`mp4a`, `mdat` at EOF |
| 54 997 243 B | `play_addr` | 902.004 s | 902.005 s (+0.001 s), 1080×1920, `avc1`+`mp4a`, `mdat` at EOF |

A ~3 s excess on the watermark-free file is ordinary segment padding, not a defect.

## Two verified traps

**Replaying the signed URL returns HTML with a `200`.** Fetching the captured
`a_bogus`-signed `aweme/detail` URL again — including from inside the page — can return
an anti-bot HTML page while still reporting HTTP 200 and a plausible length. Saving that
as the media file yields an `.mp4` full of markup. Capture the response body at source
through the browser's network layer instead of re-fetching it.

**`yt-dlp` alone will not get past this.** It reports "fresh cookies needed" on the
share link. It does become viable once a browser has minted anonymous cookies for the
session, which is a longer route than capturing the response directly.
