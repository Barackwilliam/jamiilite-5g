from django.contrib.auth import get_user_model
from django.db import transaction

from billing.subscriptions import start_trial
from core.models import Owner


def create_owner_account(business_name, phone, password):
    """Akaunti mpya ya mmiliki: user (username = namba ya simu) + Owner + majaribio."""
    with transaction.atomic():
        user = get_user_model().objects.create_user(username=phone, password=password)
        owner = Owner.objects.create(user=user, business_name=business_name, phone=phone)
        start_trial(owner)
    return owner
