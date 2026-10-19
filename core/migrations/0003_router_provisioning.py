import django.db.models.deletion
from django.db import migrations, models

import core.models


def give_each_router_a_token(apps, schema_editor):
    Router = apps.get_model("core", "Router")
    for router in Router.objects.filter(provision_token__isnull=True):
        router.provision_token = core.models.generate_provision_token()
        router.save(update_fields=["provision_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_radius_support"),
    ]

    operations = [
        # Hatua 1-3: kila router iliyopo ipate token yake (default ya callable
        # ingeipa kila router token ile ile na unique ingeshindwa).
        migrations.AddField(
            model_name="router",
            name="provision_token",
            field=models.CharField(max_length=64, null=True, editable=False),
        ),
        migrations.RunPython(give_each_router_a_token, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="router",
            name="provision_token",
            field=models.CharField(
                default=core.models.generate_provision_token,
                editable=False,
                help_text="Siri iliyo kwenye link ya usanidi na ripoti za router. Usiitoe hadharani.",
                max_length=64,
                unique=True,
                verbose_name="token ya usanidi",
            ),
        ),
        migrations.AddField(
            model_name="router",
            name="last_seen_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="ilionekana mara ya mwisho"),
        ),
        migrations.AddField(
            model_name="router",
            name="routeros_version",
            field=models.CharField(blank=True, max_length=60, verbose_name="toleo la RouterOS"),
        ),
        migrations.AddField(
            model_name="router",
            name="uptime",
            field=models.CharField(blank=True, max_length=40, verbose_name="muda iliowaka"),
        ),
        migrations.AddField(
            model_name="router",
            name="active_clients",
            field=models.PositiveIntegerField(default=0, verbose_name="wateja online"),
        ),
        migrations.CreateModel(
            name="RouterCommand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("reboot", "Washa upya (reboot)"),
                            ("reapply_setup", "Weka upya usanidi wa JamiiLite"),
                        ],
                        max_length=20,
                        verbose_name="agizo",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True, verbose_name="lilipokelewa")),
                (
                    "router",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commands",
                        to="core.router",
                        verbose_name="router",
                    ),
                ),
            ],
            options={
                "verbose_name": "agizo la router",
                "verbose_name_plural": "maagizo ya router",
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(
                        condition=models.Q(("delivered_at__isnull", True)),
                        fields=["router", "created_at"],
                        name="routercommand_pending_idx",
                    )
                ],
            },
        ),
    ]
