(function () {

    // instantiate
    $(function () {
        $('.vf-repeated-attachment-field').repeatedAttachmentField();
    });

    // define
    $.widget('vf.repeatedAttachmentField', {
        _create: function () {
            this.$blankField = this.element.find('input[type="file"]').remove();
            this.fieldIdPrefix = this.$blankField.attr('id').replace(/\d+$/,'');
            this.fieldNamePrefix = this.$blankField.attr('name').replace(/\d+$/,'');
            this.element.empty();
            this.addField();
        },
        addField: function () {
            var that = this,
                $clearButton,
                $field = this.$blankField.clone().
                    addClass('vf-repeated-attachment-field-input-empty').
                    bind('change', function () {
                        that.addField();
                        if ($field.val()) {
                            $field.removeClass("vf-repeated-attachment-field-input-empty");
                        }
                        $field.unbind('change');
                        $clearButton = $('<button/>').
                            text('remove').
                            addClass('vf-repeated-attachment-field-remove-button').
                            bind('click', function () {
                                $fieldContainer.remove();
                                that.updateFields();
                            }).
                            insertAfter($field);
                    }),
                $fieldContainer = $('<div/>').
                    addClass('vf-repeated-attachment-field-input-container').
                    append($field).
                    appendTo(this.element);
            this.updateFields();
        },
        updateFields: function () {
            var that = this,
                $fields = this.element.find('input[type="file"]');
            $fields.
                each(function (i) {
                    var $field = $(this),
                        newName = that.fieldNamePrefix + i,
                        newId = that.fieldIdPrefix + i;
                    if ($field.attr('name') != newName) {
                        $field.attr({
                            id: newId,
                            name: newName
                        });
                    }
                });
        }
    });
})();
