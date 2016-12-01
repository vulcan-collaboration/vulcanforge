/**
 * Created by papszi on 8/23/16.
 */

$(document).ready(function () {

    var $descriptionHolder = $('<div/>');
    $('<p/>', {
        text: 'This tool helps you to get involved in discussions, create new ' +
        'ones and search existing ones. It supports two levels of hierarchy: ' +
        'forums and topics within them.'
    }).appendTo($descriptionHolder);

    var $descList = $('<ul/>').appendTo($descriptionHolder);
    $('<li>', {
        text: 'Users with admin permission can create forums which in turn can ' +
        'contain specific topics.'
    }).appendTo($descList);
    $('<li>', {
        text: 'Users with post permission can create topics within a forum ' +
        'and post comments.'
    }).appendTo($descList);
    $('<li>', {
        text: 'Users are also allowed to attach files to their comments that ' +
        'should not exceed 20MB in size.'
    }).appendTo($descList);

    $('<p/>', {
        text: 'While this tutorial is showing, you can place your mouse ' +
        'pointer over items in the sidebar to the right to ' +
        'receive more information about how they work.'
    }).appendTo($descriptionHolder);

    /*
     */
    var tutorialConfig = {
        statePersistenceApiUrl: '/auth/prefs/state/',
        pageId: 'forums/general',
        containerElement: $('#tutorialHolder'),
        title: 'Discussions',
        toolTipped: true,
        description: $descriptionHolder,
        elements: {

            // global elements
            '#keyword-search-form': {
                title: 'Keyword search',
                content: 'Platform-wide search for matching text fragments ' +
                'across components, projects, designers and competitions.'
            },
            '.referenceBin' : {
                title: "Link Bin",
                content: "The Link Bin stores references to artifacts and " +
                "objects on VulcanForge for use in making cross-references.",
                position: "left"
            },

            // tool specific elements
            '#sidebarmenu-item-show-all': {
                title: "Show Forums",
                content: "Provides an overview of all the forums available.",
                position: "left"
            },
            '#sidebarmenu-item-add-forum': {
                title: "Add new forum",
                content: "Takes you to a page for creating a new " +
                "forum. Displayed for users with admin permission only.",
                position: "left"
            },
            '#sidebarmenu-item-admin-forums': {
                title: "Administer Forums",
                content: "Takes you to a page where you can edit and delete " +
                "forums. Displayed for users with admin permission only.",
                position: "left"
            },
            '#sidebarmenu-item-show-topics': {
                title: "Show Topics",
                content: "Provides an overview of all the topics within this forum.",
                position: "left"
            },
            '#sidebarmenu-item-create-topic': {
                title: "Create Topic",
                content: "Takes you to a page for creating a new topic.",
                position: "left"
            }

        }
    };

    var tutorial = new $vf.Tutorial(tutorialConfig);
});
