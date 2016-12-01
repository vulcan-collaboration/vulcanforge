import os
import logging
import subprocess
import tempfile


LOG = logging.getLogger(__name__)


from vulcanforge.visualize.base import (
    SingleFileProcessor,
    OnUploadProcessingVisualizer
    )
from vulcanforge.visualize.pdf import PDFContent

LOG = logging.getLogger(__name__)


class PresentationProcessor(SingleFileProcessor):
    """Converts MS and Open Office files to pdf for visualization"""

    @property
    def processed_filename(self):
        basefile, _ = os.path.splitext(os.path.basename(self.artifact.url()))
        if hasattr(self.artifact, '_id'):
            return str(self.artifact._id) + '.pdf'
        else:
            return basefile + '.pdf'

    def run(self):
        input_file = None
        output_file = None
        def delete_callback(wrote, total):
            if wrote == total:
                if input_file is not None and os.path.exists(input_file.name):
                    os.remove(input_file.name)
                if output_file is not None and os.path.exists(output_file.name):
                    os.remove(output_file.name)

        _, ext = os.path.splitext(os.path.basename(self.artifact.url()))

        input_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        input_file.write(self.artifact.read())
        input_file.flush()
        input_file.close()
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        attempts = 0

        while True:
            try:
                # Making sure a listener is running in the background
                os.system('unoconv -l &')
                subprocess.check_call(
                    ['unoconv', '-f', 'pdf', '-d', 'presentation', '-o', output_file.name, input_file.name])
                self.result_file.set_contents_from_file(output_file, cb=delete_callback)
                output_file.close()
                break
            except Exception as exc:
                attempts += 1
                if attempts == 3:
                    output_file.close()
                    delete_callback(0, 0)
                    raise exc


class PresentationVisualizer(OnUploadProcessingVisualizer):
    default_options = {
        "name": "Presentation Visualizer",
        "mime_types": [
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.ms-powerpoint.presentation.macroenabled.12',
            'application/vnd.openxmlformats-officedocument.presentationml.slideshow',
            'application/vnd.ms-powerpoint.slideshow.macroenabled.12',
            'application/vnd.openxmlformats-officedocument.presentationml.template',
            'application/vnd.ms-powerpoint.template.macroenabled.12',
            'application/vnd.oasis.opendocument.presentation',
            'application/vnd.oasis.opendocument.presentation-template'
        ],
        "description": "Visualizes MS and Open Office presentations by converting to PDF",
        "extensions": ['.*[.]ppt',
                       '.*[.]pptx',
                       '.*[.]pptm',
                       '.*[.]pps',
                       '.*[.]ppsx',
                       '.*[.]pot',
                       '.*[.]potx',
                       '.*[.]potm',
                       '.*[.]odp',
                       '.*[.]otp',
                       '.*[.]fodp'],
        "processing_mime_types": [
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.ms-powerpoint.presentation.macroenabled.12',
            'application/vnd.openxmlformats-officedocument.presentationml.slideshow',
            'application/vnd.ms-powerpoint.slideshow.macroenabled.12',
            'application/vnd.openxmlformats-officedocument.presentationml.template',
            'application/vnd.ms-powerpoint.template.macroenabled.12',
            'application/vnd.oasis.opendocument.presentation',
            'application/vnd.oasis.opendocument.presentation-template'
        ],
        "processing_extensions": ['.*[.]ppt',
                                  '.*[.]pptx',
                                  '.*[.]pptm',
                                  '.*[.]pps',
                                  '.*[.]ppsx',
                                  '.*[.]pot',
                                  '.*[.]potx',
                                  '.*[.]potm',
                                  '.*[.]odp',
                                  '.*[.]otp',
                                  '.*[.]fodp'],
        "icon": "FILE_TEXT"
    }
    content_widget = PDFContent()

    def process_artifact(self, artifact):
        processor = PresentationProcessor(artifact, self)
        processor.full_run()
