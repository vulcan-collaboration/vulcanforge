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

    $('.ticketRow:has(.ticketLink), .ticketRow:has(.artifact-link-container)')
            .css('cursor', 'pointer')
            .bind('click', function (e) {
                var target = $(e.target),
                    checkbox = $('input[type="checkbox"]', target);
                if (checkbox.length > 0) {
                    checkbox.click();
                } else if (!target.is('a, input, button')) {
                    var link = $('.ticketLink, a', $(this));
                    var href = link.attr('href');
                    var linkTarget = link.attr('target');
                    if (e.which === 1) {
                        if (linkTarget == undefined) {
                            window.location.href = href;
                        }
                        else {
                            window.open(href, linkTarget);
                        }
                    }
                    else if (e.which === 2) {
                        window.open(href, '_blank');
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
