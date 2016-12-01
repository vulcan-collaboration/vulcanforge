$(document).ready(function () {

    var $descriptionHolder = $('<div/>').append($('<br/>'));
    $('<p/>', {
        text: 'Generally you can explore the folders and download content from them. ' +
            'In certain cases when a visualizer is available you can view file content in the browser.'
    }).appendTo($descriptionHolder);
    $('<p/>', {
        text: 'With write access you can create folders and upload files into them. ' +
            'Things to know about adding files: '
        }).appendTo($descriptionHolder);
    var $descList = $('<ul/>').appendTo($descriptionHolder);
    $('<li>', {text: 'The UI supports "drag and drop" style file upload'}).appendTo($descList);
    $('<li>', {text: 'There is no limit on file size or on the number of files added'}).appendTo($descList);
    $('<li>', {text: 'File uploads are resumable: if the connection is interrupted or the session times out just add the same files again.'}).appendTo($descList);

    $('<p/>', {
        text: 'This tool now also supports moving files from one folder to another and browsing the content of ZIP files. ' +
            'You can only select and move files from one folder at a time, selecting files in a different folder resets the selection.'
    }).appendTo($descriptionHolder);

    var $descList2 = $('<ul/>').appendTo($descriptionHolder);
    $('<li>', {text: 'To select files: right click on them and use the context menu or use the Ctrl and Shift keys in conjunction with mouse clicks.'}).appendTo($descList2);
    $('<li>', {text: 'To paste files in the current folder: right click on the header and select paste from the context menu.'}).appendTo($descList2);
    $('<li>', {text: 'To paste files in a contained folder: right click on the folder ine the listing and select paste from the context menu.'}).appendTo($descList2);

    /*
    */
    var tutorialConfig = {
        statePersistenceApiUrl: '/auth/prefs/state/',
        pageId: 'downloadsTool',
        containerElement: $('#tutorialHolder'),
        title: 'Organize and access your files',
        toolTipped: true,
        description: $descriptionHolder,
        elements: {

            // global elements

            '#keyword-search-form': {
                title: 'Keyword search',
                content: 'Platform-wide search for matching text fragments across components, projects, designers and competitions.'
            },
            '.referenceBin' : {
                title: "Link Bin",
                content: "The Link Bin stores references to artifacts and objects on VulcanForge for use in making cross-references.",
                position: "left"
            },

            // page specific elements
            '.vf-filebrowser-list-container': {
                title: "Folder Content",
                content: "Area where content is listed. Besides making navigation possible it provides shortcuts for deleting, downloading, sharing and moving files.",
                position: "top"
            }


        }
    };

    var tutorial = new $vf.Tutorial(tutorialConfig);
});
