"""Translate texts, and whole documents, through a backend."""

import re
from collections.abc import Callable

from transl_ai.backends import Backend
from transl_ai.godot_csv import Document, MissingLocaleError
from transl_ai.languages import PluralForm, language
from transl_ai.prompts import build_context, build_messages

NEWLINE_ESCAPE = "\\n"
COUNT_PLACEHOLDER = "%d"
# The full stops of the scripts the model writes in: Latin and Cyrillic, Chinese
# and Japanese, Devanagari and Bengali, and Urdu.
FULL_STOPS = (".", "\u3002", "\u0964", "\u06d4")

Progress = Callable[[int, int], None]


def translate(
    backend: Backend,
    text: str,
    *,
    source: str,
    target: str,
    context: str | None = None,
) -> str:
    # The model turns the \n escape into a real line break about half the time, so
    # it only ever sees real line breaks and the escape is put back afterwards.
    escaped = NEWLINE_ESCAPE in text and "\n" not in text
    prompt_text = text.replace(NEWLINE_ESCAPE, "\n") if escaped else text
    messages = build_messages(
        prompt_text, source=source, target=target, context=context
    )
    reply = backend.complete(messages).strip()
    if escaped:
        reply = reply.replace("\n", NEWLINE_ESCAPE)
    return _without_added_period(text, reply)


def locale_column(document: Document, code: str) -> int | None:
    """The column of a language: under Godot's name for it, or else its code."""
    column = document.column(language(code).locale)
    return column if column is not None else document.column(code)


def translate_document(
    backend: Backend,
    document: Document,
    *,
    source: str,
    target: str,
    progress: Progress | None = None,
) -> int:
    """Fill the `target` column from the `source` one; return how many texts.

    A message that already has a text in `target` is left alone.
    """
    source_language = language(source)
    target_language = language(target)
    source_column = locale_column(document, source)
    if source_column is None:
        raise MissingLocaleError(f"the file has no {source_language.locale!r} column")
    target_column = locale_column(document, target)
    if target_column is None:
        target_column = document.add_locale(target_language.locale)

    pending = [
        block
        for block in document.messages()
        if block.forms(source_column) and not block.forms(target_column)
    ]
    forms = target_language.plural_forms
    total = sum(len(forms) if block.plural else 1 for block in pending)
    done = 0
    for block in pending:
        texts = block.forms(source_column)
        # The target language decides how many plural forms a message gets, and
        # each is translated from the source text for the same number.
        for index, form in enumerate(forms if block.plural else (None,)):
            if form is None:
                text = texts[0]
            else:
                text = texts[min(source_language.form_of(form.number), len(texts) - 1)]
            translation = _translate_form(
                backend,
                text,
                form,
                source=source,
                target=target,
                key=block.key,
                context=block.context,
            )
            document.set_form(block, index, target_column, translation)
            done += 1
            if progress is not None:
                progress(done, total)
    document.declare_plural_rule(target_column, target_language.plural_rule)
    return done


def _translate_form(
    backend: Backend,
    text: str,
    form: PluralForm | None,
    *,
    source: str,
    target: str,
    key: str,
    context: str,
) -> str:
    if form is None:
        described = build_context(key, context=context)
        return translate(backend, text, source=source, target=target, context=described)
    # With a bare %d the model reads "many" and inflects the noun wrongly, so it
    # translates the text with a real number that is swapped back afterwards.
    if text.count(COUNT_PLACEHOLDER) == 1:
        numbered = translate(
            backend,
            text.replace(COUNT_PLACEHOLDER, str(form.number)),
            source=source,
            target=target,
            context=build_context(key, context=context),
        )
        restored = _with_placeholder(numbered, form.number)
        if restored is not None:
            return restored
    # The number came back as a word, twice or not at all: describe the form instead.
    described = build_context(key, context=context, plural_hint=form.hint)
    return translate(backend, text, source=source, target=target, context=described)


def _with_placeholder(reply: str, number: int) -> str | None:
    """Put %d back where `number` stands, if it stands in exactly one place."""
    # \d and int() cover the digits of every script, such as Arabic or Devanagari.
    found = [match for match in re.finditer(r"\d+", reply) if int(match[0]) == number]
    if len(found) != 1:
        return None
    return reply[: found[0].start()] + COUNT_PLACEHOLDER + reply[found[0].end() :]


def _without_added_period(source: str, reply: str) -> str:
    # The model closes short texts with a full stop the source does not have, and
    # no instruction talks it out of that.
    added = reply.endswith(FULL_STOPS) and not reply.endswith("..")
    if added and not source.endswith(FULL_STOPS):
        return reply[:-1]
    return reply
