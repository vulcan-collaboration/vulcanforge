/*global window*/

/*
 * Initializing Post widget.
 *
 * @author Naba Bana
 */
(function (global) {
    "use strict";

    // Local globals
    var $ = global.$;

    $(function () {
        $('div.discussion-post').each(function () {
            var post = this,
                displayPost = $('.display-post', post),
                editPostForm = $('.edit_post_form', post),
                replyPostForm = $('.reply_post_form', post),
                editPostButton =  $('.edit_post', post),
                cancelEditPostButton = $('.cancel-edit-post', editPostForm),
                replyPostButton = $('.reply_post', post),
                cancelReplyPostButton = $('.cancel-edit-post', replyPostForm),
                editTextArea = $('textarea', editPostForm),
                replyTextArea = $('textarea', replyPostForm),
                shortLink = ('.shortlink', post);

            $('.submit', post).button();

            $('.flag_post', post).click(function () {
                this.parentNode.submit();
                return false;
            });

            $('.delete_post', post).click(function () {
                var go = confirm('Delete post?');
                if (go) {
                    this.parentNode.submit();
                }
                return false;
            });

            if (editPostButton) {
                editPostButton.click(function () {
                    displayPost.hide();
                    editPostForm.show();
                    editTextArea.focus();
                    return false;
                });
                cancelEditPostButton.click(function (evt) {
                    displayPost.show();
                    editPostForm.hide();

                    $("textarea", this.parentNode).val($("input.original_value", this.parentNode).val());
                    $(".attachment-form-fields input", this.parentNode).val('');
                    evt.preventDefault();
                });
            }
            if (replyPostButton) {
                replyPostButton.click(function () {
                    replyPostForm.show();
                    replyTextArea.focus();
                    return false;
                });
                cancelReplyPostButton.click(function (evt) {
                    replyPostForm.hide();
                });

            }

            if ($('.promote_to_thread', post)) {
                $('.promote_to_thread', post).click(function () {
                    $('.promote_to_thread_form', post).show();
                    return false;
                });
            }
        });

    });
}(window));