from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0006_conversation_is_ai_enabled_automationtrigger"),
    ]

    operations = [
        migrations.AddField(
            model_name="broadcast",
            name="channel_type",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="broadcast",
            name="email_subject",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
