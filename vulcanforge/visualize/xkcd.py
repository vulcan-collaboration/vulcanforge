# coding=utf-8
import re
import os

from vulcanforge.visualize.base import (
    SingleFileProcessor,
    OnDemandProcessingVisualizer
)
from vulcanforge.visualize.syntax import SyntaxContent


class XKCDSubstitutionProcessor(SingleFileProcessor):
    """See http://xkcd.com/1288/"""

    CONVERSION_TABLE = {
        'witnesses': 'these dudes I know',
        'allegedly': 'kinda probably',
        'new study': 'tumblr post',
        'rebuild': 'avenge',
        'space': 'spaaace',
        'google glass': 'virtual boy',
        'smartphone': u'pokédex',
        'electric': 'atomic',
        'senator': 'elf-lord',
        'car': 'cat',
        'election': 'eating contest',
        'congressional leaders': 'river spirits',
        'homeland security': 'homestar runner',
        'could not be reached for comment': 'is guilty and everyone knows it'
    }

    @property
    def processed_filename(self):
        basefile, _ = os.path.splitext(os.path.basename(self.artifact.url()))
        return basefile + '.xkcd'

    def run(self):
        txt = self.artifact.read()
        for pattern, sub in self.CONVERSION_TABLE.items():
            txt = re.sub(pattern, sub, txt, flags=re.IGNORECASE)
        self.result_file.set_contents_from_string(txt)


class XKCDVisualizer(OnDemandProcessingVisualizer):
    default_options = {
        "name": "XKCD Visualizer",
        "extensions": [],
        "processing_mime_types": ['text/'],
        "processing_extensions": ['*']
    }
    content_widget = SyntaxContent()

    def process_artifact(self, artifact):
        processor = XKCDSubstitutionProcessor(artifact, self)
        processor.full_run()
