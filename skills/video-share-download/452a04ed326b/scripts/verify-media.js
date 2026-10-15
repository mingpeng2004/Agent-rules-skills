#!/usr/bin/env node
'use strict';
/**
 * verify-media.js — parse an ISO-BMFF container (mp4 / mov / m4a / m4v) and
 * report measured duration, resolution, track handlers, codec markers and
 * truncation. Node built-ins only, no third-party packages.
 *
 * Usage:
 *   node verify-media.js <file> [--expect-duration <seconds>] [--json]
 *
 * Exit code:
 *   0  container parsed and sane
 *   1  unreadable, truncated, or carries no media track
 *
 * Why this exists: a half-downloaded file satisfies "HTTP 200" AND "file
 * exists on disk". Only reading the container tells the two apart. Hand-rolled
 * byte offsets are easy to get wrong (an off-by-4 turns a 905 s duration into
 * the sentinel 16777216), so this logic lives in a script instead of in prose.
 */

const fs = require('fs');

const CONTAINERS = new Set(['moov', 'trak', 'mdia', 'minf', 'stbl', 'edts']);
const MAX_SCAN = 8 * 1024 * 1024; // codec-marker scan cap

function bail(msg) {
  process.stderr.write('FAIL: ' + msg + '\n');
  process.exit(1);
}

/** Read `len` bytes at `pos`, zero-padded if the file ends early. */
function readAt(fd, pos, len) {
  const buf = Buffer.alloc(len);
  if (pos >= 0) fs.readSync(fd, buf, 0, len, pos);
  return buf;
}

function walk(fd, start, end, acc, depth) {
  let pos = start;
  while (pos + 8 <= end) {
    const head = readAt(fd, pos, 8);
    const type = head.toString('latin1', 4, 8);
    let size = head.readUInt32BE(0);
    let hdr = 8;

    if (size === 1) {
      size = Number(readAt(fd, pos + 8, 8).readBigUInt64BE(0));
      hdr = 16;
    } else if (size === 0) {
      size = end - pos;
    }

    if (size < hdr || pos + size > end) {
      acc.boxes.push({ type, pos, size, hdr, depth, clipped: true });
      if (depth === 0) acc.top.push({ type, pos, size, hdr, clipped: true });
      return; // box claims to run past its parent — stop, caller reports it
    }

    acc.boxes.push({ type, pos, size, hdr, depth });
    if (depth === 0) acc.top.push({ type, pos, size, hdr });
    if (CONTAINERS.has(type)) walk(fd, pos + hdr, pos + size, acc, depth + 1);
    pos += size;
  }
}

/** mvhd / mdhd share a layout: version+flags, 2 timestamps, timescale, duration. */
function readTimeBox(fd, pos, hdr) {
  const ver = readAt(fd, pos + hdr, 1)[0];
  if (ver === 1) {
    const ts = readAt(fd, pos + hdr + 4 + 16, 4).readUInt32BE(0);
    const du = Number(readAt(fd, pos + hdr + 4 + 20, 8).readBigUInt64BE(0));
    return { timescale: ts, duration: du };
  }
  const ts = readAt(fd, pos + hdr + 4 + 8, 4).readUInt32BE(0);
  const du = readAt(fd, pos + hdr + 4 + 12, 4).readUInt32BE(0);
  return { timescale: ts, duration: du };
}

/** tkhd carries the display dimensions as 16.16 fixed-point, after a version-sized header. */
function readTkhd(fd, pos, hdr) {
  const ver = readAt(fd, pos + hdr, 1)[0];
  const base = ver === 1 ? pos + hdr + 4 + 40 : pos + hdr + 4 + 24;
  const wh = readAt(fd, base, 8);
  return { width: wh.readUInt32BE(0) / 65536, height: wh.readUInt32BE(4) / 65536 };
}

