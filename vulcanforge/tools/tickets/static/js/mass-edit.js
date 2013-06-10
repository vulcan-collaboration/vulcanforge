$(function(){
    $('#assigned_to').val('');
    $('#select_all').click(function(){
        if(this.checked){
            $('.ticket-list input[type=checkbox]').attr('checked', 'checked');
        }
        else{
            $('.ticket-list input[type=checkbox]').removeAttr('checked');
        }
    });
});
