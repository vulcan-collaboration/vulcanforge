$(function () {
    $('.artifact-labels-field').each(function() {
        var $this = $(this),
            options = JSON.parse($this.attr('data-availabletags'));
        $this.tagit({
            availableTags: options,
            singleField: true,
            removeConfirmation: true,
            autocomplete: {
                delay: 0, minLength: 1
            },
            showAutocompleteOnFocus: true
        });
    });
});
