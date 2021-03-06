import os
import logging

import requests
from requests.exceptions import Timeout
from urlparse import urlparse
from pylons import tmpl_context as c, app_globals as g
from BeautifulSoup import BeautifulSoup

from vulcanforge.auth.requester import ForgeRequester
from vulcanforge.tools.wiki.model import Page

LOG = logging.getLogger(__name__)


class BrokenLinkFinder(object):

    def __init__(self, user=None, follow_redirects=2):
        self.requester = ForgeRequester()
        if user:
            self.requester.set_user(user)
        self.user = user
        self.follow_redirects = follow_redirects

    def make_request_for_page(self, url, page, follow_redirects=None):
        if follow_redirects is None:
            follow_redirects = self.follow_redirects
        parsed = urlparse(url)
        request_kwargs = {"stream": True, "allow_redirects": False}
        if not parsed.netloc:
            path = parsed.path
            if not path.startswith('/'):
                path = os.path.normpath(os.path.join(page.url(), path))
            url = g.base_url + path
            if parsed.query:
                url += '?' + parsed.query
            request_func = self.requester.get
        else:
            domain = parsed.scheme + '://' + parsed.netloc
            if domain == g.base_url:
                request_func = self.requester.get
            elif self.user and domain == g.base_s3_url.rstrip('/'):
                request_func = requests.get
            else:
                request_func = requests.get
        resp = request_func(url, **request_kwargs)
        LOG.info("Request to %s returned %s", url, resp.status_code)
        if follow_redirects and resp.status_code == 302:
            resp = self.make_request_for_page(
                resp.headers["location"], page, follow_redirects - 1)
        return resp

    def find_broken_links_by_page(self, page):
        """Yields json with link, html str, status"""
        html = page.get_rendered_html()
        try:
            soup = BeautifulSoup(html)
        except Exception:
            LOG.warn("Error parsing html in page %s", page.url())
            raise StopIteration
        for img in soup.findAll("img"):
            src = img.get("src")
            if src:
                try:
                    resp = self.make_request_for_page(src, page)
                except Timeout:
                    yield {
                        "link": src,
                        "html": str(img),
                        "msg": "Request timed out"
                    }
                except Exception as e:
                    yield {
                        "link": src,
                        "html": str(img),
                        "msg": "Unknown Error: {}".format(str(e))
                    }
                if resp.status_code != 200:
                    yield {
                        "link": src,
                        "html": str(img),
                        "msg": "HTML Request Failure Response {}".format(
                            resp.status_code)
                    }
            else:
                yield {
                    "link": None,
                    "html": str(img),
                    "msg": "Image without src attribute"
                }

        for a in soup.findAll('a'):
            href = a.get("href")
            if href:
                try:
                    resp = self.make_request_for_page(href, page)
                except Timeout:
                    yield {
                        "link": href,
                        "html": str(a),
                        "msg": "Request timed out"
                    }
                except Exception as e:
                    yield {
                        "link": href,
                        "html": str(a),
                        "msg": "Unknown Error: {}".format(str(e))
                    }
                if resp.status_code != 200:
                    yield {
                        "link": href,
                        "html": str(a),
                        "msg": "HTML Request Failure Response {}".format(
                            resp.status_code)
                    }

    def find_broken_links_by_app(self, app_config_id=None):
        """Yields triplets of link, html str, page"""
        if app_config_id is None:
            app_config_id = c.app.config._id

        query = {
            "app_config_id": app_config_id,
            "deleted": False
        }
        # keep all() below to prevent timeout
        for page in Page.query.find(query).all():
            LOG.debug("Searching for links for %s", page.url())
            for err_json in self.find_broken_links_by_page(page):
                err_json["page"] = page
                yield err_json
