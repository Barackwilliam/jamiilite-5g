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
        self._language = override_settings(LANGUAGE_CODE="sw")
        self._language.enable()

    def teardown_test_environment(self, **kwargs):
        self._language.disable()
        super().teardown_test_environment(**kwargs)
