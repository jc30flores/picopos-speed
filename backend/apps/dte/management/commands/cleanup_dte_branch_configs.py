from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.dte.models import DTEBranchConfig


def _is_valid_nit(value: str | None) -> bool:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    return len(digits) == 14


class Command(BaseCommand):
    help = "Desactiva configuraciones DTE inválidas/duplicadas por branch y conserva la mejor config activa."

    def handle(self, *args, **options):
        total_disabled = 0
        branch_ids = list(
            DTEBranchConfig.objects.values_list("branch_id", flat=True).distinct()
        )
        for branch_id in branch_ids:
            configs = list(
                DTEBranchConfig.objects.filter(branch_id=branch_id).order_by("-updated_at", "-id")
            )
            if not configs:
                continue
            keeper = None
            for cfg in configs:
                if _is_valid_nit(cfg.emisor_nit):
                    keeper = cfg
                    break
            if keeper is None:
                keeper = configs[0]

            with transaction.atomic():
                if not keeper.is_active:
                    keeper.is_active = True
                    keeper.save(update_fields=["is_active", "updated_at"])
                for cfg in configs:
                    should_disable = cfg.id != keeper.id and (cfg.is_active or not _is_valid_nit(cfg.emisor_nit))
                    if should_disable:
                        cfg.is_active = False
                        cfg.save(update_fields=["is_active", "updated_at"])
                        total_disabled += 1

        self.stdout.write(self.style.SUCCESS(f"cleanup_dte_branch_configs: desactivadas {total_disabled} configuraciones."))
