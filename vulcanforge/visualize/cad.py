from vulcanforge.visualize.base import BaseVisualizer
from vulcanforge.visualize.widgets import BaseContentWidget


class CADContent(BaseContentWidget):
    template = 'visualize/widgets/cad.html'


class CADVisualizer(BaseVisualizer):
    content_widget = CADContent()
    default_options = {
        "name": "CAD Visualizer",
        "mime_types": ['^application/step'],
        "priority": 5,
        "icon": "FILE_IMAGE"
    }