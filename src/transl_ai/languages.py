"""The languages the tool translates between, and how each one counts.

They are the languages TranslateGemma was evaluated on (the 55 WMT24++ pairs of
its technical report, without their regions) plus the official languages of the
European Union, under plain language codes: no regional locales.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from gettext import c2py


@dataclass(frozen=True)
class PluralForm:
    # A number that takes this form, shown to the model in place of %d.
    number: int
    # What the model is told %d stands for when the number cannot be used.
    hint: str


@dataclass(frozen=True)
class Language:
    name: str
    # The rule Godot applies to the locale, in gettext syntax, copied from its table
    # (core/string/locales.h). A file's plural rows follow the order of this rule.
    plural_rule: str
    # The header of the language's column in a file: the name Godot gives it.
    locale: str

    def form_of(self, number: int) -> int:
        """The plural form `number` takes, as an index into `plural_forms`."""
        return _parse(self.plural_rule)[1](number)

    @property
    def plural_forms(self) -> tuple[PluralForm, ...]:
        return _forms(self.plural_rule)


_NAMES = {
    "ar": "Arabic",
    "bg": "Bulgarian",
    "bn": "Bengali",
    "ca": "Catalan",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "et": "Estonian",
    "fa": "Persian",
    "fi": "Finnish",
    "fil": "Filipino",
    "fr": "French",
    "ga": "Irish",
    "gu": "Gujarati",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "is": "Icelandic",
    "it": "Italian",
    "ja": "Japanese",
    "kn": "Kannada",
    "ko": "Korean",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "ml": "Malayalam",
    "mr": "Marathi",
    "mt": "Maltese",
    "nl": "Dutch",
    "no": "Norwegian",
    "pa": "Punjabi",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sr": "Serbian",
    "sv": "Swedish",
    "sw": "Swahili",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh": "Chinese",
    "zu": "Zulu",
}

_PLURAL_RULES = (
    ("id ja ko th vi zh", "nplurals=1; plural=0;"),
    (
        "bg ca da de el en es et fi he hu it ml mr nl no pt sv sw ta te tr ur",
        "nplurals=2; plural=(n != 1);",
    ),
    ("fr pa", "nplurals=2; plural=(n > 1);"),
    ("bn fa gu hi kn zu", "nplurals=2; plural=(n==0 || n==1);"),
    ("is", "nplurals=2; plural=(n%10==1 && n%100!=11);"),
    (
        "fil",
        "nplurals=2; plural=(n==1 || n==2 || n==3 || (n%10!=4 && n%10!=6 && n%10!=9));",
    ),
    ("cs sk", "nplurals=3; plural=(n==1) ? 0 : (n>=2 && n<=4) ? 1 : 2;"),
    ("ga", "nplurals=3; plural=n==1 ? 0 : n==2 ? 1 : 2;"),
    (
        "hr ru sr uk",
        "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4"
        " && (n%100<10 || n%100>=20) ? 1 : 2);",
    ),
    (
        "lt",
        "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2"
        " && (n%100<10 || n%100>=20) ? 1 : 2);",
    ),
    ("lv", "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n != 0 ? 1 : 2);"),
    (
        "pl",
        "nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4"
        " && (n%100<10 || n%100>=20) ? 1 : 2);",
    ),
    (
        "ro",
        "nplurals=3; plural=n==1 ? 0 : (n==0 || (n%100 > 0 && n%100 < 20)) ? 1 : 2;",
    ),
    (
        "sl",
        "nplurals=4; plural=(n%100==1 ? 0 : n%100==2 ? 1 : n%100==3 || n%100==4"
        " ? 2 : 3);",
    ),
    (
        "mt",
        "nplurals=5; plural=(n==1 ? 0 : n==2 ? 1 : n==0 || (n%100>=3 && n%100<=10)"
        " ? 2 : n%100>=11 && n%100<=19 ? 3 : 4);",
    ),
    (
        "ar",
        "nplurals=6; plural=(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3"
        " && n%100<=10 ? 3 : n%100>=11 && n%100<=99 ? 4 : 5);",
    ),
)

# Godot renames these codes when it imports a file, so the column carries its name.
_GODOT_LOCALES = {"no": "nb"}

LANGUAGES = dict(
    sorted(
        (code, Language(_NAMES[code], rule, _GODOT_LOCALES.get(code, code)))
        for codes, rule in _PLURAL_RULES
        for code in codes.split()
    )
)


class UnknownLanguageError(ValueError):
    """Raised for a language code the tool does not know."""


def language(code: str) -> Language:
    try:
        return LANGUAGES[code]
    except KeyError:
        known = ", ".join(sorted(LANGUAGES))
        raise UnknownLanguageError(
            f"unknown language code {code!r}; known codes: {known}"
        ) from None


@cache
def _parse(rule: str) -> tuple[int, Callable[[int], int]]:
    declared = re.fullmatch(r"nplurals=(\d+); plural=(.+);", rule)
    if declared is None:
        raise ValueError(f"not a plural rule: {rule!r}")
    return int(declared.group(1)), c2py(declared.group(2))


@cache
def _forms(rule: str) -> tuple[PluralForm, ...]:
    count, form_of = _parse(rule)
    numbers: list[list[int]] = [[] for _ in range(count)]
    # 0 is tried last, so only a form that nothing else takes is shown with it.
    for number in (*range(1, 201), 0):
        numbers[form_of(number)].append(number)
    return tuple(PluralForm(found[0], _hint(found)) for found in numbers)


def _hint(numbers: list[int]) -> str:
    if numbers[0] == 1:
        return "singular, %d is exactly 1"
    if len(numbers) == 1:
        return f"plural, %d is exactly {numbers[0]}"
    *first, last = (str(number) for number in numbers[:3])
    return f"plural, %d is a number such as {', '.join(first)} or {last}"
