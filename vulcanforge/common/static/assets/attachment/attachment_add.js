/*global window*/

/*
 * Initializing attachment_add widget.
 *
 * @author Naba Bana
 */
(function (global) {
    "use strict";

    // Local globals
    var $ = global.$;

    $(function() {

        $('button.attachment-form-add-button').click(function () {
            $(this).hide();
            $('.attachment-form-fields', this.parentNode).fadeIn();
        });


        // taking care of unified file inputs
        $('.real-file').each( function() {

            var realField = $(this),
                browseButton = $('<button/>').
                    addClass('browse-button has-icon ico-browse').
                    insertAfter(realField).
                    text('Select File to Attach'),
                fakeField = $('<span/>').
                    addClass('fake-file').
                    insertAfter(browseButton);

            fakeField.val('');

            browseButton.click( function (e) {
                e.preventDefault();
                e.stopPropagation();
                realField.click();
            });

            realField.click( function (e) {
                e.stopPropagation();
            });

            realField.change( function () {

                var pattern = 'C:\\fakepath\\';
                var fileName = realField.val();

                fileName = fileName.split( pattern ).join('');

                fakeField.text( fileName );
            });

        });

    });
}(window));
