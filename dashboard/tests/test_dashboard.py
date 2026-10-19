from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing import wallet
from billing.models import LedgerEntry, Payment, Voucher, Withdrawal
from billing.services import start_payment
from core.models import Package, RouterCommand
from core.tests.factories import make_owner, make_package, make_router

FEES = {"JAMIILITE_MONTHLY_FEE": 10000, "JAMIILITE_MIN_WITHDRAWAL": 1000, "JAMIILITE_SALE_FEE_PERCENT": 0}


def give_balance(owner, amount):
    LedgerEntry.objects.create(owner=owner, kind=LedgerEntry.Kind.ADJUSTMENT, amount=amount)


class SignupLoginTests(TestCase):
    def test_signup_logs_in_and_starts_trial(self):
        response = self.client.post(reverse("dashboard:signup"), {
            "business_name": "Neema WiFi", "phone": "0712 345 678",
            "password1": "Sinza-wifi-2026", "password2": "Sinza-wifi-2026",
        })
        self.assertRedirects(response, reverse("dashboard:home"))
        owner = response.wsgi_request.user.owner
        self.assertEqual(owner.user.username, "255712345678")
        self.assertTrue(owner.is_in_trial())

    def test_duplicate_phone_is_refused(self):
        make_owner(username="255712345678")
        response = self.client.post(reverse("dashboard:signup"), {
            "business_name": "Nyingine", "phone": "+255 712 345 678",
            "password1": "Sinza-wifi-2026", "password2": "Sinza-wifi-2026",
        })
        self.assertContains(response, "tayari ina akaunti")

    def test_login_with_phone_in_any_format(self):
        make_owner(username="255712345678")
        response = self.client.post(reverse("dashboard:login"), {"phone": "0712345678", "password": "test-pass-123"})
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_wrong_password(self):
        make_owner(username="255712345678")
        response = self.client.post(reverse("dashboard:login"), {"phone": "0712345678", "password": "si-yenyewe"})
        self.assertContains(response, "si sahihi")

    def test_login_ignores_external_next(self):
        make_owner(username="255712345678")
        response = self.client.post(reverse("dashboard:login"), {
            "phone": "0712345678", "password": "test-pass-123", "next": "https://evil.example/",
        })
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response["Location"])

    def test_suspended_owner_is_blocked(self):
        owner = make_owner(is_active=False)
        self.client.force_login(owner.user)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "imesitishwa", status_code=403)


