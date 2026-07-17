# Merge conflicting shop 0011 leaves:
# - 0011_planfunnelevent_event_types (repo)
# - 0011_rename_shop_planfu_... (created on server)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0011_planfunnelevent_event_types'),
        ('shop', '0011_rename_shop_planfu_event_t_8a1b0d_idx_shop_planfu_event_t_992d53_idx_and_more'),
    ]

    operations = []
