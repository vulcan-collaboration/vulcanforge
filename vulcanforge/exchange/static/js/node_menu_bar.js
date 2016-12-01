/* globals window, jQuery */

(function ($) {
    "use strict";
    var $vf = window.$vf || {};

    $vf.unpublishNode = function(unpublishUrl) {
        var confirmed = window.confirm("Unpublish artifact?");
        if (confirmed) {
            $.ajax({
                "url": unpublishUrl,
                "type": "POST",
                "data": {
                    "_session_id": $.cookie("_session_id")
                },
                "dataType": "json",
                "success": function (response) {
                    window.location = response.location;
                },
                "error": function () {
                    $vf.webflash({
                        "message": "An error occurred while unpublishing this artifact.",
                        "status": "error"
                    });
                }
            });
        }
        return false;
    };
}(jQuery));
