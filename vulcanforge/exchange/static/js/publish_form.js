/* global $ */

$(function () {
    "use strict";

    var $publishForm = $("#artifact-publish-form"),
        $dependents = $publishForm.find("#publish-acl-dependents"),
        $shareSelect = $publishForm.find('select[name="scope"]'),
        $nbhdSelect,
        $projectSelect;

    $dependents.hide().find('br').remove();
    $nbhdSelect = $dependents.find('select[name="share_neighborhoods"]');
    $projectSelect = $dependents.find('input[name="share_projects"]');

    $shareSelect.change(function () {
        var val = $(this).val();
        if (val === 'neighborhood') {
            $nbhdSelect.show();
            $projectSelect.hide();
            $dependents.show();
        } else if (val === 'project') {
            $projectSelect.show();
            $nbhdSelect.hide();
            $dependents.show();
        } else {
            $dependents.hide();
        }
    });
    $shareSelect.change();
});