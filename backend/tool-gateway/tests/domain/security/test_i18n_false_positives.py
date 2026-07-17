import pytest

from cys_core.domain.security.sanitizer import InjectionVerdict, InputSanitizer


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "Authorized scope: repo acme/webapp, read-only SAST",
        "Проанализируйте устаревшие рекомендации по CVE-2024-1234 без изменения конфигурации",
        "Режим read-only сканирования в рамках согласованного scope",
        "Оцените соответствие политике compliance для внутреннего аудита",
        "Сеть: проверьте открытые порты на edge-роутере в dev-сегменте",
    ],
)
def test_legitimate_ru_assessment_phrases_not_blocked(text: str):
    assert InputSanitizer().classify(text) is InjectionVerdict.NONE
