$(document).ready(function () {

    var tutorialConfig = {
        containerElement: $('#tutorialHolder'),

        title: 'Manage your project',
        description: 'The project admin interface allows administrators ' +
            'to customize their project\'s users, metadata, & tools.',

        elements: {

            // sidebar menu items

            '#sidebarmenu-item-metadata': {
                title: 'Metadata',
                content: 'Manage project name, icon, summary, home ' +
                    'page or delete project.',
                position: 'left'
            },

            '#sidebarmenu-item-screenshots': {
                title: 'Screenshots',
                content: 'Manage project screenshots.',
                position: 'left'
            },

            '#sidebarmenu-item-categorization': {
                title: 'Categorization',
                content: 'Manage project categorization.',
                position: 'left'
            },

            '#sidebarmenu-item-permissions': {
                title: 'Permissions',
                content: 'Assign permissions to each project role.',
                position: 'left'
            },

            '#sidebarmenu-item-tools': {
                title: 'Tools',
                content: 'Add, delete, and manage project tools ' +
                    '(wikis, forums, repositories, etc.)',
                position: 'left'
            },

            '#sidebarmenu-item-usergroups': {
                title: 'Usergroups',
                content: 'Define project user groups and assign users ' +
                    'to them.',
                position: 'left'
            },

            // page content items

            '#admin-section-setup': {
                title: 'Project setup',
                content: 'Manage your project\'s metadata and homepage ' +
                    'wiki.',
                position: 'top'
            },

            '#admin-section-docs': {
                title: 'Documentation',
                content: 'Edit your project\'s documentation wiki.',
                position: 'top'
            },

            '#admin-section-repositories': {
                title: 'Version Control Systems',
                content: 'Collaborate by working in shared repositories, ' +
                    'manage them here and on the Tools page.',
                position: 'top'
            },

            '#admin-section-manage': {
                title: 'Ticket Trackers',
                content: 'Track issues, bugs, assigned tasks, or ' +
                    'anything you want with the ticketing tool. You ' +
                    'can have multiple ticket trackers on one project.',
                position: 'top'
            },

            '#admin-section-forums': {
                title: 'Discussion Forums',
                content: 'Foster collaborative discussions with ' +
                    'integrated discussion forums.',
                position: 'top'
            },

            '#admin-section-components': {
                title: 'VehicleForge Component Exchange',
                content: 'The VehicleForge Component Exchange allows ' +
                    'you to publish and discover new components.',
                position: 'top'
            }

        }
    };

    var tutorial = new $vf.Tutorial(tutorialConfig);
});
