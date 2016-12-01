(function (global) {
    "use strict";

    var $ = global.$,
        $vf = global.$vf || undefined,
        InvitationForm;

    if (!$vf) {
        throw {
            name: "MissingRequirement",
            message: "Artifact.js requires vf.js to be loaded first"
        };
    }

    InvitationForm = function (config) {
        var that = this,
            containerE = config.containerE || $(document),
            action = config.action,
            autocompleteUrl = config.autocompleteUrl,
            context = config.context || "project",
            project_opts = config.project_opts || [],
            onShow = config.onShow || null,
            onHide = config.onHide || null,
            onSubmit = config.onSubmit || $.noop,
            inputE,
            inviteTextE;

        this.form = null;

        function clear() {
            inputE.val("");
            inviteTextE.html("");
        }

        function hide() {
            /* clear(); */
            that.form.slideUp(400, function() {
                if (onHide !== null) {
                    onHide();
                }
            });
        }

        function submitHook() {
            var go = onSubmit();
            if (go !== false) {
                if (!inputE.val()){
                    inputE.parent().next('.explanation').html(
                        $('<p/>', {
                            "class": "fielderror",
                            "text": "Please specify user(s) and/or email addresses to invite"
                        })
                    );
                    go = false;
                }
            }
            return go;
        }

        function makeUserRow() {
            return $('<tr/>')
                .append($('<td/>').append($('<label for="users">To:</label>')))
                .append($('<td/>').append(
                    inputE = $('<input type="text" name="users" />')
                        .multicomplete({
                            ignoreRe: /@/,
                            minLength: 2,
                            source: function(request, callback) {
                                $.ajax({
                                    url: autocompleteUrl,
                                    data: {q: request.term},
                                    success: function (data, status, request) {
                                        callback(data.results);
                                    }
                                });
                            },
                            focus: function() {return false;},
                            autoFocus: true
                        })
                )).append($('<td class="explanation"/>')
                  .append("Enter usernames or email addresses, separated by commas"));
        }

        function makeProjectRow() {
            var tr = null,
                input;
            if (project_opts.length > 1) {
                tr = $('<tr/>')
                input = $('<select/>', {
                    name: "project"
                });
                $.each(project_opts, function(i, val) {
                    input.append($('<option/>')
                        .val(val.project_id)
                        .text(val.project_name));
                });
                tr.append($('<td/>').append($('<label for="project"/>Project:</label>')))
                    .append($('<td/>').append(input));
            } else if (project_opts.length === 1){
                tr = $('<tr/>').css("display", "none");
                input = $('<input/>', {
                    type: "hidden",
                    name: "project",
                    value: project_opts[0].project_id
                });
                tr.append($('<td/>'))
                    .append($('<td/>').append(input));
            }
            return tr;
        }

        function render() {
            that.form = $('<form/>', {
                style: "display:none",
                action: action,
                method: "POST",
                id: "invite-user-form",
                submit: submitHook
            }).append(
                $('<table/>').append($('<tbody/>')
                    .append(context === "project" ? makeUserRow() : makeProjectRow())
                    .append($('<tr/>')
                    .append($('<td/>').append($('<label for="text">Message:</label>')))
                    .append($('<td/>').append(
                    inviteTextE = $('<textarea rows="8" cols="60" name="text">Please join my project!</textarea>')
                ))
                    .append($('<td/>'))
                )
                )
            ).append(
                $('<input type="submit" value="Send" title="Send Invitations"/>')
            ).append(
                $('<input type="reset" value="Cancel" title="Cancel"/>')
                    .click(hide)
            ).append(
                $('<input/>', {
                    name: "_session_id",
                    type: "hidden",
                    value:$.cookie('_session_id')
                })
            );

            containerE.html(that.form);
        }

        function show() {
            if (that.form === null) {
                render();
            }
            that.form.slideDown();
            if (onShow !== null){
                onShow();
            }
        }

        /* exports */
        that.render = render;
        that.show = show;
    };

    $vf.InvitationForm = InvitationForm;

}(window));