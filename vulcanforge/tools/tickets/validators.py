from datetime import datetime

from formencode import Schema, Invalid
from formencode.validators import OneOf, String


class DueDateValidator(String):
    messages = {"invalid": "Invalid Date"}

    def _to_python(self, value, state):
        value = super(DueDateValidator, self)._to_python(value, state)
        if value:
            try:
                datetime.strptime(value, '%m/%d/%Y')
            except ValueError:
                raise Invalid(self.message('invalid', state), value, state)
        return value


class MilestoneNameValidator(String):
    def _to_python(self, value, state):
        value = super(MilestoneNameValidator, self)._to_python(value, state)
        return value.replace('/', '-').replace('"', '')


class MilestoneSchema(Schema):
    new_name = MilestoneNameValidator()
    old_name = MilestoneNameValidator()
    description = String()
    due_date = DueDateValidator()
    complete = OneOf(['Open', 'Closed'])
