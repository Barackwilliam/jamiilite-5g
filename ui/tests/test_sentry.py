from django.test import SimpleTestCase

from config import sentry


class SentryPrivacyTests(SimpleTestCase):
    def test_router_secrets_are_hidden_from_error_reports(self):
        event = {
            "request": {"url": "https://jamiilite.onrender.com/r/AbC_123-xyz/checkin", "query_string": ""},
            "transaction": "/r/AbC_123-xyz/setup.rsc",
        }
        cleaned = sentry.before_send(event, {})
        self.assertEqual(cleaned["request"]["url"], "https://jamiilite.onrender.com/r/[siri]/checkin")
        self.assertEqual(cleaned["transaction"], "/r/[siri]/setup.rsc")

    def test_other_addresses_are_left_alone(self):
        event = {"request": {"url": "https://jamiilite.onrender.com/dashboard/"}}
        self.assertEqual(sentry.before_send(event, {})["request"]["url"], "https://jamiilite.onrender.com/dashboard/")
