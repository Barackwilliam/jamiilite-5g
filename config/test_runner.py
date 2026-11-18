"""
Majaribio mengi ya zamani yanakagua maandishi ya Kiswahili (msgid), yaliyoandikwa wakati
Kiswahili kilikuwa lugha ya msingi. Hapa yanaendeshwa kwa Kiswahili kama msingi; majaribio
ya lugha yenyewe yanatumia @override_settings(LANGUAGE_CODE="en") kuiga mfumo halisi.
"""
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class SwahiliBaselineRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        # Cache ya kumbukumbu, na kurasa/mipangilio havihifadhiwi kati ya majaribio (kila jaribio
        # linaona mabadiliko yake mara moja). Majaribio ya cache yenyewe yanaiwasha.
        self._language = override_settings(
            LANGUAGE_CODE="sw",
            JAMIILITE_CACHE_PAGES=False,
            CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        )
        self._language.enable()

    def teardown_test_environment(self, **kwargs):
        self._language.disable()
        super().teardown_test_environment(**kwargs)
