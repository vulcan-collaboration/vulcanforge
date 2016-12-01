/*global window, $vf*/

/*
 * Initializing attachment widget.
 *
 * @author Naba Bana
 */

(function (global) {
    "use strict";

    // Local globals
    var $ = global.$;

    var sessionId = $.cookie('_session_id');
    // Setting up the action for delete button
    $('.delete-attachment-button').each( function() {

        var button = $(this);
        var href = button.attr('href');
        var wrapperElement;

        button.removeAttr('href');

        button.click( function(e) {
            e.preventDefault();
            e.stopPropagation();

            if (confirm("Delete attachment?") === true){
                $.ajax({
                    type: 'POST',
                    url: href,
                    headers: {"VFSessionID": sessionId},
                    data: {delete: true},
                    success: function () {
                        var $messages = $('#messages');

                        $messages.notify('Attachment deleted', {
                            status: 'success'
                        });


                    },
                    error:function () {
                        var $messages = $('#messages');

                        $messages.notify('Attachment could not be deleted!', {
                            status: 'error'
                        });
                    }

                });

                wrapperElement = button.closest('li.attachment-wrapper') ||
                    button.closest('.attachment');

                if (wrapperElement) {
                    wrapperElement.remove();
                }
            }

        });

    });

}(window));
