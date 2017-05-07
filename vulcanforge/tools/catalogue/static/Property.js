/**
 * Core code for the Property Feature
 *
 *
 * @author Papszi
 *
 */


var $catalogue = $catalogue || {};

(function (global) {
    "use strict";

    $catalogue.Properties = function (config) {
        $.extend(this, config);

        this.featureElement = $('<div>',{
            id:'propertyFeatures',
            'class': 'featureHeader'
        });

        this.featureElement.appendTo($('#datasetProperties'));
        $.extend(this, new $catalogue.widgets.WidgetList({
            id: 'propertyWidgetList',
            containerElement: this.featureElement
        }));
    };

    $catalogue.Properties.prototype = {
        featureElement: null,
        controlElement: null,

        headerInputTemplate: '<table class="widgetsHolder widgetsList" cellspacing="3">'+
            '<tbody><tr><td class="labelContainer"/><td class="valueContainer">'+
            '<div class="controlContainer"/><div class="actionContainer">'+
            '<b>Discoverable</b><br/>Select / Deselect All<input type="checkbox" class="headerSelectAll"></div>'+
            '</td></tr></tbody></table>',

        init: function(){
            this.propertyTypeDescriptors = {};
            this.propertyInstanceDescriptors = [];
            this.propertyGroups = {};

            this.quantities = $catalogue.quantities;
        },

        config: function(config){
            $.extend(this, config);
        },

        ensureGroup: function(prefix, addHeader){
            var parentGroup, newGroup, metaName;
            var splitPrefix = prefix.split('.');
            var safePrefix = prefix.replace(/\./g, '_');
            var headerElement = null;
            var headerSelectAllCheckboxE;

            if (safePrefix == ''){
                return this;
            }
            if (addHeader && this.mode == 'INPUT') {
                headerElement = $(this.headerInputTemplate);
                headerSelectAllCheckboxE = headerElement.find('.headerSelectAll');
                headerSelectAllCheckboxE.bind('click', function(){
                    $('.headerDiscoverableBox').attr('checked', this.checked)
                });
            }

            if (this.propertyGroups.hasOwnProperty(safePrefix)){
                return this.propertyGroups[safePrefix];
            }else{
                metaName = splitPrefix.slice(splitPrefix.length-1, splitPrefix.length)[0];
                newGroup = {
                    typeId: 'property_group',
                    meta_name: metaName,
                    sort_name: 'zz' + metaName,
                    propertyInstanceDescriptors: [],
                    headerElement: headerElement
                };
                parentGroup = this.ensureGroup(
                    splitPrefix.slice(0, splitPrefix.length-1).join('.')
                );
                parentGroup.propertyInstanceDescriptors.push(newGroup);
                this.propertyGroups[safePrefix] = newGroup;
                return newGroup;
            }

        },

        addDiscoverableCheckbox: function(propertyInstance, discoverable){
            var action = {
                element: $('<input>', {
                    type: "checkbox",
                    class: "headerDiscoverableBox",
                    id: propertyInstance.id,
                    checked: discoverable
                }),
                click_function: function () {
                    if($(".headerDiscoverableBox").length == $(".headerDiscoverableBox:checked").length){
                        $(".headerSelectAll").attr("checked", "checked");
                    } else {
                        $(".headerSelectAll").removeAttr("checked");
                    }
                }};

            propertyInstance['actions'] = [action];
        },

        setValues: function(instances, readOnly){
            var i, j, prefix;
            var propertyType, propertyInstance, propertyGroup;

            this.init();

            for (i = 0; i < instances.length; i++) {
                var responseProp = instances[i];

                propertyType = { // descriptor of the property type ("meta")
                    id: responseProp.name.replace(" ","_") + '_property_type',
                    //readonly: readOnly, // if readonly then true
                    readonly: true,
                    //widget: responseProp.widget_type, // required
                    widget: 'TextField',
                    label: responseProp.name, // label of the property
                    description: '', // description of the property, can be used for title
                    defaultValue: responseProp.value, // default value
                    widgetParameters: {}, // holder of extra, widget-specific parameters
                    quantityId: null, // not required
                    possibleValues: null, // for select and multiple select
                    multiple: false
                };

                propertyInstance = { // descriptor of the actual property instance
                    id: responseProp.attribute_id, // id of the property
                    typeId: propertyType.id, // required
                    value: responseProp.value,
                    valid: true,
                    hint: responseProp.errors,
                    meta_name: responseProp.name,
                    sort_name: responseProp.name,
                    unitId: '', // if not set, default for quantity is set
                    // has_value_type_selector: true, // allow user to select value type
                    // value_type: responseProp.value_type == undefined ? 'fixed' : responseProp.value_type,
                    range: [0, 0]
                };

                switch(responseProp.value_type){
                    case 'derived':
                        propertyInstance.value_type = 'fixed';
                        break;
                    case 'parametric':
                        propertyInstance.value_type = 'parametric';
                        break;
                    case 'normal_distribution':
                        propertyInstance.value_type = 'normal_distribution';
                        break;
                    default:
                        propertyInstance.value_type = 'fixed';
                }

                // No hints means no problem with values so it can be discovered
                if (responseProp.errors.length == 0 && responseProp.value){
                    this.addDiscoverableCheckbox(propertyInstance, responseProp.discoverable);
                }

                if (responseProp.unit_id) {
                    propertyType.quantityId = responseProp.quantity_kind_id;
                    if (!propertyInstance.unitId) {
                        propertyInstance.unitId = responseProp.unit_id;
                    }
                }

                if (!isNaN(responseProp.min_value) && !isNaN(responseProp.max_value)) {
                    propertyInstance.range = [responseProp.min_value, responseProp.max_value];
                }
                if (responseProp.value_type && responseProp.value_type == 'computed') {
                    propertyInstance.value = responseProp.expression;
                    propertyInstance.has_value_type_selector = false;
                }

                propertyGroup = this.ensureGroup('Header', true);
                propertyGroup.propertyInstanceDescriptors.push(propertyInstance);

                this.propertyTypeDescriptors[propertyType.id] = propertyType;
            }
        },

        getPropertyValue: function(propInstance){
            var prop, $checkboxE, discoverable = false;
            $checkboxE = $(".headerDiscoverableBox[id='" + propInstance.id + "']");
            if ($checkboxE && $checkboxE.is(":checked")){
                discoverable = true;
            }
            prop = {
                attribute_id: propInstance.id,
                discoverable: discoverable
            };

            return prop;
        },

        getValues: function(){
            var result = [];
            var propInstance;
            var i;

            for (i in this.propertyInstanceDescriptorIndex) {
                if (this.propertyInstanceDescriptorIndex.hasOwnProperty(i)) {
                    propInstance = this.propertyInstanceDescriptorIndex[i];
                    result.push(this.getPropertyValue(propInstance));
                }
            }

            return result;
        },

        render: function(){
            var groupName, group;

            for (groupName in this.propertyGroups) {
                if (this.propertyGroups.hasOwnProperty(groupName)){
                    group = this.propertyGroups[groupName];
                    group.propertyInstanceDescriptors.sort($catalogue.sortBySortName);
                }
            }
            this.propertyInstanceDescriptors.sort($catalogue.sortBySortName);
            this.renderPropertyWidgets();

            // Finally setting the select all box:
            if($(".headerDiscoverableBox").length == $(".headerDiscoverableBox:checked").length){
                $(".headerSelectAll").attr("checked", "checked");
            } else {
                $(".headerSelectAll").removeAttr("checked");
            }
        }
    };

    $catalogue.features['properties'] = new $catalogue.Properties();

}(window));
