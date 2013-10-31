from vulcanforge.visualize.base import BaseVisualizer
from vulcanforge.visualize.widgets import BaseContentWidget


class ImageContent(BaseContentWidget):
    template = 'visualize/widgets/image.html'


class ImageVisualizer(BaseVisualizer):
    content_widget = ImageContent()
    default_options = {
        "name": "Image Visualizer",
        "mime_types": ['^image'],
        "extensions": ['*'],
        "description": "Visualizes images, with nifty zoom functionality",
        "icon": "FILE_IMAGE",
        "priority": -1
    }