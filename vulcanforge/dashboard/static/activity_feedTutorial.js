$(document).ready(function () {
    var $descriptionHolder = $('<div/>').append($('<br/>'));
    $('<p/>', {
        text: 'The Activity Feed provides a powerful way to examine user activity in your projects, and their tools, as a time-ordered sequence of actions.'
    }).appendTo($descriptionHolder);

    $('<p/>', {
        text: "It's organized into three main areas: the Filter List at left, the Timeline below, and the Activity List below that.  Place your mouse pointer over these areas while this tutorial is showing to receive more information about how they work."
    }).appendTo($descriptionHolder);

    $('<p/>', {
        text: 'The Timeline enables you to examine activity during particular intervals of time.  With the Filter List, you can focus on activity in specific projects and tools.  The Activity List allows you to examine individual user actions and navigate directly to their related project, tool, and artifact.'
    }).appendTo($descriptionHolder);

    $('<p/>', {
        text: 'The Activity Feed has been recently updated to indicate, in the Filter List, which project tools contain new activity since the last time you accessed that tool.  The Filter List also conveniently now presents projects with the most unseen activity to the top.'
    }).appendTo($descriptionHolder);

    var tutorialConfig = {
        statePersistenceApiUrl: '/auth/prefs/state/',
        pageId: 'activityFeed',
        containerElement: $('#tutorialHolder'),
        title: 'Activity Feed',
        toolTipped: true,
        description: $descriptionHolder,
        elements: {

            // global elements

            // page specific elements

            '#filter-list': {
                title: "Filter List",
                content: "The Filter List presents each of your projects and each project tool.  The checkboxes next to them control whether their related items are presented in the Timeline and Activity List.  Use the project checkboxes to select, or unselect, all of the project's tools.  In the heading of the panel are controls to select All, None, or New activity.  The settings in this panel are preserved between visits.",
                position: "center"
            },

            '#notification-list': {
                title: "Activity List",
                content: "The Activity List presents the individual user actions on projects and their tools.  Each item may identify the user performing the action and provides additional information about the action, which can be expanded by clicking on the triangle-shaped icon.",
                position: "top"
            },
            
            '#notification-stats': {
                title: "Timeline",
                content: "The TImeline presents activity relative to time.  It consists of upper and lower parts.  Drag select some region in the upper part to zoom in.  Whenever you have zoomed, the lower part shows where you are in the overall timeline.  Drag select the lower part to zoom out, or just click it to zoom out completely.",
                position: "center"               
            }
        }
    };

    var tutorial = new $vf.Tutorial(tutorialConfig);
});
