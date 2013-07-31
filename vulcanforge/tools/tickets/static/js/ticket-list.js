(function ($) {
    function requery() {
        window.location = '?tool_q=' + q +
                '&limit=' + limit +
                '&page=' + page +
                '&sort=' + encodeURIComponent(sort);
    }

    /* ## bind ticket list events */
    /* ### sorting headers */
    $('th[data-sort]').click(function () {
        var old_sort = sort.split(',')[0].split(' '),
            new_sort = $(this).attr('data-sort'),
            split_sort = new_sort.split(','),
            new_dir;
        if (split_sort[0] !== old_sort[0]) {
            new_dir = 'asc';
        } else if (old_sort[1] === 'asc') {
            new_dir = 'desc';
        } else {
            new_dir = 'asc';
        }
        sort = $.map(split_sort, function(s, i) {
            return s + ' ' + new_dir;
        }).join(',');
        page = 0;
        requery();
    });

    $('.ticketRow:has(input[type="checkbox"]), .ticketRow:has(.artifact-link-container)').
        css('cursor', 'pointer').
        on('click', function (e) {
            var $row = $(this),
                $target = $(e.target),
                $checkbox = $row.find('input[type="checkbox"]'),
                $link = $row.find('a'),
                linkTarget = $link.attr('target');
            if (!$target.is('a, input, button, a *')) {
                if ($checkbox.length > 0) {
                    $checkbox.prop('checked', !$checkbox.prop('checked'));
                } else if ($link.length > 0) {
                    switch (e.which) {
                    case 2:
                        linkTarget = '_blank';
                        break;
                    default:
                        linkTarget = $link.attr('target') || '_self';
                        break;
                    }
                    window.open($link.attr('href'), linkTarget);
                }
            }
        });

    $('#lightbox_col_list').append($('#col_list_form'));
    $('#col_list_form').show();

    $('#col_list_form ul').sortable({
        stop:function () {
            $('li', $(this)).each(function (i, ele) {
                var $ele = $(ele);
                $ele.html($ele.html().replace(/columns-(.*?)\./g,
                        'columns-' + i + '.'))
            });
        }
    }).disableSelection();
})(jQuery);
