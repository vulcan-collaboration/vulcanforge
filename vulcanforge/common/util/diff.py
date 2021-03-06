import sys
import difflib
from itertools import chain


class Region(object):
    """Simple utility class that keeps track of subsequences"""
    __slots__ = (
        'seq',  # sequence
         'l',  # lower bound
         'h',  # upper bound
    )

    def __init__(self, seq, l=0, h=None):
        if h is None:
            h = len(seq)
        self.seq, self.l, self.h = seq, l, h

    def __iter__(self):
        """Iterates over the subsequence only"""
        for i in xrange(self.l, self.h):
            yield self.seq[i]

    def __getitem__(self, i):
        """works like getitem on the subsequence.  Slices return new
        regions."""
        if isinstance(i, slice):
            start, stop, step = i.indices(len(self))
            assert step == 1
            return self.clone(l=self.l+start, h=self.l+stop)
        elif i >= 0:
            return self.seq[i+self.l]
        else:
            return self.seq[i+self.h]

    def __len__(self):
        return self.h-self.l

    def __repr__(self):
        if len(self) > 8:
            srepr = '[%s,...]' % (','.join(repr(x) for x in self[:5]))
        else:
            srepr = repr(list(self))
        return '<Region (%s,%s): %s>' % (self.l, self.h, srepr)

    def clone(self, **kw):
        """Return a new Region based on this one with the
        provided kw arguments replaced in the constructor.
        """
        kwargs = dict(seq=self.seq, l=self.l, h=self.h)
        kwargs.update(kw)
        return Region(**kwargs)


def region_diff(ra, rb):
    """generator yielding up to two matching blocks, one at the
    beginning of the region and one at the end.  This function
    mutates the a and b regions, removing any matched blocks.
    """
    # Yield match at the beginning
    i = 0
    while i < len(ra) and i < len(rb) and ra[i] == rb[i]:
        i += 1
    if i:
        yield ra.l, rb.l, i
        ra.l += i
        rb.l += i
        # Yield match at the end
    j = 0
    while j < len(ra) and j < len(rb) and ra[-j-1] == rb[-j-1]:
        j += 1
    if j:
        yield ra.h-j, rb.h-j, j
        ra.h -= j
        rb.h -= j


def unique(a):
    """generator yielding unique lines of a sequence and their positions"""
    count = {}
    for aa in a:
        count[aa] = count.get(aa, 0)+1
    for i, aa in enumerate(a):
        if count[aa] == 1:
            yield aa, i


def common_unique(a, b):
    """generator yielding pairs i,j where
    a[i] == b[j] and a[i] and b[j] are unique within a and b,
    in increasing j order."""
    uq_a = dict(unique(a))
    for bb, j in unique(b):
        try:
            yield uq_a[bb], j
        except KeyError, ke:
            continue


def patience(seq):
    stacks = []
    for i, j in seq:
        last_top = None
        for stack in stacks:
            top_i, top_j, top_back = stack[-1]
            if top_i > i:
                stack.append((i, j, last_top))
                break
            last_top = len(stack)-1
        else:
            stacks.append([(i, j, last_top)])
    if not stacks:
        return []
    prev = len(stacks[-1])-1
    seq = []
    for stack in reversed(stacks):
        top_i, top_j, top_back = stack[prev]
        seq.append((top_i, top_j))
        prev = top_back
    return reversed(seq)


def match_core(a, b):
    """Returns blocks that match between sequences a and b as
    (index_a, index_b, size)
    """
    ra = Region(a)
    rb = Region(b)
    # beginning/end match
    for block in region_diff(ra, rb):
        yield block
    # patience core
    last_i = last_j = None
    for i, j in chain(
            patience(common_unique(ra, rb)),
            [(ra.h, rb.h)]):
        if last_i is not None:
            for block in region_diff(ra[last_i:i], rb[last_j:j]):
                yield block
        last_i = i
        last_j = j


def diff_gen(a, b, opcode_gen):
    """Convert a sequence of SequenceMatcher opcodes to
    unified diff-like output
    """

    def _iter():
        for op, i1, i2, j1, j2 in opcode_gen:
            if op == 'equal':
                yield '  ', Region(a, i1, i2)
            if op in ('delete', 'replace'):
                yield '- ', Region(a, i1, i2)
            if op in ('replace', 'insert'):
                yield '+ ', Region(b, j1, j2)

    for prefix, rgn in _iter():
        for line in rgn:
            yield prefix, line


def unified_diff(a, b, fromfile='', tofile='', fromfiledate='', tofiledate='',
                 n=3, lineterm='\n'):
    started = False
    for group in SequenceMatcher(None, a, b).get_grouped_opcodes(n):
        if not started:
            yield '--- %s %s%s' % (fromfile, fromfiledate, lineterm)
            yield '+++ %s %s%s' % (tofile, tofiledate, lineterm)
            started = True
        i1, i2, j1, j2 = group[0][1], group[-1][2], group[0][3], group[-1][4]
        yield "@@ -%d,%d +%d,%d @@%s" % (i1+1, i2-i1, j1+1, j2-j1, lineterm)
        for tag, i1, i2, j1, j2 in group:
            if tag == 'equal':
                for line in a[i1:i2]:
                    yield ' '+line
                continue
            if tag == 'replace' or tag == 'delete':
                for line in a[i1:i2]:
                    yield '-'+line
            if tag == 'replace' or tag == 'insert':
                for line in b[j1:j2]:
                    yield '+'+line


class SequenceMatcher(difflib.SequenceMatcher):
    def get_matching_blocks(self):
        """Uses patience diff algorithm to find matching blocks."""
        if self.matching_blocks is not None:
            return self.matching_blocks
        matching_blocks = list(match_core(self.a, self.b))
        matching_blocks.append((len(self.a), len(self.b), 0))
        self.matching_blocks = sorted(matching_blocks)
        return self.matching_blocks


