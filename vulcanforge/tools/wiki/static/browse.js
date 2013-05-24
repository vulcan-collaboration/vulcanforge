/*global alert, window, jQuery, $ */

$(function () {
    "use strict";

    var showDeleted,
        canDelete,
        $showDeletedButton = $('#show-deleted-button'),
        $hideDeletedButton = $('#hide-deleted-button'),
        $deletedEntries = $('#forge_wiki_browse_pages tbody > tr.deleted');

    window.toggleDeleted = function(showDeleted) {

        if ($deletedEntries.length && canDelete) {

            $showDeletedButton.toggle(!showDeleted);
            $hideDeletedButton.toggle(showDeleted);
            $deletedEntries.toggle(showDeleted);

            var suffix = showDeleted ? '&showDeleted=True' : '';
            $('#sort_recent').attr('href', '?sort=recent' + suffix);
            $('#sort_alpha').attr('href', '?sort=alpha' + suffix);
        } else {

            // There are now deleted items and user can't delete so turning buttons of

            $showDeletedButton.toggle(false);
            $hideDeletedButton.toggle(false);
        }

    };

    window.initBrowsePage = function(_canDelete, _showDelete) {
        canDelete = _canDelete;
        showDeleted = _showDelete;

        window.toggleDeleted(canDelete && showDeleted);
    };


});
