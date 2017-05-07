/**
 * Core code for the Property Feature
 *
 *
 * @author Naba Bana
 * @author Papszi
 *
 */


var $catalogue = $catalogue || {};

(function (global) {
    "use strict";

    $catalogue.BaseProperties = function (config) {
        $.extend(this, config);

        this.featureElement = $('#baseProperties');

        $.extend(this, new $catalogue.widgets.WidgetList({
            id: 'basePropertyWidgetList',
            containerElement: this.featureElement
        }));

        var that = this;
    };

    $catalogue.BaseProperties.prototype = {
        featureElement: null,
        nameProperty: null,
        versionProperty: null,
        componentId: null,

        init: function(){
            this.propertyTypeDescriptors = {};
            this.propertyInstanceDescriptors = [];
        },

        config: function(config){
            $.extend(this, config);
        },

        setValues: function (response, readOnly) {
            var i;
            var baseProp = [];

            var typeDescriptor, propertyInstance, propValue;
            var baseProps;

            this.init();
            this.versionedItem = response;

            if (response.description){
                $('#descriptionInput').val(response.description);
            }

            baseProps = [
                ['Name', this.versionedItem.name, 'TextField', 'name', '', 'Item name'],
                ['Version', this.versionedItem.version, 'TextField', 'version', '', 'Item version'],
                ['Released', this.versionedItem.released, 'CheckBox', 'released', '', 'Has item been released'],
                ['Description', this.versionedItem.description, 'TextField', 'description', '', 'Item description']
            ];

            for (i = 0; i < baseProps.length; i++) {
                baseProp = baseProps[i];
                propValue = baseProp[1];

                if (baseProp[4] != ''){
                    propValue = $('<a/>', {
                        'class': 'value',
                        'href': baseProp[4],
                        'text': baseProp[1]
                    });
                }

                typeDescriptor = {
                    id: baseProp[0] + '_Type',
                    readonly: readOnly,
                    widget: baseProp[2],
                    label: baseProp[0],
                    description: baseProp[5],
                    defaultValue: '',
                    widgetParameters: {},
                    quantityId: null,
                    possibleValues: null,
                    multiple: false
                };

                propertyInstance = {
                    id: baseProp[0] + '_Instance',
                    typeId: typeDescriptor.id,
                    value: propValue,
                    valid: true,
                    hint: '',
                    meta_name: baseProp[0],
                    sort_name: baseProp[0],
                    unitId: null,
                    value_type: 'fixed',
                    xcng_name: baseProp[3]
                };

                this.propertyTypeDescriptors[typeDescriptor.id] = typeDescriptor;
                this.propertyInstanceDescriptors.push(propertyInstance);
            }
        },

        getValues: function(){
            var baseProperties = {};
            var propInstance;
            var i;

            for (i in this.propertyInstanceDescriptorIndex) {
                if (this.propertyInstanceDescriptorIndex.hasOwnProperty(i)) {
                    propInstance = this.propertyInstanceDescriptorIndex[i];
                    if (this.propertyTypeDescriptors[propInstance.typeId].readonly){
                        continue;
                    }
                    baseProperties[propInstance.xcng_name] = propInstance.value;
                }
            }
            baseProperties["description"] = $('#descriptionInput').val();

            return baseProperties;
        },

        render: function(){
            this.removePropertyWidgets();
            this.renderPropertyWidgets();
            this.featureElement.toggle(true);
        }
    };

    $catalogue.baseProperties = new $catalogue.BaseProperties();

}(window));
