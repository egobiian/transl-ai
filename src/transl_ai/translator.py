"""Translate one text through a backend."""

from transl_ai.backends import Backend
from transl_ai.godot_csv import Entry
from transl_ai.prompts import build_context, build_messages

NEWLINE_ESCAPE = "\\n"


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


def translate_entry(backend: Backend, entry: Entry, *, source: str, target: str) -> str:
    context = build_context(
        entry.key, context=entry.context, plural_form=entry.plural_form
    )
    return translate(backend, entry.text, source=source, target=target, context=context)


def _without_added_period(source: str, reply: str) -> str:
    # The model closes short texts with a period the source does not have, and no
    # instruction talks it out of that.
    added = reply.endswith(".") and not reply.endswith("..")
    if added and not source.endswith("."):
        return reply[:-1]
    return reply