def test():  # pragma no cover
    if len(sys.argv) == 3:
        fn_a = sys.argv[1]
        fn_b = sys.argv[2]
    else:
        fn_a = 'a.c'
        fn_b = 'b.c'
    a = open(fn_a).readlines()
    b = open(fn_b).readlines()
    # print '====', fn_a
    # sys.stdout.write(''.join(a))
    # print '====', fn_b
    # sys.stdout.write(''.join(b))
    sm = SequenceMatcher(None, a, b)
    # print 'Patience opcodes:', sm.get_opcodes()
    print ''.join(unified_diff(a, b))  #pragma:printok
    # for prefix, line in diff_gen(a, b, sm.get_opcodes()):
    #     sys.stdout.write(''.join((prefix, line)))
    # sm = difflib.SequenceMatcher(None, a, b)
    # print 'Difflib opcodes:', sm.get_opcodes()
    # for prefix, line in diff_gen(a, b, sm.get_opcodes()):
    #     sys.stdout.write(''.join((prefix, line)))


def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if not s1:
        return len(s2)

    previous_row = xrange(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # j+1 instead of j bc previous_row is one character longer
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


class DictDiffCalculator(object):

    def __init__(self, a, b):
        assert isinstance(a, dict) and isinstance(b, dict), \
            "both arguments must be dictionaries"
        self.a = a
        self.b = b
        self._changed_keys_set = set()

    # public api methods
    def get_changed_keys(self):
        """
        Slower, recursively checks entire dict structure and returns a set
        of key names that have changed.

        e.g. {'some_list', 'some_list.0', 'some_list.0.a_dict_key'}
        """
        self._changed_keys_set.clear()
        self._calculate_changed_keys(self.a, self.b)
        return set(['.'.join(k) for k in self._changed_keys_set if k])

    def get_has_key_changed(self, *key_path):
        """
        Faster, but checks only one key path at a time.

        returns True if changed else False
        """
        # get starting point
        x = self.a
        y = self.b
        key_stack = list(key_path)
        while len(key_stack):
            key = key_stack.pop(0)
            if isinstance(x, dict) and isinstance(y, dict):
                try:
                    x = x[key]
                    y = y[key]
                except KeyError:
                    return True
                else:
                    continue
            elif isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
                try:
                    x = x[int(key)]
                    y = y[int(key)]
                except IndexError:
                    return True
                else:
                    continue
        # walk the rest of it until a difference is found
        return self._walk_until_diff(x, y)

    # internal processing methods
    @staticmethod
    def _iter_path_items_from_path(key_path):
        for i in range(len(key_path)):
            yield tuple(key_path[:i + 1])

    @staticmethod
    def _iterable_plus_args(iterable, *args):
        for x in iterable:
            yield x
        for x in args:
            yield x

    def _walk_until_diff(self, a, b):
        """
        return True if diff is found else False
        """
        if isinstance(a, dict) and isinstance(b, dict):
            for key in set(a).union(b):
                if key in a and key in b:
                    x = a[key]
                    y = b[key]
                    if self._walk_until_diff(x, y):
                        continue
                    if x == y:
                        continue
                return True
        elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            if len(a) != len(b):
                return True
            for i in range(len(a)):
                if len(a)-1 >= i and len(b)-1 >= i:
                    x = a[i]
                    y = b[i]
                    if self._walk_until_diff(x, y):
                        continue
                    if x == y:
                        continue
                return True
        return not a == b

    def _walk_for_changed(self, x, y, key_path):
        if isinstance(x, dict) and isinstance(y, dict):
            self._calculate_changed_keys(x, y, *key_path)
            return True
        elif isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
            self._calculate_changed_indexes(x, y, *key_path)
            return True
        return False

    def _add_path_items_to_changed_keys(self, key_path):
        self._changed_keys_set.update(self._iter_path_items_from_path(key_path))

    def _calculate_changed_keys(self, a, b, *key_path):
        assert isinstance(a, dict)
        assert isinstance(b, dict)
        for key in set(a).union(b):
            new_key_path = list(self._iterable_plus_args(key_path, key))
            if key in a and key in b:
                x = a[key]
                y = b[key]
                if self._walk_for_changed(x, y, new_key_path):
                    continue
                if x == y:
                    continue
            self._add_path_items_to_changed_keys(new_key_path)

    def _calculate_changed_indexes(self, a, b, *key_path):
        assert isinstance(a, (list, tuple))
        assert isinstance(b, (list, tuple))
        for i in range(max(len(a), len(b))):
            new_key_path = list(self._iterable_plus_args(key_path, str(i)))
            if len(a)-1 >= i and len(b)-1 >= i:
                x = a[i]
                y = b[i]
                if self._walk_for_changed(x, y, new_key_path):
                    continue
                if x == y:
                    continue
            self._add_path_items_to_changed_keys(new_key_path)


def get_dict_diff_changed_keys(a, b):
    return DictDiffCalculator(a, b).get_changed_keys()


def get_dict_diff_have_keys_changed(a, b, *key_paths):
    """
    example:

        to test if `options.name` or `acl` or `labels.1.title` have changed:

        >>> self.have_keys_changed(a, b,
                                   ('options', 'name'),
                                   ('acl',),
                                   ('labels', 1, 'title')
                                   )

    :param key_paths: a tuple of tuples to test sequentially. If any have
                      changed in the given state, return True else False.
    """
    dict_diff = DictDiffCalculator(a, b)
    for key_path in key_paths:
        if dict_diff.get_has_key_changed(key_path):
            return True
    return False


if __name__ == '__main__':  # pragma no cover
    test()
