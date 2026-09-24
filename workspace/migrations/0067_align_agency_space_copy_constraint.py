# Generated manually to align migration state with models.AgencySpaceCopy.Meta.constraints

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workspace", "0066_remove_agencyspacecopy_agency_space_copy_kind_shape_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="agencyspacecopy",
            name="agency_space_copy_kind_shape",
        ),
        migrations.AddConstraint(
            model_name="agencyspacecopy",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(target_kind="property", copied_customer__isnull=True)
                    | models.Q(target_kind="customer", copied_property__isnull=True)
                ),
                name="agency_space_copy_kind_shape",
            ),
        ),
    ]
