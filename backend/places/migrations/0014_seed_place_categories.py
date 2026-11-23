from django.db import migrations


DEFAULT_CATEGORIES = ('Restaurant', 'Cafe', 'Park', 'Other')


def add_default_categories(apps, schema_editor):
    Category = apps.get_model('places', 'Category')
    database = schema_editor.connection.alias

    for name in DEFAULT_CATEGORIES:
        if not Category.objects.using(database).filter(name__iexact=name).exists():
            Category.objects.using(database).create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0013_review_unique_review_per_place_user'),
    ]

    operations = [
        migrations.RunPython(add_default_categories, migrations.RunPython.noop),
    ]
