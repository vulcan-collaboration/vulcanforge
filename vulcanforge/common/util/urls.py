# -*- coding: utf-8 -*-

"""
urls

@author: U{tannern<tannern@gmail.com>}
"""
import urlparse


def rebase_url(url, old_base, new_base):
    """
    expects a relative url, and 2 absolute bases

    examples:

    >>> rebase_url('a.jpg', '/old/a.html', '/new/b.html')
    u'../old/a.jpg'
    >>> rebase_url('./a.jpg', '/old/a.html', '/new/b.html')
    u'../old/a.jpg'
    >>> rebase_url('../other/a.jpg', '/old/a.html', '/new/b.html')
    u'../other/a.jpg'
    >>> rebase_url('../new/a.jpg', '/old/a.html', '/new/b.html')
    u'a.jpg'
    """
    old_url = urlparse.urljoin(old_base, url)
    return absolute_to_relative_url(old_url, new_base)


def absolute_to_relative_url(url, base):
    """
    expects 2 absolute URLs

    examples:

    >>> absolute_to_relative_url('/a/b/c.jpg', '/a/b/')
    u'c.jpg'
    >>> absolute_to_relative_url('/a/b/c.jpg', '/a/d/')
    u'../b/c.jpg'
    >>> absolute_to_relative_url('/a/b/c.jpg', '/a')
    u'a/b/c.jpg'
    >>> absolute_to_relative_url('/a/b/c.jpg', '/a/')
    u'b/c.jpg'
    >>> absolute_to_relative_url('/a/b/c.jpg', '/')
    u'a/b/c.jpg'
    """
    url_parts = url.split('/')
    base_parts = base.split('/')
    base_parts.pop(-1)
    for old_part, new_part in zip(url_parts, base_parts):
        if old_part == new_part:
            url_parts.pop(0)
            base_parts.pop(0)
    new_parts = ['..'] * len(base_parts) + url_parts
    return u'/'.join(new_parts)
