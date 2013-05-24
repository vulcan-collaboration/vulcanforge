function render_edit_btn(container){
    container.html(
        $('<a/>', {href: "#"})
            .append($('<b/>', {"class": "has-icon ico-edit icon", "data-icon": "p"}))
            .click(function(){
                /* prepare for edit */
                var row = $(this).parents('tr.visualizer_row').first();
                var active_container = row.find('.visualizer_active');
                var is_active = active_container.find('span.original').text() == 'True';

                /* cancel other edits */
                row.siblings().each(function(i, el){
                    cancel_edit($(el));
                });
                row.addClass('vediting');


                /* archive uploader */
                row.find('.visualizer_name').append(
                    $('<input/>', {
                        "type": "file",
                        "class": "text",
                        "name": "archive"
                    }).change(function(){render_save_btn(container);})
                ).find('.original').hide();

                /* active */
                active_container.append(
                    $('<input/>', {
                        "type": "checkbox",
                        "name": "active",
                        "checked": is_active
                    }).change(function(){render_save_btn(container);})
                ).find('.original').hide();

                container.html('');
                $('#visualizer').val(row.find('.visualizer_id').text());
                render_delete_btn(row);
                return false;
            })
    );
}
function render_save_btn(container){
    container.html(
        $('<input/>', {"type": "submit", "value": "Save"})
    );
}
function render_delete_btn(row){
    row.find('.delete_btn_container').first().html(
        $('<input/>', {"type": "submit", "value": "Delete", "name": "delete"})
    );
}
function cancel_edit(row){
    if (row.hasClass('vediting')){
        row.find('.original').show().siblings().remove();
        render_edit_btn(row.find('.btn_container'));
        row.removeClass('vediting');
    }
}

$(document).ready(function(){
    $('.btn_container').each(function(){
        render_edit_btn($(this));
    });
    $('#add_visualizer').click(function(){
        $('#add_visualizer_form').show();
        return false;
    });
    $('#add_visualizer_cancel').click(function(){
        $('#add_visualizer_form').hide();
        $('#archive').val('');
        return false;
    });
    $('#visualizers > tbody').sortable({
        update: function(ev, ui){
            $.ajax({
                url: 'set_priority',
                type: "POST",
                data: {
                    _session_id: $.cookie('_session_id'),
                    visualizers: $('table#visualizers').find('.visualizer_id').map(function(){return $(this).text();}).get().join(',')
                },
                dataType: "json",
                success: function(response){
                    return;
                },
                error: function(error, param2){
                    trace("Visualizer Priority Change Error");
                }
            });
        }
    });
});