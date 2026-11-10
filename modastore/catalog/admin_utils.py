from django.contrib import admin

from catalog.templatetags.jalali import jdatetime_num


def jalali_column(field, label):
    """Read-only Jalali display of a datetime field.

    Assign it in a ModelAdmin/Inline class body and use its attribute name in
    list_display, readonly_fields or fieldsets. Sorting uses the real field.
    """
    @admin.display(description=label, ordering=field)
    def column(self, obj):
        return jdatetime_num(getattr(obj, field, None)) or '—'

    return column