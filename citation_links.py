"""Conservative APA author/year linking; never invent or rewrite reference data."""
import re
from collections import defaultdict

YEAR = r'(?:18|19|20|21)\d{2}[a-z]?'
# APA reference authors use surname, initials. Full corporate names are supported too.
AUTHOR = re.compile(r"(?:^|[,;&]\s*|\band\s+|\bve\s+)([^,;&\d]+?),\s*(?:[A-ZÇĞİÖŞÜ]\.(?:\s*[-–]?\s*[A-ZÇĞİÖŞÜ]\.)*)")


def _name_pattern(name):
    return r'\s+'.join(re.escape(part) for part in name.split())


class CitationIndex:
    def __init__(self, references, enabled=True):
        self.references = references
        self.patterns = []
        self.unsupported = []
        self.ambiguous = []
        if not enabled:
            return
        groups = defaultdict(list)
        patterns = {}
        for index, ref in enumerate(references):
            year = re.search(r'\((' + YEAR + r')\)', ref)
            if not year:
                self.unsupported.append(index)
                continue
            prefix = ref[:year.start()].strip()
            names = [m.group(1).strip(' .,&;') for m in AUTHOR.finditer(prefix)]
            if not names and ',' not in prefix and prefix:
                names = [prefix.rstrip('.')]
            if not names:
                self.unsupported.append(index)
                continue
            first = _name_pattern(names[0])
            if len(names) == 2:
                author = first + r'\s*(?:&|ve|and)\s*' + _name_pattern(names[1])
            elif len(names) > 2 or re.search(r'\bet\s+al\.|\bvd\.', prefix):
                author = first + r'\s+(?:et\s+al\.|vd\.|ve\s+ark\.)'
            else:
                author = first
            # No bare four-digit numbers: require a recognizable author/year citation.
            pattern = r'(?<![\w\-])' + author + r'(?:\s*,\s*|\s+\(\s*)' + year.group(1) + r'(?![\w])'
            key = pattern.replace('İ', 'I').lower()
            groups[key].append(index)
            patterns[key] = pattern
        for pattern, indices in groups.items():
            if len(indices) > 1:
                self.ambiguous.extend(indices)
            # Keep ambiguous patterns to detect collisions with more specific matches.
            self.patterns.append((re.compile(patterns[pattern], re.IGNORECASE), indices))

    def spans(self, text):
        candidates = []
        for pattern, indices in self.patterns:
            for match in pattern.finditer(text):
                # Do not link a shortened single-author tail of a multi-author citation.
                prefix = text[:match.start()]
                if re.search(r'(?:&|\bve|\band)\s*$', prefix, re.IGNORECASE):
                    continue
                end = match.end()
                if '(' in match.group() and end < len(text) and text[end] == ')':
                    end += 1
                candidates.append((match.start(), end, indices))
        candidates.sort(key=lambda item: (item[0], -item[1]))
        end = -1
        for start, stop, indices in candidates:
            if start < end:
                continue
            end = stop
            if len(indices) == 1:
                yield start, stop, indices[0]

    def latex(self, text, escape):
        pieces, start = [], 0
        for left, right, index in self.spans(text):
            pieces.extend([escape(text[start:left]), r'\hyperlink{aiditor_ref_' + str(index) + '}{' + escape(text[left:right]) + '}'])
            start = right
        pieces.append(escape(text[start:]))
        return ''.join(pieces)


def citation_report(data, enabled=True):
    refs = [r.strip() for r in data.get('references', '').splitlines() if r.strip()]
    index = CitationIndex(refs, enabled)
    count = sum(len(list(index.spans(s.get('content', '')))) for s in data.get('sections', []))
    return {'enabled': enabled, 'linked_in_body': count, 'ambiguous_references': len(index.ambiguous), 'unrecognized_references': len(index.unsupported)}
