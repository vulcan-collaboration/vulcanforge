$(document).ready(function () {

    var tutorialConfig = {
        containerElement: $('#tutorialHolder'),

        //title: 'Welcome to VehicleForge!',
        //description: 'The forge is probably new to you, so here\'s some info on the features and services of your Dashboard&mdash;the hub of your work on VehicleForge. This interactive tutorial gives help when you point to key elements on the page. Point to this panel to reveal all the sensitive screen-areas.',

        title: "The User Dashboard",
        description: 'The Dashboard is your starting point on ' +
            'VehicleForge. From here you can keep track of what is ' +
            'going on in all of the projects you are involved in ' +
            'or subscribe to. While this tutorial is active, you ' +
            'can move the mouse pointer over areas of the page to ' +
            'get information about them. ',

        elements: {

            // global elements

            '#headerLogoHolder' : {
                title: 'VehicleForge front page',
                content: 'You can reach the VehicleForge front page at any time by clicking on the logo.',
                position: "right"
            },

            '#discoverComponents': {
                title: 'Discover components',
                content: 'Search and browse for reusable components in the VehicleForge Component Exchange.'
            },

            '#discoverProjects': {
                title: 'Discover projects',
                content: 'Browse the projects hosted at VehicleForge.'
            },

            '#discoverDesigners': {
                title: 'Designers',
                content: 'Designers can customize and publish a public portfolio page to showcase their work.%%UC%%'
            },

            '#discoverCompetitions': {
                title: 'Competitions',
                content: 'You will be able to find here everything about design challenges: announcements, results and designs.%%UC%%'
            },

            '#my-portfolio': {
                title: 'Your Portfolio',
                content: 'This will be the place where you can customize/edit your own portfolio page.%%UC%%'
            },

            '#my-dashboard': {
                title: 'Your Dashboard (this page)',
                content: 'This is the landing page where you arrive after logging in to vehicleforge.mil. Here you can monitor activity and engage with other designers.'
            },

            '#my-settings': {
                title: 'Settings',
                content: 'Basic user preferences and notification setting here. The structure and the content of this page will be merging with the Dashboard.'
            },

            '#keyword-search-form': {
                title: 'Keyword search',
                content: 'Platform-wide search for matching text fragments across components, projects, designers and competitions.'
            },

            '#workspace-tab-bar-container': {
                title: 'Bookmarks',
                content: 'The bookmark bar lets you to create and store shortcuts to any page on VehicleForge, keeping the things you use frequently only one click away.',
                position: 'center'
            },

            '#footer': {
                title: 'Footer',
                content: 'The footer will give you access to general information in the form of static pages.%%UC%%',
                position: 'top'
            },

            '.referenceBin' : {
                title: "Link Bin",
                content: "The Link Bin stores references to artifacts and objects on VehicleForge for use in making cross-references.",
                position: "left"
            },

            // page-specific elememts

            '#messageComposer': {
                title: 'Message Composer',
                content: 'To send messages from the Dashboard&mdash;to individuals, to projects, or to watchers&mdash;just start typing in the area.'
            },

            '#myProjectsContainer': {
                title: 'Project List',
                content: 'All of your projects are just one click away.',
                position: 'left'
            },

            '#createProject' : {
                title: "Create A Project",
                content: "Start your own design project here."
            },

            '#messageStreamHolder' : {
                title: "Messages and Notifications",
                content: "The Dashboard provides notifications of all activity in your projects and all your received messages as a consolidated information stream here.",
                position: 'top'
            },

            '#loadOlderMessages' : {
                title: "Older messages",
                content: "Your messages and notifications are kept until you delete them.  Retrieve older items by clicking here.",
                position: "top"
            },

            '#channelListContainer' : {
                title: "Channels",
                content: "Channels are your subscriptions to information on VehicleForge, whether about projects, people, or groups.  This area shows the current messages on your subscribed channels, supports filtering, and allows you to tune into to more channels.",
                position: "right"
            }
        }
    }

    var tutorial = new $vf.Tutorial(tutorialConfig);
});