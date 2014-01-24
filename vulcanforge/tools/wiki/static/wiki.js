/*global window, $, isNaN, RegExp, jQuery */
(function(){
    "use strict";
    $(function(){

        var $vf = window.$vf;

        $vf.afterInit(function() {

            var $v1Input = $('input[name=v1]'),
                $v2Input = $('input[name=v2]'),
                $v1RB = $('input[name=v1rb]'),
                $v2RB = $('input[name=v2rb]'),
                $v1Display = $('#version1-number'),
                $v2Display = $('#version2-number'),
                $compareButton = $('#compare-selected-button').button().removeClass('hidden'),
                v1 = Number($('#version1-number').text()),
                v2 = Number($('#version2-number').text());

            function checkIfDiffIsEnabled( dontRedirect ) {
                if (!isNaN(v1) && !isNaN(v2)) {
                    $compareButton.button('enable');
                } else {
                    $compareButton.button('disable');
                }

                if (!isNaN(v1)) {
                    $v1Display.text(v1);
                    if (!dontRedirect) {
                        $.redirect( { v1 : v1 });
                    }

                }

                if (!isNaN(v2)) {
                    $v2Display.text(v2);
                    if (!dontRedirect) {
                        $.redirect( { v2 : v2 });
                    }
                }

            }

            function setV1Value(versionNumber) {
                v1 = versionNumber;
                $v1Input.val(v1);
                checkIfDiffIsEnabled();
            }

            function setV2Value(versionNumber) {
                v2 = versionNumber;
                $v2Input.val(v2);
                checkIfDiffIsEnabled();
            }

            $v1RB.change(function() {
                setV1Value($(this).val());
            });

            $v2RB.change(function() {
                setV2Value($(this).val());
            });

            checkIfDiffIsEnabled(true);

            if (WIKI_SIDEBAR) {
                $('.wiki-titlebar-item').each(function () {
                    var $this = $(this),
                        $label = $('.wiki-titlebar-item-label', $this),
                        $content = $('.wiki-titlebar-item-popup', $this);
                    if ($content.length > 0) {
                        $content.remove();
                        $label.qtip({
                            content: {
                                text: $content
                            },
                            show: {
                                solo: true,
                                event: 'mouseenter click'
                            },
                            hide: {
                                delay: 100,
                                event: 'unfocus mouseleave',
                                fixed: true
                            },
                            position: {
                                at: 'bottom left'
                            },
                            style: {
                                classes: 'titlebarDropdownTip wikiTitlebarDropdownTip',
                                tip: false
                            },
                            events: {
                                toggle: function (event, api) {
                                    var enabled = event.type === 'tooltipshow';
                                    api.elements.target.toggleClass('hover', enabled);
                                }
                            }
                        });
                    }
                });
            }
        });

    });
}());