@override_settings(PAYMENT_PROVIDER="sandbox", ALLOW_SANDBOX_PAYMENTS=True, **FEES)
class OwnerPagesTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.client.force_login(self.owner.user)

    def test_every_page_renders(self):
        router = make_router(self.owner, nas_identifier="jl-x")
        package = make_package(self.owner)
        start_payment(router=router, package=package, phone="255712345678")
        for name, args in [
            ("home", []), ("routers", []), ("router_detail", [router.pk]), ("packages", []),
            ("package_edit", [package.pk]), ("vouchers", []), ("sales", []), ("wallet", []),
            ("subscription", []), ("settings", []),
        ]:
            with self.subTest(page=name):
                response = self.client.get(reverse(f"dashboard:{name}", args=args))
                self.assertEqual(response.status_code, 200)

    def test_home_shows_todays_sales(self):
        router = make_router(self.owner)
        start_payment(router=router, package=make_package(self.owner, price=1500), phone="255712345678")
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "Tsh 1,500")
        self.assertContains(response, 'class="chart-mark"')

    def test_adding_router_sets_nas_identifier_and_shows_setup_line(self):
        response = self.client.post(reverse("dashboard:routers"), {"name": "Duka la Kati", "location": "Sinza"})
        router = self.owner.routers.get()
        self.assertRedirects(response, reverse("dashboard:router_detail", args=[router.pk]))
        self.assertEqual(router.nas_identifier, f"jl-{router.slug}")
        detail = self.client.get(reverse("dashboard:router_detail", args=[router.pk]))
        self.assertContains(detail, router.provision_token)

    def test_router_commands(self):
        router = make_router(self.owner)
        self.client.post(reverse("dashboard:router_detail", args=[router.pk]), {"action": "reboot"})
        self.assertEqual(RouterCommand.objects.get().action, RouterCommand.Action.REBOOT)

    def test_owner_cannot_see_another_owners_router_or_package(self):
        other = make_owner(username="mwingine", business_name="Mwingine")
        router = make_router(other)
        package = make_package(other)
        self.assertEqual(self.client.get(reverse("dashboard:router_detail", args=[router.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("dashboard:package_edit", args=[package.pk])).status_code, 404)
        self.client.post(reverse("dashboard:router_detail", args=[router.pk]), {"action": "reboot"})
        self.assertFalse(RouterCommand.objects.exists())

    def test_package_create_and_edit(self):
        self.client.post(reverse("dashboard:packages"), {
            "name": "Siku 1", "price": 1000, "duration_value": 1, "duration_unit": 1440,
            "rate_limit": "2M/5M", "shared_users": 2, "is_active": "on",
        })
        package = Package.objects.get()
        self.assertEqual((package.duration_minutes, package.rate_limit, package.shared_users), (1440, "2M/5M", 2))

        edit = self.client.get(reverse("dashboard:package_edit", args=[package.pk]))
        self.assertEqual(edit.context["form"].initial["duration_unit"], 1440)
        self.client.post(reverse("dashboard:package_edit", args=[package.pk]), {
            "name": "Siku 1", "price": 1200, "duration_value": 1, "duration_unit": 1440,
            "rate_limit": "", "shared_users": 1,
        })
        package.refresh_from_db()
        self.assertEqual((package.price, package.is_active), (1200, False))

    def test_voucher_batch_and_print(self):
        router = make_router(self.owner)
        package = make_package(self.owner)
        response = self.client.post(reverse("dashboard:vouchers"), {"package": package.pk, "router": router.pk, "count": 5})
        batch = Voucher.objects.values_list("batch", flat=True).first()
        self.assertRedirects(response, reverse("dashboard:voucher_print", args=[batch]))
        self.assertEqual(Voucher.objects.filter(batch=batch).count(), 5)
        page = self.client.get(response["Location"])
        for voucher in Voucher.objects.all():
            self.assertContains(page, voucher.code)
        listing = self.client.get(reverse("dashboard:vouchers"))
        self.assertContains(listing, "Saa 1 × 5")

    def test_vouchers_blocked_when_subscription_expired(self):
        self.owner.trial_ends_at = timezone.now() - timedelta(days=1)
        self.owner.save()
        router = make_router(self.owner)
        package = make_package(self.owner)
        response = self.client.post(reverse("dashboard:vouchers"), {"package": package.pk, "router": router.pk, "count": 5})
        self.assertRedirects(response, reverse("dashboard:subscription"))
        self.assertFalse(Voucher.objects.exists())

    def test_print_page_is_private(self):
        other = make_owner(username="mwingine", business_name="Mwingine")
        Voucher.objects.create(router=make_router(other), package=make_package(other), batch="abc123")
        self.assertEqual(self.client.get(reverse("dashboard:voucher_print", args=["abc123"])).status_code, 404)

    def test_withdraw(self):
        give_balance(self.owner, 25000)
        self.client.post(reverse("dashboard:wallet"), {"amount": 20000, "phone": "0712345678"})
        self.assertEqual(Withdrawal.objects.get().amount, 20000)
        self.assertEqual(wallet.balance(self.owner), 5000)

    def test_withdraw_more_than_balance(self):
        give_balance(self.owner, 5000)
        response = self.client.post(reverse("dashboard:wallet"), {"amount": 20000, "phone": "0712345678"})
        self.assertContains(response, "halitoshi")
        self.assertFalse(Withdrawal.objects.exists())

    def test_pay_subscription_from_balance(self):
        give_balance(self.owner, 30000)
        self.client.post(reverse("dashboard:subscription"), {"months": "3"})
        self.owner.refresh_from_db()
        self.assertEqual(wallet.balance(self.owner), 0)
        self.assertGreater(self.owner.paid_until, timezone.now() + timedelta(days=89 + 14))

    def test_sales_page_lists_only_own_sales(self):
        mine = make_router(self.owner)
        other = make_owner(username="mwingine", business_name="Mwingine")
        start_payment(router=mine, package=make_package(self.owner, price=700), phone="255712345678")
        start_payment(router=make_router(other), package=make_package(other, price=900), phone="255712345679")
        response = self.client.get(reverse("dashboard:sales"))
        self.assertEqual(list(response.context["page"].object_list), list(Payment.objects.filter(router=mine)))

    def test_superuser_without_owner_goes_to_control(self):
        from django.contrib.auth import get_user_model

        admin = get_user_model().objects.create_superuser("boss", password="x-pass-123")
        self.client.force_login(admin)
        self.assertRedirects(self.client.get(reverse("dashboard:home")), reverse("control:home"))
