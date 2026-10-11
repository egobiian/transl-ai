"""Prompts sent to the translation model."""

from typing import Literal, TypedDict

LANGUAGE_NAMES = {
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "ru": "Russian",
}

# Each rule answers a failure measured on examples/translations.csv. Its GOOD/BAD pair
# shows that failure on another sentence, so the prompt does not memorise the sample.
# Rule 4 has no pair on purpose: a BAD line in Russian made the model copy it.
# The final period and the \n escape are repaired in translator.py instead, because
# instructions for them made no difference.
# Rule 3 escapes the lone Cyrillic capital U: on its own it reads as a Latin Y.
SYSTEM_RULES = "\n".join(
    (
        "The text is a string from a video game. Translate it following these rules.",
        "",
        "1. Keep the grammatical number of the source. A singular source stays"
        " singular, even when the number is the %d placeholder.",
        '   GOOD: "Te queda %d vida" -> "You have %d life left"',
        '   BAD:  "Te queda %d vida" -> "You have %d lives left"',
        "",
        "2. Keep the grammatical gender of the source wherever the target language"
        " marks gender. Never write both genders.",
        '   GOOD: "%s está cansada." -> "%s est fatiguée."',
        '   BAD:  "%s está cansada." -> "%s est fatigué(e)."',
        "",
        '3. Address the player the way the source does. Spanish "tú" is informal:'
        " use the informal second person, never the formal one.",
        '   GOOD: "Tienes una llave." -> French "Tu as une clé." / German "Du hast'
        ' einen Schlüssel." / Russian "\u0423 тебя есть ключ."',
        '   BAD:  "Tienes una llave." -> French "Vous avez une clé." / German "Sie'
        ' haben einen Schlüssel." / Russian "\u0423 вас есть ключ."',
        "",
        "4. A context of male or female is the gender of the player being addressed."
        " Use it only where the target language marks the gender of the person"
        " addressed; otherwise translate neutrally. The speaker never has a gender.",
        "",
        "The examples only illustrate the rules. Translate into the requested"
        " language.",
        "",
    )
)

CONTEXT_LINE = (
    "Context to pick the right meaning (do not translate it or mention it): {context}\n"
)

# Without these the model reads %d as "many" and translates a singular as a plural.
# They assume a source language with two plural forms, the singular first.
SINGULAR_HINT = "plural form: singular, %d is exactly 1"
PLURAL_HINT = "plural form: plural, %d is 2 or more"

# The single user message TranslateGemma documents. The two blank lines before the
# text are part of the format.
USER_PROMPT = (
    "You are a professional {source_name} ({source}) to {target_name} ({target})"
    " translator. Your goal is to accurately convey the meaning and nuances of the"
    " original {source_name} text while adhering to {target_name} grammar,"
    " vocabulary, and cultural sensitivities.\n"
    "Produce only the {target_name} translation, without any additional"
    " explanations or commentary. Please translate the following {source_name}"
    " text into {target_name}:\n\n\n{text}"
)


class Message(TypedDict):
    role: Literal["system", "user"]
    content: str


class UnknownLanguageError(ValueError):
    """Raised for a language code the prompt has no name for."""


def language_name(code: str) -> str:
    try:
        return LANGUAGE_NAMES[code]
    except KeyError:
        known = ", ".join(sorted(LANGUAGE_NAMES))
        raise UnknownLanguageError(
            f"unknown language code {code!r}; known codes: {known}"
        ) from None


def build_context(
    key: str, *, context: str = "", plural_form: int | None = None
) -> str:
    """Describe a text to the model with what its row says about it."""
    parts = [f"translation key {key}"]
    if context:
        parts.append(f"context: {context}")
    if plural_form is not None:
        parts.append(SINGULAR_HINT if plural_form == 0 else PLURAL_HINT)
    return "; ".join(parts)


def build_messages(
    text: str, *, source: str, target: str, context: str | None = None
) -> list[Message]:
    system = SYSTEM_RULES
    if context:
        system += CONTEXT_LINE.format(context=context)
    user = USER_PROMPT.format(
        source=source,
        source_name=language_name(source),
        target=target,
        target_name=language_name(target),
        text=text,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
