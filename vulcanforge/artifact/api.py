import re

from pylons import tmpl_context as c
from vulcanforge.artifact.model import Shortlink, ArtifactReference


class ArtifactAPI(object):
    """
    Global entry point for artifact-related API, most notably for artifact
    references. Mounted on pylons.app_globals as artifact

    """
    # regex to extract shortlinks from markdown
    SHORTLINK_RE = re.compile(
        r'''(?<![\[])\[(  # bracket, not double bracket
        (([^\]]*?):)?     # project part (optional)
        (([^\]]*?):)?     # app part (optional)
        ([^\]]+)          # artifact part
        )\]               # end bracket
        ''', re.VERBOSE)

    # regex for parsing extracted links
    PARSE_SHORTLINK_RE = re.compile(r'\s*\[([^\]\[]*)]\s*')

    # patterns for looking up artifacts by index_id when no ArtifactReference
    # document yet exists, or the artifact is not persisted (repo objects)
    INDEX_ID_EPHEMERALS = {}

    # patterns for shortlinks
    SHORTLINK_EPHERMERALS = {}

    def get_artifact_by_index_id(self, index_id):
        artifact = None

        # find ephemerals
        for regex, func in self.INDEX_ID_EPHEMERALS.iteritems():
            match = regex.match(index_id)
            if match:
                artifact = func(index_id, match)

        # standard approach
        if artifact is None:
            aref = ArtifactReference.query.get(_id=index_id)
            if aref:
                artifact = aref.artifact

        return artifact

    def parse_shortlink(self, link):
        """Parse a shortlink into its project/app/artifact parts"""
        link_bracket_match = self.PARSE_SHORTLINK_RE.match(link)
        if link_bracket_match:
            link = link_bracket_match.group(1)

        parts = link.split(':', 2)
        p_shortname = None
        if hasattr(c, 'project'):
            p_shortname = getattr(c.project, 'shortname', None)
        if len(parts) == 3:
            return {
                'project': parts[0],
                'app': parts[1],
                'artifact': parts[2]
            }
        elif len(parts) == 2:
            return {
                'project': p_shortname,
                'app': parts[0],
                'artifact': parts[1]
            }
        elif len(parts) == 1:
            return {
                'project': p_shortname,
                'app': None,
                'artifact': parts[0]
            }
        else:
            return None

    def find_shortlink_refs(self, text, **kw):
        ref_ids = []
        # TODO: include markdown extensions in vulcanforge then uncomment
        # fcp = FencedCodeProcessor()
        # converted = fcp.run(text.split('\n'))
        converted = text.split('\n')
        for line in converted:
            if not line.startswith('    '):
                ref_ids.extend(
                    self.get_ref_id_by_shortlink(alink.group(1), **kw)
                    for alink in self.SHORTLINK_RE.finditer(line) if alink
                )
        return ref_ids

    def get_artifact_by_shortlink(self, shortlink):
        parsed = self.parse_shortlink(shortlink)
        if parsed:
            artifact = None

            # standard method
            shortlink = Shortlink.get_from_parsed(parsed)
            if shortlink:
                artifact = shortlink.ref.artifact

            # try ephemerals
            if not artifact:
                for regex, func in self.SHORTLINK_EPHERMERALS.iteritems():
                    match = regex.match(parsed['artifact'])
                    if match:
                        artifact = func['artifact'](parsed, match)

            return artifact

    def get_ref_id_by_shortlink(self, shortlink, upsert=True):
        parsed = self.parse_shortlink(shortlink)
        if parsed:
            ref_id = None

            # standard method
            shortlink = Shortlink.get_from_parsed(parsed)
            if shortlink:
                ref_id = shortlink.ref_id

            # try ephemerals
            if ref_id is None:
                for regex, func in self.SHORTLINK_EPHERMERALS.iteritems():
                    match = regex.match(parsed['artifact'])
                    if match:
                        ref_id = func['ref_id'](parsed, match, upsert=upsert)

            return ref_id
