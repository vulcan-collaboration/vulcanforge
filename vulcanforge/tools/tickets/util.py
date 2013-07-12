
class changelog(object):
    """
    A dict-like object which keeps log about what keys have been changed.

    >>> c = changelog()
    >>> c['foo'] = 'bar'
    >>> c['bar'] = 'baraban'
    >>> c.get_changed()
    []
    >>> c['bar'] = 'drums'
    >>> c.get_changed()
    [('bar', ('baraban', 'drums'))]

    The .get_changed() lists key in the same order they were added to the
    changelog:

    >>> c['foo'] = 'quux'
    >>> c.get_changed()
    [('foo', ('bar', 'quux')), ('bar', ('baraban', 'drums'))]

    When the key is set multiple times it still compares to the value that was
    set first.
    If changed value equals to the value set first time it is not included.

    >>> c['foo'] = 'bar'
    >>> c['bar'] = 'koleso'
    >>> c.get_changed()
    [('bar', ('baraban', 'koleso'))]

    """
    def __init__(self):
        self.keys = []  # to track insertion order
        self.originals = {}
        self.data = {}

    def __setitem__(self, key, value):
        if key not in self.keys:
            self.keys.append(key)
        if key not in self.originals:
            self.originals[key] = value
        self.data[key] = value

    def get_changed(self):
        t = []
        for key in self.keys:
            if key in self.originals:
                orig_value = self.originals[key]
                curr_value = self.data[key]
                if not orig_value == curr_value:
                    t.append((key, (orig_value, curr_value)))
        return t

