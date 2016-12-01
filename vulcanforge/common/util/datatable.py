from formencode import validators

DATATABLE_SCHEMA = {
    'iDisplayStart': validators.Int(min=0, if_empty=0),
    'iDisplayLength': validators.Int(max=100, if_empty=20),
    'sSearch': validators.String(),
    'bRegex': validators.StringBool(),
    'iSortingCols': validators.Int(min=0),
    'sEcho': validators.Int()
}
