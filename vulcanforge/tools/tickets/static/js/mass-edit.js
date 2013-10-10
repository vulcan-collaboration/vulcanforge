$(function () {
    $('#assigned_to').val('');

    $('#tracker_mass_edit_form').
        on('change', '.ticketRow :checkbox', function (eventObject) {
            var allChecked = $('.ticketRow :checkbox:not(:checked)').length === 0;
            $('#select_all').prop('checked', allChecked);
        }).
        on('change', '#select_all', function (eventObject) {
            $('.ticketRow :checkbox').prop('checked', $(this).prop('checked'));
        });
});
