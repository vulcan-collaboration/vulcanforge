(function(global){

    var VIS;

    function getParameterByName(name, myFrame){
        var frame = myFrame || window;
        name = name.replace(/[\[]/, "\\\[").replace(/[\]]/, "\\\]");
        var regexS = "[\\?&]" + name + "=([^&#]*)";
        var regex = new RegExp(regexS);
        var results = regex.exec(frame.location.search);
        if(results == null)
            return "";
        else
            return decodeURIComponent(results[1].replace(/\+/g, " "));
    }

    function _makeVisualizerUrl(method){
        var visualizerId = getParameterByName("processingVisualizerId") ||
                           global.location.pathname.split('/')[2];
        return '/visualize/' + visualizerId + '/' + method;
    }

    VIS = {
        "init": function(){
            var processingStatus;
            this.processingOverlay = null;
            this.config = {
                "loadingImg": null,
                "loadingMsg": "Processing File for Visualization",
                "processingUrl": null,
                "processingInitUrl": null,
                "loadingPollInterval": 5000
            };
            $(this).trigger("initConfig", this.config);
            processingStatus = this.getProcessingStatus();
            if (processingStatus === "loading"){
                this.createProcessingOverlay();
                this.pollProcessing();
            } else if (processingStatus === "error"){
                this.processingError();
            } else {
                $(this).trigger("ready");
            }
        },
        "getProcessingStatus": function(){
            return getParameterByName("processingStatus");
        },
        "getResourceUrl": function(){
            return getParameterByName("resource_url");
        },
        "getProcessResourceId": function(){
            return getParameterByName("processingResourceId");
        },
        "getProcessingPollUrl": function(){
            if (this.config.processingPollUrl === null){
                this.config.processingPollUrl = _makeVisualizerUrl('processed_status');
            }
            return this.config.processingPollUrl;
        },
        "createProcessingOverlay": function(){
            var processingContent;
            if (this.processingOverlay === null){
                this.processingOverlay = $('<div/>', {
                    "class": "processingOverlay"
                });
                processingContent = $('<div/>', {"class": "processingOverlayContent"});
                if (this.config.loadingImg){
                    processingContent.append(
                        $('<img/>', {
                            "src": this.config.loadingImg,
                            "class": "processingLoadingGif"
                        })
                    );
                }
                processingContent.append($('<h3/>', {
                        "text": this.config.loadingMsg
                }));
                this.processingOverlay.append(processingContent);
                $(document).find("body")
                    .css("min-height", 500)
                    .append(this.processingOverlay);
            }
        },
        "removeProcessingOverlay": function(){
            this.processingOverlay.remove();
            this.processingOverlay = null;
        },
        "pollProcessing": function(){
            var that = this;
            $.ajax({
                url: that.getProcessingPollUrl(),
                type: "GET",
                dataType: 'json',
                data: {"unique_id": that.getProcessResourceId()},
                success: function(response) {
                    if ($(that).trigger("pollComplete") === false){
                        return;
                    }
                    if (response['status'] == 'loading') {
                        setTimeout(that.pollProcessing, that.config.loadingPollInterval);
                    } else if (response['status'] == 'success') {
                        that.processingSuccess();
                    } else {
                        that.processingError();
                    }
                },
                error: this.processingError
            });
            setTimeout(function(){
                global.VIS.pollProcessing.call(global.VIS);
            }, this.config.loadingPollInterval);
            $(this).trigger("processingSuccess");
        },
        "processingSuccess": function(){
            this.removeProcessingOverlay();
            $(this).trigger("ready");
        },
        "processingError": function(){
            this.createProcessingOverlay();
            this.processingOverlay.find(".processingOverlayContent").html(
                $("<h3/>", {
                    "text": "There was an error processing this file for visualization"
                })
            ).append($("<span>You can </span>"))
             .append(
                    $("<a/>", {
                        "href": this.getResourceUrl(),
                        "text": "download the file"
                    }))
                .append($("<span> instead.</span>"));
        },

        /* events */
        "pollComplete": $.noop,
        "initConfig": $.noop,
        "ready": $.noop
    };

    global.VIS = VIS;

    $(document).ready(function(){
        global.VIS.init.call(global.VIS);
    });

}(window));