/*global window */

(function ( global ) {
    "use strict";

    // Import Globals
    var $ = global.jQuery,
        trace = global.trace,
        $vf = global.$vf;

    $vf.designSubmissionDataRenderers = {
        'Team Design Commit': function( $cell, data ) {

            var $commitLinkContainer = $( '<div/>', {
                'class': 'artifact-link-container rendering',
                'html': '<label>Commit:</label>'
            }), commitArtifactLink = new $vf.ArtifactLink({
                label: data.commit.label,
                iconURL: data.commit.iconURL,
                infoURL: data.commit.infoURL,
                extras: data.commit.extras,
                clickURL: data.commit.clickURL,
                artifactType: data.commit.artifactType,
                containerE: $commitLinkContainer,
                refId: data.commit.refId,
                showIcon: false,
                leftTrimmed: false
            } ),$designLinkContainer = $( '<div/>', {
                'class': 'artifact-link-container rendering',
                'html': '<label>Design:</label>'
            }), designArtifactLink = new $vf.ArtifactLink({
                label: data.design.label,
                iconURL: data.design.iconURL,
                infoURL: data.design.infoURL,
                extras: data.design.extras,
                clickURL: data.design.clickURL,
                artifactType: data.design.artifactType,
                containerE: $designLinkContainer,
                refId: data.design.refId,
                showIcon: false,
                leftTrimmed: false
            } ),
            $teamContainer = $('<div/>', {
                'html': '<label>Team:</label>'
            });


            $teamContainer.append($('<a/>', {
                'href': data.team.url,
                'text': data.team.shortname,
                'title': data.team.name
            }));

            $cell.append($teamContainer);

            $cell.append( $designLinkContainer );
            if (data.design.refId) {
                designArtifactLink.render();
            } else {
                $designLinkContainer.
                    removeClass('rendering').
                    append(data.design.label);
            }

            $cell.append( $commitLinkContainer );
            if (data.commit.refId) {
                commitArtifactLink.render();
            } else {
                $commitLinkContainer.
                    removeClass('rendering').
                    append("{repository deleted}");
            }


        },
        'Project and Design ArtifactLink': function( $cell, data ) {

            function renderDesignArtifact(dataItem, containerClass, containerTitle) {
                var $linkContainer = $('<div/>', {
                    'class': 'artifact-link-container rendering',
                    'html': '<div class="' + containerClass + '" title="' +
                             containerTitle + '"></div>'
                }), $artifactLink = new $vf.ArtifactLink({
                    label: dataItem.label,
                    iconURL: dataItem.iconURL,
                    infoURL: dataItem.infoURL,
                    extras: dataItem.extras,
                    clickURL: dataItem.clickURL,
                    artifactType: dataItem.artifactType,
                    containerE: $linkContainer,
                    refId: dataItem.refId,
                    showIcon: false,
                    leftTrimmed: false
                });

                $cell.append($linkContainer);
                $artifactLink.render();

                return {
                    "container": $linkContainer,
                    "artifactLink": $artifactLink
                };
            }

            renderDesignArtifact(data["project"], "pa-icon", "Project");
            renderDesignArtifact(data["design"], "design-icon", "Design");
            if (data["xme_file"]) {
                renderDesignArtifact(data["xme_file"], "xme-icon", "XME");
            }

        },
        'ArtifactLink': function( $cell, data ) {

            var $linkContainer = $( '<div/>', {
                'class': 'artifact-link-container rendering'
            }), artifactLink = new $vf.ArtifactLink({
                label: data.label,
                iconURL: data.iconURL,
                infoURL: data.infoURL,
                extras: data.extras,
                clickURL: data.clickURL,
                artifactType: data.artifactType,
                containerE: $linkContainer,
                refId: data.refId,
                showIcon: false,
                leftTrimmed: true
            });

            $cell.append( $linkContainer );
            artifactLink.render();

        },
        'Scoring Submission Status': function( $cell, data ) {

            var $detailsIcon, $detailsButton, detailRow, detailContent,
                detailOn = false;

            $detailsIcon = $( '<span/>' , {
                'class': 'icon ico-bars details-icon status ' + data.status,
                'title': data.status
            });

            function renderDetails(details){
                var subtitle, i, colspan = $cell.parent().children().length;
                detailContent = $('<div/>', {
                    'class': 'submission-details-container'
                }).append(
                    $('<h3/>', {
                        'class': "content-section-header",
                        'text': "Warnings"
                    })
                );
                for (subtitle in details){
                    detailContent.append(
                        $('<h4/>', {
                            'class': 'details-subtitle',
                            'text': subtitle
                        })
                    );
                    for (i = 0; i < details[subtitle].length; i++){
                        detailContent.append($('<p/>', {
                            "text": details[subtitle][i]
                        }));
                    }
                }
                detailRow = $('<tr/>', {
                    'class': 'details-row no-hover'
                }).append(
                    $('<td/>', {
                        'class': 'details-cell',
                        'colspan': colspan
                    }).append(
                        $('<div/>', {
                            'class': 'details-liner'
                        }).append(detailContent))
                );
                $cell.parent().after(detailRow);
            }

            $cell.qtip( {
                suppress: true,
                content: {
                    text: data.status
                },
                position: {
                    at: 'middle left',
                    my: 'middle right'
                },
                style: {
                    classes: 'vf-tutorial-tip design-submission-tip'
                }
            });

            $cell.append( $detailsIcon );

            if (data.details) {
                $detailsButton = $('<button/>', {
                    'class': 'details-expand-button',
                    title: 'Show details',
                    text: 'Details',
                    click: function() {
                        if (detailOn === true){
                            detailRow.hide();
                            detailOn = false;
                        }
                        else {
                            if (detailRow === undefined){
                                renderDetails(data.details);
                            }
                            detailRow.show();
                            detailOn = true;
                        }
                    }
                });
                $cell.append( $detailsButton );
            }

        },
        'Submission Status': function( $cell, data ) {

            var $detailsIcon,
                $detailsButton = $('<button/>', {
                    'class': 'details-expand-button',
                    title: 'Show details',
                    text: 'Details'
                } ),
                $hideDetailsButton = $('<button/>', {
                    'class': 'details-collapse-button',
                    title: 'Hide details',
                    html: 'Hide<br/>Details'
                } ),
                $detailsRow = $('<tr/>', {
                    'class': 'details-row no-hover'
                }),
                $detailsCell = $('<td/>', {
                    'class': 'details-cell'
                } ),
                $detailsLiner = $('<div/>', {
                    'class': 'details-liner'
                }).
                    appendTo($detailsCell),
                $detailsConnector = $('<div/>', {
                    'class': 'details-connector'
                } ) .html('<svg width="5px" height="30px" viewBox = "0 0 5 30" version = "1.1" fill="#333" stroke="#333" stroke-width="2"><line x1="2.5" y1="0" x2="2.5" y2="25" stroke-width="1"/><circle cx="2.5" cy="27.5" r="2.5" stroke-width="0"/></svg>');

            $detailsIcon = $( '<span/>' , {
                'class': 'icon details-icon status ' + data.status,
                'title': data.status
            });

            if (data.status !== 'error') {
                $detailsIcon.addClass('ico-bars');
            } else {
                $detailsIcon.text('error');
            }

            $detailsIcon.qtip( {
                suppress: true,
                content: {
                    text: (data.status === 'failed') ? 'Non-manufacturable' : data.status
                },
                position: {
                    at: 'middle right',
                    my: 'middle left'
                },
                style: {
                    classes: 'vf-tutorial-tip'
                }
            });

            $cell.append( $detailsIcon );

            $cell.append( $detailsButton );
            $cell.append( $hideDetailsButton.hide() );
            $cell.append(  $detailsConnector.hide() );

            $detailsButton.click( function() {
                var colspan = $cell.parent().children().length,
                    loadingSpinner;

                $detailsCell.attr('colspan', colspan);
                $cell.parent().after( $detailsRow );

                $detailsRow.append( $detailsCell );
                loadingSpinner = new $vf.PleaseWait('Loading details', $detailsLiner);
                loadingSpinner.update();
                loadingSpinner.show();
                $.ajax({
                    url: data.detail_url,
                    success: function (responseData) {
                        loadingSpinner.hide();
                        $detailsLiner.showManufacturabilityDetails({
                            data: responseData
                        });
                    },
                    error: function () {
                        loadingSpinner.hide();
                        $detailsLiner.text('processing...');
                    }
                });

                $cell.parent().addClass('no-hover');

                $detailsButton.hide();
                $hideDetailsButton.show();
                $detailsConnector.show();
            });

            $hideDetailsButton.click( function() {
                $detailsRow.remove();

                $detailsButton.show();
                $hideDetailsButton.hide();
                $detailsConnector.hide();

                $cell.parent().removeClass('no-hover');
            });
        },
        'Link': function ($cell, data) {
            $('<a/>', data).appendTo($cell);
        },
        'Chosen': function ($cell, data) {
            if (data.chosen) {
                $cell.
                    parent().
                    addClass('chosenOne');
            } else {
                $('<a/>', {
                    text: 'choose',
                    href: data.choose_url
                }).appendTo($cell);
            }
        }
    }

}( window ));
