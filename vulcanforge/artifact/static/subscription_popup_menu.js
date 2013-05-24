(function ($) {
    $vf.afterInit(function () {
        $('.subscription-popup-button').each(function () {
            var $content = $(this).next('.subscription-popup-content');
            $content.remove();
            $(this).qtip({
                content: $content,
                position: {
                    at: 'bottom middle', // Position the tooltip above the link
                    my: 'top right',
                    viewport: $(window), // Keep the tooltip on-screen at all times
                    effect: false // Disable positioning animation
                },
                show: {
                    event: 'click',
                    solo: true // Only show one tooltip at a time
                },
                hide: 'unfocus',
                style: {
                    classes: 'tooltip subscription-popup-menu',
                    width: '300px'
                }
            });
        });
    });
}(jQuery));