function main() {
  const argv = process.argv.slice(2);
  let target = null, expect = null, asJson = false;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--json') asJson = true;
    else if (a === '--expect-duration') expect = parseFloat(argv[++i]);
    else if (!a.startsWith('--')) target = a;
  }
  if (!target) bail('usage: node verify-media.js <file> [--expect-duration <s>] [--json]');
  if (!fs.existsSync(target)) bail('file not found: ' + target);

  const stat = fs.statSync(target);
  if (!stat.isFile()) bail('not a regular file: ' + target);
  if (stat.size === 0) bail('file is empty (0 bytes) — the download produced nothing');

  const fd = fs.openSync(target, 'r');
  try {
    // The box TYPE lives at offset 4 (after the 4-byte size). Offset 8 is only
    // meaningful when that type is 'ftyp' — there it holds the major brand.
    const firstType = readAt(fd, 4, 4).toString('latin1');
    const SIGNATURES = ['ftyp', 'styp', 'moov', 'moof', 'free', 'skip', 'mdat', 'wide'];
    if (!SIGNATURES.includes(firstType)) {
      bail(
        'no ISO-BMFF signature — first box type is "' + JSON.stringify(firstType) +
        '", so this is not an mp4/mov file (a saved web page or error body looks like this)'
      );
    }

    const acc = { boxes: [], top: [] };
    walk(fd, 0, stat.size, acc, 0);

    const top = acc.top;
    const moov = top.find((b) => b.type === 'moov');
    const mdat = top.find((b) => b.type === 'mdat');
    const clipped = acc.boxes.filter((b) => b.clipped);

    const report = {
      file: target,
      size_bytes: stat.size,
      ftyp_brand: firstType === 'ftyp' ? readAt(fd, 8, 4).toString('latin1') : null,
      top_level_boxes: top.map((b) => b.type),
      movie: null,
      resolution: null,
      tracks: [],
      codec_markers: [],
      mdat_reaches_eof: null,
      problems: [],
    };

    if (!moov) bail('no moov box — the file has no index, so no player can seek it');
    // Read mvhd from ITS OWN box record in acc.boxes (it is a child of moov, so
    // it is not in the depth-0 `top` list). Passing moov's pos/header instead
    // reads the child box's size field as the version byte and yields a silent NaN.
    const mvhd = acc.boxes.find((b) => b.type === 'mvhd');
    if (!mvhd) bail('moov present but no mvhd box — the movie header is unreadable');
    const mv = readTimeBox(fd, mvhd.pos, mvhd.hdr);
    if (!mv.timescale) bail('mvhd timescale is 0 — duration cannot be computed');
    report.movie = {
      timescale: mv.timescale,
      duration_units: mv.duration,
      seconds: +(mv.duration / mv.timescale).toFixed(3),
    };

    // Scan the index once and reuse it for codec markers and display size.
    // Resolution is authoritative in the VisualSampleEntry inside stsd, NOT in
    // tkhd — tkhd carries 0 for many muxers, which is why an earlier version of
    // this script reported "resolution": null on a perfectly good 720x1280 file.
    const scanLen = Math.min(moov.size, MAX_SCAN);
    const moovBuf = readAt(fd, moov.pos, scanLen);
    const hay = moovBuf.toString('latin1');

    for (const m of ['avc1', 'avcC', 'hvc1', 'hev1', 'hvcC', 'vp09', 'av01', 'mp4a', 'esds', 'Opus'])
      if (hay.indexOf(m) !== -1) report.codec_markers.push(m);

    // VisualSampleEntry layout from box start: 8-byte header, then 24 bytes of
    // reserved/pre_defined/data_reference_index, then width(2) height(2).
    // Verified against two files of known size: 720x1280 and 1080x1920.
    const VIDEO_TAGS = ['avc1', 'hvc1', 'hev1', 'vp09', 'av01'];
    const sampleEntries = [];
    for (const tag of VIDEO_TAGS) {
      let idx = hay.indexOf(tag);
      while (idx !== -1) {
        const boxStart = idx - 4; // type sits 4 bytes into the box
        if (boxStart >= 8 && boxStart + 8 + 28 <= moovBuf.length) {
          const w = moovBuf.readUInt16BE(boxStart + 8 + 24);
          const h = moovBuf.readUInt16BE(boxStart + 8 + 26);
          if (w > 0 && h > 0) sampleEntries.push({ codec: tag, width: w, height: h });
        }
        idx = hay.indexOf(tag, idx + 1);
      }
    }
    const uniqEntries = [];
    for (const e of sampleEntries) {
      if (!uniqEntries.some((u) => u.codec === e.codec && u.width === e.width && u.height === e.height))
        uniqEntries.push(e);
    }
    report.video_sample_entries = uniqEntries;
    report.moov_scan_truncated = moov.size > MAX_SCAN;
    if (report.moov_scan_truncated && !uniqEntries.length) {
      report.problems.push(
        'moov is ' + moov.size + ' bytes, above the ' + MAX_SCAN + '-byte scan limit, and no ' +
        'visual sample entry was found in the scanned prefix — resolution is unknown, not absent'
      );
    }

    for (const t of acc.boxes.filter((b) => b.type === 'trak')) {
      const inTrak = acc.boxes.filter(
        (b) => b.type === 'mdhd' && b.pos > t.pos && b.pos + b.size <= t.pos + t.size
      )[0];
      const hdlr = acc.boxes.filter(
        (b) => b.type === 'hdlr' && b.pos > t.pos && b.pos + b.size <= t.pos + t.size
      )[0];
      const tkhd = acc.boxes.filter(
        (b) => b.type === 'tkhd' && b.pos > t.pos && b.pos + b.size <= t.pos + t.size
      )[0];
      const track = {
        handler: hdlr ? readAt(fd, hdlr.pos + hdlr.hdr + 8, 4).toString('latin1') : 'unknown',
        seconds: inTrak ? +(readTimeBox(fd, inTrak.pos, inTrak.hdr).duration / readTimeBox(fd, inTrak.pos, inTrak.hdr).timescale).toFixed(3) : null,
      };
      if (tkhd) {
        const d = readTkhd(fd, tkhd.pos, tkhd.hdr);
        if (d.width > 0 && d.height > 0) track.tkhd_display_size = Math.round(d.width) + 'x' + Math.round(d.height);
      }
      report.tracks.push(track);
    }

    // Highest declared pixel count wins: that is the entry a player selects.
    if (uniqEntries.length) {
      const best = uniqEntries.reduce((a, b) => (a.width * a.height >= b.width * b.height ? a : b));
      report.resolution = best.width + 'x' + best.height;
      report.resolution_source = 'VisualSampleEntry in stsd' + (uniqEntries.length > 1
        ? ' (' + uniqEntries.length + ' entries declared; largest reported)'
        : '');
    } else {
      const tkhdOnly = report.tracks.find((t) => t.tkhd_display_size);
      if (tkhdOnly) {
        report.resolution = tkhdOnly.tkhd_display_size;
        report.resolution_source = 'tkhd fallback (no VisualSampleEntry found)';
      }
    }

    if (mdat) {
      const end = mdat.pos + mdat.size;
      report.mdat_reaches_eof = end <= stat.size;
      if (end > stat.size) {
        report.problems.push('mdat ends at ' + end + ' but the file is ' + stat.size + ' bytes — TRUNCATED');
      }
    } else {
      report.problems.push('no mdat box — there is no media payload');
    }

    if (clipped.length) {
      report.problems.push(
        clipped.length + ' box(es) run past their parent: ' + clipped.map((b) => b.type).join(', ')
      );
    }

    if (!report.tracks.length) report.problems.push('no tracks found — the file carries no playable media');
    if (!report.tracks.some((t) => t.handler === 'vide') && !report.tracks.some((t) => t.handler === 'soun')) {
      report.problems.push('no video or audio track handler found');
    }

    report.avg_bitrate_kbps = report.movie.seconds
      ? Math.round((stat.size * 8) / report.movie.seconds / 1000)
      : null;

    if (expect && report.movie) {
      const delta = Math.abs(report.movie.seconds - expect);
      const tol = Math.max(5, expect * 0.02);
      report.duration_check = {
        expected_seconds: expect,
        measured_seconds: report.movie.seconds,
        delta_seconds: +delta.toFixed(3),
        tolerance_seconds: +tol.toFixed(1),
        verdict: delta <= tol ? 'match' : 'MISMATCH — investigate before delivering',
      };
      if (delta > tol) report.problems.push('duration mismatch vs claimed ' + expect + 's');
    }

    report.ok = report.problems.length === 0;

    if (asJson) {
      process.stdout.write(JSON.stringify(report, null, 2) + '\n');
    } else {
      const L = [];
      L.push('file      : ' + report.file);
      L.push('size      : ' + report.size_bytes + ' bytes (' + (report.size_bytes / 1048576).toFixed(2) + ' MB)');
      L.push('brand     : ' + report.ftyp_brand);
      L.push('duration  : ' + report.movie.seconds + ' s (' + (report.movie.seconds / 60).toFixed(2) + ' min)');
      if (report.resolution) L.push('resolution: ' + report.resolution + '  (' + report.resolution_source + ')');
      L.push('tracks    : ' + report.tracks.map((t) => t.handler + '@' + t.seconds + 's' + (t.tkhd_display_size ? ' tkhd:' + t.tkhd_display_size : '')).join(', '));
      if (report.codec_markers.length) L.push('codec     : ' + report.codec_markers.join(', '));
      if (report.avg_bitrate_kbps) L.push('bitrate   : ' + report.avg_bitrate_kbps + ' kbps (avg)');
      L.push('mdat@EOF  : ' + report.mdat_reaches_eof);
      if (report.duration_check) {
        L.push('duration chk: claimed ' + report.duration_check.expected_seconds + 's, measured ' +
          report.duration_check.measured_seconds + 's, delta ' + report.duration_check.delta_seconds +
          's (tol ' + report.duration_check.tolerance_seconds + 's) -> ' + report.duration_check.verdict);
      }
      L.push('verdict   : ' + (report.ok ? 'OK' : 'PROBLEMS FOUND'));
      for (const p of report.problems) L.push('  ! ' + p);
      process.stdout.write(L.join('\n') + '\n');
    }

    process.exit(report.ok ? 0 : 1);
  } finally {
    fs.closeSync(fd);
  }
}

main();
