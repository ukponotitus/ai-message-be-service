from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0005_broadcast_business_customfield_socialaccount_tag_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="is_ai_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="AutomationTrigger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("keyword", models.CharField(max_length=200)),
                ("response_text", models.TextField(blank=True, default="")),
                ("action_type", models.CharField(choices=[("reply", "Reply with text"), ("tag", "Tag contact"), ("notify", "Notify owner")], default="reply", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="triggers", to="automation.business")),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("business", "keyword")},
            },
        ),
    ]
