/**
 * Presentational classes for input/display property fields and corresponding labels for ComponentExchange.
 *
 * @author Naba Bana
 * @submodule $catalogue.widgets
 */

var $catalogue = $catalogue || {};

(function (global) {

    "use strict";

    // Import Globals

    var $ = global.jQuery,
        isSet = global.isSet,
        EventDispatcher = global.EventDispatcher,
        trace = global.trace;

    // Creating separate namespace for property widgets.

    $catalogue.widgets = {};

    // Constants

    $catalogue.valueTypeOptions = {
        'fixed': 'Fixed',
        'parametric': 'Parametric',
        'normal_dictribution': 'NormalDistribution'
        //'computed': 'Computed'
    };

    // Exceptions

    var ArgumentError = $catalogue.widgets.ArgumentError = function (msg) {
        this.name = 'ArgumentError';
        this.message = typeof msg !== undefined ? msg :
            'Argument is either missing or invalid.';
    };

    // Classes

    /**
    * This class renders a widget list on the screen. Can have a label.
     *
     * @class WidgetList
     * @namespace $catalogue.widgets
     *
     * @param {Object} config Configuration object
     */
    $catalogue.widgets.WidgetList = function (config) {
        $.extend(this, config);
    };

    $catalogue.widgets.WidgetList.prototype = {
        id: null,

        containerElement: null,

        label: null,
        labelElement: null,

        mode: "INPUT", // default mode
        quantities: null,
        propertyTypeDescriptors: null,
        propertyInstanceDescriptors: null,
        propertyWidgets: null,

        propertyInstanceDescriptorIndex: null,

        widgetsHolderTemplate: '<table cellspacing="3" class="widgetsHolder"><tbody></tbody></table>',
        widgetSkinTemplate: null,

        subLists: null,
        subWidgetsHolderTemplate: '<tr><td colspan="2" class="subWidgetsHolder"></td></tr>',
        subWidgetSkinTemplate: null,
        widgetLabelPostfix: null,

        widgetsHolder: null,

        renderPropertyWidgets: function (excludeList) {
            var i, widget, widgetType, containerElement;

            if (this.propertyInstanceDescriptors) {

                var propertyTypeDescriptors = this.propertyTypeDescriptors;

                if (!this.widgetsHolder) {
                    this.widgetsHolder = $(this.widgetsHolderTemplate);
                    this.widgetsHolder.attr('id', this.id);
                    this.widgetsHolder.addClass('widgetsList');
                    if (this.containerElement) {
                        containerElement = this.containerElement;
                        if (this.label) {
                            this.labelElement = $('<h4/>', {
                                'class': 'widgetsListLabel',
                                text: this.label
                            });
                            this.displayIndicatorElement = $('<div/>', {
                                'class': 'widgetsListDisplayIndicator',
                                text: "▲"
                            });
                            this.displayIndicatorElement.appendTo(this.labelElement);
                            this.labelElement.appendTo(this.containerElement);
                            this.labelElement.on('click', function(){
                                containerElement.find('.widgetsList').toggle();
                                var indicator = containerElement.find('.widgetsListDisplayIndicator').text();
                                if (indicator == "▲"){
                                    containerElement.find('.widgetsListDisplayIndicator').text('▼');
                                } else {
                                    containerElement.find('.widgetsListDisplayIndicator').text('▲');
                                }
                            });
                        }

                        if (this.headerElement){
                            this.headerElement.appendTo(this.containerElement);
                        }
                        this.widgetsHolder.appendTo(this.containerElement);
                    }
                }

                this.removePropertyWidgets();
                this.propertyWidgets = {};
                var subListOrder = 0;

                var propertyInstanceDescriptorIndex =
                    this.propertyInstanceDescriptorIndex =
                    this.propertyInstanceDescriptorIndex || {};

                var make_valueChangeHandler =  function() {
                    return function (e, args) {
                        if (e.host.onValueChange) {
                            var ctx = isSet(e.host.onValueChange_ctx) ? e.host.onValueChange_ctx : this;
                            e.host.onValueChange.call(ctx, args);
                        }
                    };
                };

                for (i = 0; i < this.propertyInstanceDescriptors.length; i++) {
                    var d = this.propertyInstanceDescriptors[i],
                        $containerE, $headerHolderE;

                    if (!($.isArray(excludeList) && excludeList.indexOf(d.meta_name) > -1)) {

                        // dealing with sub-lists
                        if (d.typeId == 'property_group' && $.isArray(d.propertyInstanceDescriptors)) {

                            this.subLists = this.subLists || [];

                            var subWidgetsHolder = $(this.subWidgetsHolderTemplate);
                            subWidgetsHolder.appendTo(this.widgetsHolder);

                            if ( subWidgetsHolder.hasClass( 'subWidgetsHolder' ) ) {
                                $containerE = subWidgetsHolder;
                            } else {
                                $containerE = subWidgetsHolder.find('.subWidgetsHolder');
                            }

                            var subList = new $catalogue.widgets.WidgetList({

                                id: this.id + '_' + subListOrder,
                                containerElement: $containerE,

                                mode: this.mode,

                                label: d.meta_name,
                                headerElement: d.headerElement,
                                onValueChange: this.onValueChange,
                                onValueChange_ctx: this.onValueChange_ctx,

                                widgetsHolderTemplate: this.widgetsHolderTemplate,
                                widgetSkinTemplate: this.widgetSkinTemplate,
                                subWidgetsHolderTemplate: this.subWidgetsHolderTemplate,
                                subWidgetSkinTemplate: this.subWidgetSkinTemplate,
                                widgetLabelPostfix: this.widgetLabelPostfix,
                                quantities: this.quantities,
                                propertyTypeDescriptors: this.propertyTypeDescriptors,
                                propertyInstanceDescriptors: d.propertyInstanceDescriptors,

                                propertyInstanceDescriptorIndex: this.propertyInstanceDescriptorIndex

                            });

                            this.subLists.push(subList);

                            subList.renderPropertyWidgets();

                        } else {
                            widget = propertyTypeDescriptors[d.typeId].widget;

                            propertyInstanceDescriptorIndex[d.meta_name] = d;

                            widgetType = this.propertyTypeDescriptors[d.typeId].widget;

                            //trace(widgetType);
                            if ($.isFunction($catalogue.widgets[widgetType])) {
                                widget = new $catalogue.widgets[widgetType](d, this.mode, this);

                                if (this.widgetSkinTemplate) {
                                    widget.skinTemplate = this.widgetSkinTemplate;
                                }

                                if (this.widgetLabelPostfix) {
                                    widget.labelPostfix = this.widgetLabelPostfix;
                                }

                                widget.renderTo(this.widgetsHolder);

                                if (i % 2 == 0) {
                                    widget.skin.addClass('even');
                                }

                                widget.addEventListener("VALUE_CHANGED", make_valueChangeHandler());
                                this.propertyWidgets[d.id] = widget;
                            }

                        }
                    }
                }
            }
        },

        removePropertyWidgets: function () {
            var i;

            if (this.propertyWidgets) {
                for (i in this.propertyWidgets) {

                    if (this.propertyWidgets.hasOwnProperty(i)) {
                        this.propertyWidgets[i].removeAllEventListeners("VALUE_CHANGED");
                        this.propertyWidgets[i].remove();
                    }
                }

                if (this.subLists) {
                    for (i = 0; i < this.subLists.length; i++) {
                        this.subLists[i].remove();
                    }
                }

                this.propertyWidgets = null;
                this.propertyInstanceDescriptorIndex = {};
                this.subLists = [];
            }
        },

        remove: function () {

            if (this.widgetsHolder) {
                this.removePropertyWidgets();
                this.containerElement.closest('tr').remove();
                this.containerElement.remove();
            }
        },

        addPropertyInstance: function(instanceId) {

        }
    };


    /**
     * Virtual base class for the various Widgets. Extend this and Use subclasses to create instances.
     *
     * @class PropertyWidget
     * @namespace $catalogue.widgets
     * @constructor
     *
     * @param {Object} propertyInstanceDescriptor Property to display.
     * @param {String} mode Can be 'DISPLAY' or 'INPUT'
     * @param {Object} host Creator Object or parent (typically a WidgetList) who handles events
     */
    $catalogue.widgets.PropertyWidget = function (propertyInstanceDescriptor, mode, host) {

        this.mode = mode;
        this.host = host;
        this.propertyInstanceDescriptor = propertyInstanceDescriptor;

        if (typeof this.host === 'undefined' ||
            typeof this.host.propertyTypeDescriptors === 'undefined') {
            throw new ArgumentError("PropertyWidget requires a host with a " +
                "propertyTypeDescriptors property.");
        }
        this.propertyTypeDescriptor = host.propertyTypeDescriptors[propertyInstanceDescriptor.typeId];

        if (this.propertyTypeDescriptor.quantityId) {
            this.quantity = host.quantities[this.propertyTypeDescriptor.quantityId];
        }

        $.extend(this, new EventDispatcher());
    };

    $catalogue.widgets.PropertyWidget.prototype = {
        quantity: null,
        propertyTypeDescriptor: null,
        propertyInstanceDescriptor: null,
        containerElement: null,
        skin: null,

        labelContainer: null,
        controlContainer: null,
        statusContainer: null,
        hintContainer: null,
        actionContainer: null,
        valueContainer: null,
        control: null,

        mode: 'INPUT', // default mode
        host: null,

        skinTemplate: '<tr><td class="labelContainer"></td><td class="valueContainer">'
            +'<div class="controlContainer"/><div class="actionContainer"/><div class="hintContainer"/></td></tr>',
        labelPostfix: '',
        titleText: '',
        unit: null,

        renderTo: function (containerElement) {
            if (this.containerElement != containerElement) {
                this.containerElement = containerElement;
                this.render();
            }
        },

        render: function () {
            var i;
            var propertyInstanceDescriptor = this.propertyInstanceDescriptor;
            var pLabel = this.propertyTypeDescriptor.label;
            //this.unit = propertyInstanceDescriptor.unit;
            var oldSkin;
            if (!this.skin) {
                this.skin = $(this.skinTemplate);
            } else {
                oldSkin = this.skin;
                this.skin = $(this.skinTemplate);
            }
            this.skin.attr('id', propertyInstanceDescriptor.id + "_widget");
            this.skin.attr('title', this.propertyTypeDescriptor.description);
            this.skin.addClass('widgetSkin');
            this.skin.addClass(this.mode);

            this.labelContainer = this.skin.find('.labelContainer');
            this.labelContainer.text(pLabel + this.labelPostfix);

            this.valueContainer = this.skin.find('.valueContainer');

            this.controlContainer = this.skin.find('.controlContainer');
            this.statusContainer = this.skin.find('.statusContainer');

            if (!propertyInstanceDescriptor.valid) {
                this.skin.addClass('invalid');
            } else {
                this.skin.addClass('valid');
            }

            if (this.mode == 'INPUT'){
                this.actionContainer = this.skin.find('.actionContainer');
                if (isSet(propertyInstanceDescriptor.actions)) {
                    for (i = 0; i < propertyInstanceDescriptor.actions.length; i++) {
                        var action = propertyInstanceDescriptor.actions[i];
                        this.actionContainer.append(action.element);
                        action.element.bind('click', action.click_function);
                    }
                }
            }

            this.hintContainer = this.skin.find('.hintContainer');
            if (isSet(propertyInstanceDescriptor.hint)) {
                this.hintContainer.text(propertyInstanceDescriptor.hint);
            }

            this.skin.data('host', this);

            this.skin.keydown(function (e) {
                if (e.which == 8 || e.which == 46) {
                    e.stopPropagation();
                }
            });

            if (this.containerElement) {
                this.controlContainer.empty();

                // should be implemented in children
                this.renderControl();

                if (oldSkin) {
                    this.skin.insertBefore(oldSkin);
                    oldSkin.remove();
                } else {
                    this.skin.appendTo(this.containerElement);
                }
            }
        },

        enable: function () {
            // Override this in child classes
        },

        disable: function () {
            // Override this in child classes
        },

        // call this from skin
        _triggerChange: function () {
            this.dispatchEvent("VALUE_CHANGED", this.propertyInstanceDescriptor);
        },

        remove: function () {
            this.skin.remove();
        }
    };


    /**
     * TextField widget
     *
     * @class TextField
     * @namespace $catalogue.widgets
     * @constructor
     * @extends PropertyWidget
     *
     * @param {Object} propertyInstanceDescriptor Property to display.
     * @param {String} mode Can be 'DISPLAY' or 'INPUT'
     * @param {Object} host Creator Object or parent (typically a WidgetList) who handles events
     */
    $catalogue.widgets.TextField = function (propertyInstanceDescriptor, mode, host) {
        $catalogue.widgets.PropertyWidget.call(this, propertyInstanceDescriptor, mode, host);

        this.valueTypeSelectorE = null;
    };

    $catalogue.widgets.TextField.prototype = {
        renderControl: function () {

            var that = this;

            var unit, unitE, unitId, control, i, options, inputHint = '', valueTypeSelectorE, valueOptionE,
                valueType = this.propertyInstanceDescriptor.value_type, inputE, rangeLowerInputE, rangeUpperInputE, muInputE, sigmaInputE;


            if (this.quantity && this.quantity.units) {

                if (this.propertyInstanceDescriptor.unitId) {
                    unitId = this.propertyInstanceDescriptor.unitId;
                } else if (this.quantity.baseUnit) {
                    unitId = this.quantity.baseUnit;
                }

                unit = this.quantity.units[unitId];
            }

            switch (this.mode) {
            case "INPUT":

                if (unit) {

                    options = [];
                    $.each(this.quantity.units, function (unitName, unitInstance) {
                        options.push([unitName, unitInstance.symbol]);
                    });

                    if (options.length == 1) {
                        unitE = $('<span/>', {
                            text: unit.symbol,
                            'class': 'unit ' + this.propertyTypeDescriptor.quantityId
                        });
                    } else {
                        var optionsHtml = "";
                        for (i = 0; i < options.length; i++) {
                            if (unitId == options[i][0]) {
                                optionsHtml += '<option value="' + options[i][0]
                                            + '" selected="selected">' + options[i][1] + '</option>';
                            } else {
                                optionsHtml += '<option value="' + options[i][0] + '">'
                                            + options[i][1] + '</option>';
                            }
                        }
                        unitE = $('<select/>', {
                            html: optionsHtml,
                            disabled: this.propertyTypeDescriptor.readonly ? true : false,
                            'class': 'unit ' + this.propertyTypeDescriptor.quantityId,
                            change: function () {
                                var host = $(this).data('host');
                                host.propertyInstanceDescriptor.unitId = $(this).val();
                                host._triggerChange.call(host);
                            }

                        });

                        unitE.data('host', this.host);
                    }
                }

                if (valueType == 'parametric') {
                    rangeLowerInputE = $('<input/>', {
                        type: "text",
                        title: this.quantity ? inputHint : "",
                        value: this.propertyInstanceDescriptor.range[0],
                        'class': "rangeLower propertyValue TextField INPUT numeric",
                        id: this.propertyInstanceDescriptor.id + "_rangeLower",
                        disabled: this.propertyTypeDescriptor.readonly ? true : false,
                        change: function () {
                            var host = $(this).data('host');
                            host.propertyInstanceDescriptor.range[0] = $(this).val();
                            host._triggerChange.call(host);
                        }
                    });

                    rangeUpperInputE = $('<input/>', {
                        type: "text",
                        title: this.quantity ? inputHint : "",
                        value: this.propertyInstanceDescriptor.range[1],
                        'class': "rangeUpper propertyValue TextField INPUT numeric",
                        id: this.propertyInstanceDescriptor.id + "_rangeUpper",
                        disabled: this.propertyTypeDescriptor.readonly ? true : false,
                        change: function () {
                            var host = $(this).data('host');
                            host.propertyInstanceDescriptor.range[1] = $(this).val();
                            host._triggerChange.call(host);
                        }
                    });
                }

                switch (valueType) {
                    case 'parametric':
                        control = rangeLowerInputE.after($('<span> - </span>')).after(rangeUpperInputE);
                        break;

                    case 'computed':
                        inputE = $('<input/>', {
                            type: "text",
                            title: this.quantity ? inputHint : "",
                            value: this.propertyInstanceDescriptor.value,
                            'class': "propertyValue TextField INPUT",
                            id: this.propertyInstanceDescriptor.id + "_input",
                            disabled: true, //this.propertyTypeDescriptor.readonly ? true : false,
                            change: function () {
                                var host = $(this).data('host');
                                host.propertyInstanceDescriptor.value = $(this).val();
                                host._triggerChange.call(host);
                            }
                        });

                        //control = inputE.after($('<br/>')).after(rangeLowerInputE)
                        //                .after($('<span> - </span>')).after(rangeUpperInputE);
                        control = inputE;
                        break;

                    case 'fixed':
                        inputE = $('<input/>', {
                            type: "text",
                            title: this.quantity ? inputHint : "",
                            value: this.propertyInstanceDescriptor.value,
                            'class': "propertyValue TextField INPUT" + (this.quantity ? " numeric" : ""),
                            id: this.propertyInstanceDescriptor.id + "_input",
                            disabled: this.propertyTypeDescriptor.readonly ? true : false,
                            change: function () {
                                var host = $(this).data('host');
                                host.propertyInstanceDescriptor.value = $(this).val();
                                host._triggerChange.call(host);
                            }
                        });
                        control = inputE;
                        break;

                    case 'normal_distribution':
                        muInputE = $('<input/>', {
                            type: "text",
                            title: this.quantity ? inputHint : "",
                            value: this.propertyInstanceDescriptor.mean,
                            'class': "propertyValue TextField INPUT numeric",
                            id: this.propertyInstanceDescriptor.id + "_mean",
                            disabled: this.propertyTypeDescriptor.readonly ? true : false,
                            change: function () {
                                var host = $(this).data('host');
                                host.propertyInstanceDescriptor.mean = $(this).val();
                                host._triggerChange.call(host);
                            }
                        });

                        sigmaInputE = $('<input/>', {
                            type: "text",
                            title: this.quantity ? inputHint : "",
                            value: this.propertyInstanceDescriptor.standard_deviation,
                            'class': "propertyValue TextField INPUT numeric",
                            id: this.propertyInstanceDescriptor.id + "_standard_deviation",
                            disabled: this.propertyTypeDescriptor.readonly ? true : false,
                            change: function () {
                                var host = $(this).data('host');
                                host.propertyInstanceDescriptor.standard_deviation = $(this).val();
                                host._triggerChange.call(host);
                            }
                        });
                        var muText = $('<span/>', {
                            text: 'μ: '
                        });
                        control = muText.after(muInputE).after($('<span> σ: </span>')).after(sigmaInputE);
                        break;

                    case undefined:

                }

                if (unitE) {
                    control = control.after(unitE);
                }

                if (isSet(this.propertyTypeDescriptor.widgetParameters)
                    && isSet(this.propertyTypeDescriptor.widgetParameters.width)) {
                    control.width(this.propertyTypeDescriptor.widgetParameters.width);
                }

                if (this.propertyInstanceDescriptor.has_value_type_selector) {
                    // here we add value_type selector

                    valueTypeSelectorE = this.valueTypeSelectorE = $('<ul/>', {
                        'class': 'valueTypeSelector'
                    });

                    $.each($catalogue.valueTypeOptions, function(option,optionText){

                        valueOptionE = $('<li/>', {
                            'text': optionText
                        });

                        if (valueType === option) {
                            valueOptionE.addClass('selected');
                        } else {
                            valueOptionE.attr('title', 'Switch type to ' + optionText);
                            valueOptionE.click(function() {
                                trace('Value type is set to ['+option+']');
                                that.propertyInstanceDescriptor.value_type = option;
                                that.controlContainer.empty();
                                that.renderControl.call(that);
                            });
                        }

                        valueTypeSelectorE.append(valueOptionE);

                    });

                    control = control.before(valueTypeSelectorE);

                }

                break;

            case "DISPLAY":

                var unitTitle = '', valueText = '';
                if (unit) {
                    unitE = $('<span/>', {
                        text: unit.symbol,
                        'class': 'unit ' + (this.propertyTypeDescriptor ? this.propertyTypeDescriptor.quantityId : '')
                    });
                    unitTitle = unit.symbol;
                }

                if (valueType !== undefined) {
                    this.skin.addClass(valueType);
                }

                switch (valueType) {
                    case 'parametric':
                        valueText = this.propertyInstanceDescriptor.range[0]
                            + ' - '
                            + this.propertyInstanceDescriptor.range[1];
                        break;

                    case 'computed':
                        valueText = this.propertyInstanceDescriptor.value;
                        break;

                    case 'normal_distribution':
                        valueText = '<strong><em>μ </em></strong>' +
                            this.propertyInstanceDescriptor.mean +
                            ' <strong><em>σ</em></strong> ' +
                            this.propertyInstanceDescriptor.standard_deviation;
                        break;

                    case undefined:
                    case 'fixed':
                        valueText = this.propertyInstanceDescriptor.value;
                        break;
                }


                this.titleText = valueText + ' ' + unitTitle;

                control = $('<span/>', {
                    html: valueText,
                    title: this.titleText,
                    'class': "propertyValue TextField DISPLAY"
                }).add(unitE);


                if (isSet(this.propertyTypeDescriptor.widgetParameters)
                    && isSet(this.propertyTypeDescriptor.widgetParameters.width)) {
                    control.width(this.propertyTypeDescriptor.widgetParameters.width);
                }

                break;

            }


            control.data('host', this);

            if (this.quantity) {
                this.controlContainer.addClass('numeric');
            }

            this.controlContainer.append(control);
            this.control = control;

        }
    };

    $.extend($catalogue.widgets.TextField.prototype, $catalogue.widgets.PropertyWidget.prototype);


    /**
     * DropDown widget
     *
     * @class DropDown
     * @namespace $catalogue.widgets
     * @constructor
     * @extends PropertyWidget
     *
     * @param {Object} propertyInstanceDescriptor Property to display.
     * @param {String} mode Can be 'DISPLAY' or 'INPUT'
     * @param {Object} host Creator Object or parent (typically a WidgetList) who handles events
     */
    $catalogue.widgets.DropDown = function (propertyInstanceDescriptor, mode, host) {
        $catalogue.widgets.PropertyWidget.call(this, propertyInstanceDescriptor, mode, host);
    };

    $catalogue.widgets.DropDown.prototype = {
        renderControl: function () {

            var _ = this;

            switch (this.mode) {
            case "INPUT":
                var control = $('<select/>', {
                    'class': "propertyValue Select INPUT",
                    id: this.propertyInstanceDescriptor.id + "_input",
                    disabled: this.propertyTypeDescriptor.readonly ? true : false,
                    change: function () {
                        var host = $(this).data('host');
                        host.propertyInstanceDescriptor.value = $(this).val();
                        host._triggerChange.call(host);
                    }
                });

                var multiple = this.propertyTypeDescriptor.multiple;
                if (multiple) {

                    control.attr('multiple', 'multiple');

                    $.each(this.propertyTypeDescriptor.possibleValues, function (key, value) {
                        var index = _.propertyInstanceDescriptor.value.indexOf(key);
                        control.append('<option'
                            + ( index > -1 ? ' selected="selected"' : '')
                            + ' value="' + key + '" >'
                            + _.propertyTypeDescriptor.possibleValues[key] + '</option>');
                    });

                } else {
                    $.each(this.propertyTypeDescriptor.possibleValues, function (key, value) {
                        control.append('<option'
                            + (key == _.propertyInstanceDescriptor.value ? ' selected="selected"' : '')
                            + ' value="' + key + '" >' + _.propertyTypeDescriptor.possibleValues[key] + '</option>');
                    });
                }

                if (isSet(this.propertyTypeDescriptor.widgetParameters)
                    && isSet(this.propertyTypeDescriptor.widgetParameters.rows)) {
                    control.attr('size', this.propertyTypeDescriptor.widgetParameters.rows);
                }

                break;

            case "DISPLAY":

                var value = this.propertyInstanceDescriptor.value;

                this.titleText = $.isArray(value) ? value.join(', ') : value;

                control = $('<span/>', {
                    text: this.titleText,
                    'class': "propertyValue Select DISPLAY"
                });

                control.attr('title', control.text());

                break;

            }

            if (isSet(this.propertyTypeDescriptor.widgetParameters)
                && isSet(this.propertyTypeDescriptor.widgetParameters.width)) {
                control.width(this.propertyTypeDescriptor.widgetParameters.width);
            }

            control.data('host', this);

            this.controlContainer.append(control);
            this.control = control;

            this.controlContainer.addClass('DropDown');

        }
    };

    $.extend($catalogue.widgets.DropDown.prototype, $catalogue.widgets.PropertyWidget.prototype);
    /**
     * CheckBox widget
     *
     * @class CheckBox
     * @namespace $catalogue.widgets
     * @constructor
     * @extends PropertyWidget
     *
     * @param {Object} propertyInstanceDescriptor Property to display.
     * @param {String} mode Can be 'DISPLAY' or 'INPUT'
     * @param {Object} host Creator Object or parent (typically a WidgetList) who handles events
     */
    $catalogue.widgets.CheckBox = function (propertyInstanceDescriptor, mode, host) {
        $catalogue.widgets.PropertyWidget.call(this, propertyInstanceDescriptor, mode, host);
    };

    $catalogue.widgets.CheckBox.prototype = {
        renderControl: function () {

            var control;

            switch (this.mode) {
            case "INPUT":
                control = $('<input/>', {
                    type: 'checkbox',
                    value: this.propertyInstanceDescriptor.value,
                    'class': "propertyValue CheckBox INPUT",
                    id: this.propertyInstanceDescriptor.id + "_input",
                    disabled: this.propertyTypeDescriptor.readonly ? true : false,
                    change: function () {
                        var host = $(this).data('host');
                        host.propertyInstanceDescriptor.value = (this.checked) ? true : false;
                        host._triggerChange.call(host);
                    }
                });

                control.attr('checked', this.propertyInstanceDescriptor.value == true);

                break;

            case "DISPLAY":
                if (this.propertyInstanceDescriptor.value == true) {
                    this.titleText = 'yes';
                } else {
                    this.titleText = 'no';
                }

                control = $('<span/>', {
                    'class': "propertyValue CheckBox DISPLAY " + this.propertyInstanceDescriptor.value,
                    id: this.propertyInstanceDescriptor.id + "_input",
                    text: this.titleText
                });
                break;

            }

            if (isSet(this.propertyTypeDescriptor.widgetParameters)
                && isSet(this.propertyTypeDescriptor.widgetParameters.width)) {
                control.width(this.propertyTypeDescriptor.widgetParameters.width);
            }

            control.data('host', this);

            this.controlContainer.addClass('CheckBox');

            this.controlContainer.append(control);
            this.control = control;

        }
    };

    $.extend($catalogue.widgets.CheckBox.prototype, $catalogue.widgets.PropertyWidget.prototype);

    /**
     * TextArea widget
     *
     * @class TextArea
     * @namespace $catalogue.widgets
     * @constructor
     * @extends PropertyWidget
     *
     * @param {Object} propertyInstanceDescriptor Property to display.
     * @param {String} mode Can be 'DISPLAY' or 'INPUT'
     * @param {Object} host Creator Object or parent (typically a WidgetList) who handles events
     */
    $catalogue.widgets.TextArea = function (propertyInstanceDescriptor, mode, host) {
        $catalogue.widgets.PropertyWidget.call(this, propertyInstanceDescriptor, mode, host);
    };

    $catalogue.widgets.TextArea.prototype = {
        renderControl: function () {

            var control;

            switch (this.mode) {
            case "INPUT":
                control = $('<textarea/>', {
                    text: this.propertyInstanceDescriptor.value,
                    'class': "propertyValue TextArea INPUT",
                    id: this.propertyInstanceDescriptor.id + "_input",
                    disabled: this.propertyTypeDescriptor.readonly ? true : false,
                    change: function () {
                        var host = $(this).data('host');
                        host.propertyInstanceDescriptor.value = $(this).val();
                        host._triggerChange.call(host);
                    }
                });

                control.attr('checked', this.propertyInstanceDescriptor.value);

                if (isSet(this.propertyTypeDescriptor.widgetParameters)
                    && isSet(this.propertyTypeDescriptor.widgetParameters.cols)) {
                    control.attr('cols', this.propertyTypeDescriptor.widgetParameters.cols);
                }
                if (isSet(this.propertyTypeDescriptor.widgetParameters)
                    && isSet(this.propertyTypeDescriptor.widgetParameters.rows)) {
                    control.attr('rows', this.propertyTypeDescriptor.widgetParameters.rows);
                }

                break;

            case "DISPLAY":

                this.titleText = this.propertyInstanceDescriptor.value;

                control = $('<span/>', {
                    text: this.propertyInstanceDescriptor.value,
                    title: this.propertyInstanceDescriptor.value,
                    'class': "propertyValue TextArea DISPLAY",
                    id: this.propertyInstanceDescriptor.id + "_input"
                });

                break;

            }

            control.data('host', this);

            this.controlContainer.addClass('TextArea');

            this.controlContainer.append(control);
            this.control = control;

        }
    };

    $.extend($catalogue.widgets.TextArea.prototype, $catalogue.widgets.PropertyWidget.prototype);

    /**
     * Matrix widget
     *
     * @class Matrix
     * @namespace $catalogue.widgets
     * @constructor
     * @extends PropertyWidget
     *
     * @param {Object} propertyInstanceDescriptor Property to display.
     * @param {String} mode Can be 'DISPLAY' or 'INPUT'
     * @param {Object} host Creator Object or parent (typically a WidgetList) who handles events
     */
    $catalogue.widgets.Matrix = function (propertyInstanceDescriptor, mode, host) {
        $catalogue.widgets.PropertyWidget.call(this, propertyInstanceDescriptor, mode, host);
    };

    $catalogue.widgets.Matrix.prototype = {
        renderControl: function () {

            var control, x_dim, y_dim, unitId, unit;

            if (this.quantity && this.quantity.units) {

                if (this.propertyInstanceDescriptor.unitId) {
                    unitId = this.propertyInstanceDescriptor.unitId;
                } else if (this.quantity.baseUnit) {
                    unitId = this.quantity.baseUnit;
                }

                unit = this.quantity.units[unitId];
            }
            switch (this.mode) {
            case "INPUT":
                control = $('<textarea/>', {
                    text: this.propertyInstanceDescriptor.value,
                    'class': "propertyValue Matrix INPUT",
                    id: this.propertyInstanceDescriptor.id + "_input",
                    disabled: this.propertyTypeDescriptor.readonly ? true : false,
                    change: function () {
                        var host = $(this).data('host');
                        host.propertyInstanceDescriptor.value = $(this).val();
                        host._triggerChange.call(host);
                    }
                });

                control.attr('checked', this.propertyInstanceDescriptor.value);

                if (isSet(this.propertyTypeDescriptor.widgetParameters)
                    && isSet(this.propertyTypeDescriptor.widgetParameters.cols)) {
                    control.attr('cols', this.propertyTypeDescriptor.widgetParameters.cols);
                }
                if (isSet(this.propertyTypeDescriptor.widgetParameters)
                    && isSet(this.propertyTypeDescriptor.widgetParameters.rows)) {
                    control.attr('rows', this.propertyTypeDescriptor.widgetParameters.rows);
                }

                break;

            case "DISPLAY":
                var unitTitle = '';
                if (unit) {
                    unitTitle = '&nbsp;&nbsp;'+unit.symbol;
                }

                this.titleText = this.propertyInstanceDescriptor.value;
                try{
                    x_dim = this.propertyInstanceDescriptor.value.split(';');
                    y_dim = x_dim[0].split(',');
                }catch (err){
                    x_dim = [];
                    y_dim = [];
                }

                control = $('<span/>', {
                    html: '<sub>' + x_dim.length + 'X' + y_dim.length + '</sub>' + unitTitle,
                    title: this.propertyInstanceDescriptor.value,
                    'class': "propertyValue Matrix DISPLAY",
                    id: this.propertyInstanceDescriptor.id + "_input"
                });

                break;

            }

            control.data('host', this);

            this.controlContainer.addClass('Matrix');

            this.controlContainer.append(control);
            this.control = control;

        }
    };

    $.extend($catalogue.widgets.Matrix.prototype, $catalogue.widgets.PropertyWidget.prototype);

    /**
     * Vector widget
     *
     * @class Vector
     * @namespace $catalogue.widgets
     * @constructor
     * @extends PropertyWidget
     *
     * @param {Object} propertyInstanceDescriptor Property to display.
     * @param {String} mode Can be 'DISPLAY' or 'INPUT'
     * @param {Object} host Creator Object or parent (typically a WidgetList) who handles events
     */
    $catalogue.widgets.Vector = function (propertyInstanceDescriptor, mode, host) {
        $catalogue.widgets.PropertyWidget.call(this, propertyInstanceDescriptor, mode, host);
    };

    $catalogue.widgets.Vector.prototype = {
        renderControl: function () {

            var control, x_dim, unitId, unit;

            if (this.quantity && this.quantity.units) {

                if (this.propertyInstanceDescriptor.unitId) {
                    unitId = this.propertyInstanceDescriptor.unitId;
                } else if (this.quantity.baseUnit) {
                    unitId = this.quantity.baseUnit;
                }

                unit = this.quantity.units[unitId];
            }
            switch (this.mode) {
            case "INPUT":
                control = $('<textarea/>', {
                    text: this.propertyInstanceDescriptor.value,
                    'class': "propertyValue Vector INPUT",
                    id: this.propertyInstanceDescriptor.id + "_input",
                    disabled: this.propertyTypeDescriptor.readonly ? true : false,
                    change: function () {
                        var host = $(this).data('host');
                        host.propertyInstanceDescriptor.value = $(this).val();
                        host._triggerChange.call(host);
                    }
                });

                control.attr('checked', this.propertyInstanceDescriptor.value);

                if (isSet(this.propertyTypeDescriptor.widgetParameters)
                    && isSet(this.propertyTypeDescriptor.widgetParameters.cols)) {
                    control.attr('cols', this.propertyTypeDescriptor.widgetParameters.cols);
                }
                if (isSet(this.propertyTypeDescriptor.widgetParameters)
                    && isSet(this.propertyTypeDescriptor.widgetParameters.rows)) {
                    control.attr('rows', this.propertyTypeDescriptor.widgetParameters.rows);
                }

                break;

            case "DISPLAY":
                var unitTitle = '';
                if (unit) {
                    unitTitle = '&nbsp;&nbsp;'+unit.symbol;
                }

                this.titleText = this.propertyInstanceDescriptor.value;
                try{
                    x_dim = this.propertyInstanceDescriptor.value.split(',');
                }catch (err){
                    x_dim = [];
                }

                control = $('<span/>', {
                    html: '<sub>' + x_dim.length + '</sub>' + unitTitle,
                    title: this.propertyInstanceDescriptor.value,
                    'class': "propertyValue Vector DISPLAY",
                    id: this.propertyInstanceDescriptor.id + "_input"
                });

                break;

            }

            control.data('host', this);

            this.controlContainer.addClass('Vector');

            this.controlContainer.append(control);
            this.control = control;

        }
    };

    $.extend($catalogue.widgets.Vector.prototype, $catalogue.widgets.PropertyWidget.prototype);
    
}(window));
