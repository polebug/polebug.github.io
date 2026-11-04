"""Repack the installed, pinned Fontsource glyphs; no font download or redesign."""
import hashlib
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from fontTools import subset
from fontTools.merge import Merger
from fontTools.ttLib import TTFont


def ranges(points):
    result = []
    for cp in sorted(points):
        if result and cp == result[-1][1] + 1:
            result[-1][1] = cp
        else:
            result.append([cp, cp])
    return ','.join(f'U+{a:X}' if a == b else f'U+{a:X}-{b:X}' for a, b in result)


def parse_ranges(value):
    result = set()
    for term in value.split(','):
        parts = term.strip().removeprefix('U+').split('-')
        start, end = int(parts[0], 16), int(parts[-1], 16)
        result.update(range(start, end + 1))
    return result


def options():
    opts = subset.Options()
    opts.layout_features = ['*']
    opts.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14]
    opts.recalc_timestamp = False
    return opts


def generate(config):
    output = Path(config['output'])
    css_file = Path(config['sourceCss'])
    # Mirror CSS precedence, including overlapping punctuation/Latin shards.
    assigned = set()
    shards = []
    reference_metrics = {}
    for block in reversed(re.findall(r'@font-face\s*\{([^}]+)\}', css_file.read_text())):
        filename = css_file.parent / re.search(r'url\(([^)]+\.woff2)\)', block)[1]
        css_points = parse_ranges(re.search(r'unicode-range:\s*([^;]+)', block)[1])
        font = TTFont(filename)
        cmap = font.getBestCmap()
        points = css_points.intersection(cmap) - assigned
        assigned.update(points)
        for cp in points:
            reference_metrics[cp] = font['hmtx'][cmap[cp]]
        shards.append({'filename': filename, 'points': points, 'bytes': filename.stat().st_size})
        font.close()
    lato = set(TTFont(config['lato']).getBestCmap())
    for page in config['pages']:
        page['points'] = {ord(c) for c in page['text']} & assigned - lato
    # Frozen once selected: adding a post does not invalidate everyone's shared cache.
    common_file = Path(config['commonFile'])
    if common_file.exists() and not config['refreshCommon']:
        common = {ord(c) for c in common_file.read_text().strip()} & assigned - lato
    else:
        frequency = Counter()
        documents = Counter()
        for page in config['pages']:
            if page['article']:
                documents.update(page['points'])
                frequency.update(ord(c) for c in page['text'] if ord(c) in page['points'])
        candidates = sorted((cp for cp in documents if documents[cp] >= 3), key=lambda cp: (-documents[cp], -frequency[cp], cp))
        common = set(candidates[:768])
        common_file.write_text(''.join(chr(cp) for cp in sorted(common)) + '\n')

    # Runtime labels are created after HTML rendering, so include their glyphs in
    # the shared set too. New labels otherwise trigger several fallback shards.
    common.update({ord(c) for c in config.get('uiText', '')} & assigned - lato)
    # Composite emoji / symbol fallback can request Latin glyphs from the CJK
    # family too. Keep those in the shared face rather than fetching old shards.
    common.update(cp for cp in lato & assigned if chr(cp).isprintable())
    common_file.write_text(''.join(chr(cp) for cp in sorted(common)) + '\n')

    master_path = output / f"master-{config['sourceDigest']}.ttf"
    if not master_path.exists():
        with tempfile.TemporaryDirectory() as tmp:
            files = []
            for i, shard in enumerate(shards):
                if not shard['points']:
                    continue
                font = TTFont(shard['filename'], recalcTimestamp=False)
                worker = subset.Subsetter(options=options())
                worker.populate(unicodes=shard['points'])
                worker.subset(font)
                font.flavor = None
                filename = Path(tmp) / f'{i}.ttf'
                font.save(filename)
                files.append(str(filename))
            master = Merger().merge(files)
            master.recalcTimestamp = False
            master['head'].created = master['head'].modified = 2082844800
            master.save(master_path)
            master.close()
    master = TTFont(master_path)
    cmap = master.getBestCmap()
    # Check every glyph's horizontal metrics against the existing published font.
    for cp, metric in reference_metrics.items():
        if master['hmtx'][cmap[cp]] != metric:
            raise ValueError(f'Glyph metrics changed: U+{cp:X}')
    master.close()
    generated = {}

    def make_font(points, label):
        if not points:
            return None
        identity = tuple(sorted(points))
        if identity in generated:
            return generated[identity]
        font = TTFont(master_path, recalcTimestamp=False)
        worker = subset.Subsetter(options=options())
        worker.populate(unicodes=points)
        worker.subset(font)
        if not points.issubset(font.getBestCmap()):
            raise ValueError('Subset lost requested characters')
        font.flavor = 'woff2'
        temporary = output / 'subset.tmp.woff2'
        font.save(temporary)
        font.close()
        data = temporary.read_bytes()
        digest = hashlib.sha256(data).hexdigest()[:24]
        name = f'noto-{label}.{digest}.woff2'
        temporary.replace(output / name)
        record = {'key': f'fonts/{name}', 'bytes': len(data), 'unicodeRange': ranges(points), 'characters': len(points)}
        generated[identity] = record
        return record

    shared = make_font(common, 'common')
    manifest = {'version': 1, 'sourceDigest': config['sourceDigest'], 'shared': shared, 'fallbackRanges': {s['filename'].stem: ranges(s['points']) for s in shards}, 'pages': {}}
    for page in config['pages']:
        points = page['points']
        extra = points - common
        font = make_font(extra, 'page')
        baseline = [s for s in shards if s['points'] & points]
        new_bytes = (shared['bytes'] if points & common else 0) + (font['bytes'] if font else 0)
        manifest['pages'][page['route']] = {
            'font': font,
            'characters': len(points),
            'baselineBytes': sum(s['bytes'] for s in baseline),
            'baselineRequests': len(baseline),
            'subsetBytes': new_bytes,
            'subsetRequests': int(bool(points & common)) + int(bool(extra)),
        }
        print(f"{page['route']}: {sum(s['bytes'] for s in baseline)//1024} -> {new_bytes//1024} KiB; {len(baseline)} -> {manifest['pages'][page['route']]['subsetRequests']} Chinese font requests", flush=True)
    (output / 'subsets.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Checked {len(reference_metrics)} original glyph metrics; generated {len(generated)} distinct subsets.')


if __name__ == '__main__':
    generate(json.loads(Path(sys.argv[1]).read_text()))
