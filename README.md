# transl-ai

Translates a Godot CSV localization file, or a plain text file, into other languages with an AI model: one running on your machine through Ollama, or one from OpenAI or Anthropic.

[Léelo en español](README.es.md)

**Status: 0.1.0, early.** This is machine translation. Read the result before you ship it, and read [Known problems](#known-problems) first.

## What it does

- Adds a column per target language to a Godot translation CSV and fills it in.
- Understands the `?context` and `?plural` columns: each language gets the number of plural forms Godot expects for it.
- Keeps `\n` escapes as they are and removes a final period the source did not have. Placeholders (`%s`, `%d`, `{name}`) and BBCode tags are left to the model.
- Never changes what is already in the file: a message that already has a translation is skipped.
- Translates plain text files one paragraph at a time.

## Requirements

- Python 3.12 or later and [uv](https://docs.astral.sh/uv/).
- One model provider:
  - **Ollama** (default): free and local. The model is an 8 GB download.
  - **OpenAI** or **Anthropic**: an API key. You pay them per use and your texts are sent to them.
- Godot 4.6 or later, only if your CSV uses `?context` or `?plural`.

## Install

It is not on PyPI. Install it from this repository:

```
uv tool install git+https://github.com/egobiian/transl-ai
```

For the default provider, install [Ollama](https://ollama.com/download) and download the model:

```
ollama pull translategemma:12b
```

## Use

```
transl-ai translations.csv --from es --to en fr de
transl-ai story.txt --from es --to en
```

- `--from` is the language to translate from, `--to` one or more languages to translate into.
- A `.csv` is updated in place; use `-o other.csv` to write somewhere else.
- Any other file is treated as text and gets a copy per language next to it: `story.en.txt`. A copy that already exists is not overwritten.

[examples/translations.csv](examples/translations.csv) is a sample CSV in Spanish with every kind of row.

### Other providers

```
transl-ai translations.csv --from es --to en --provider anthropic
transl-ai translations.csv --from es --to en --provider anthropic --model claude-haiku-5-5
transl-ai translations.csv --from es --to en --provider openai --model MODEL
```

Put the key in a `.env` file in the folder you run the command from, or in the environment:

```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

- Anthropic uses `claude-opus-5-5` unless you pass `--model`. It is their expensive tier; `claude-haiku-5-5` costs far less.
- OpenAI has no default model: `--model` is required.
- `--api-base URL` points the `openai` provider at any other API that speaks the same chat completions format.

## What happens to your CSV

- Each new language becomes a column after the last language column. Comment columns (headers starting with `_`) stay where they are.
- Plural blocks get one row per plural form of the target language, so a language with three forms adds a row to the block. The order of the rows is the one Godot's own rule for that language uses. In Bengali, Persian, Gujarati, Hindi, Kannada, Zulu, Icelandic and Filipino that puts the singular second.
- If the file has a `?pluralrule` row, the rule of each new language is written into it.
- Norwegian is asked for as `no` and written as the `nb` column, the name Godot gives it.
- The file is saved after each language. If a run stops halfway through a language, that language is lost and the finished ones are kept.

## Languages

Plain language codes only, no regional variants (`pt`, not `pt_BR`):

`ar bg bn ca cs da de el en es et fa fi fil fr ga gu he hi hr hu id is it ja kn ko lt lv ml mr mt nl no pa pl pt ro ru sk sl sr sv sw ta te th tr uk ur vi zh zu`

They are the languages TranslateGemma was evaluated on, plus the official EU languages.

## What has been tested

All of it from Spanish, on macOS, with Godot 4.7.2.

| What | How far |
|---|---|
| Spanish to English, French, German, Russian | The whole 23-message sample, with Ollama |
| Spanish to 39 other languages | A three-message file: it runs and Godot imports the result |
| Gujarati, Kannada, Malayalam, Marathi, Punjabi, Tamil, Telugu, Urdu, Zulu | Never run through a model |
| Plural rows in Godot, all 52 target languages | With made-up texts, Godot picks the expected row for every number from 0 to 200 |
| Anthropic | A five-message file, on `claude-opus-5-5` and `claude-haiku-5-5` |
| OpenAI | No real translation. Only the request format, against Ollama's compatible API |
| Any source language other than Spanish | Not tested. The examples inside the prompt are written for Spanish |
| Windows and Linux | Not tested |

## Known problems

- **Lost placeholders are not detected.** A translation can drop a `%d` or a tag and the tool will not tell you. Seen in Arabic, where "one coin" came back without the number. Check placeholders yourself.
- **The key can leak into the text.** The model is told each row's key and context. With TranslateGemma, `JOB_COOK_F` once produced "Cook (female)" and `TAVERN_STAFF` produced "tavern staff member".
- **Gender given as context can land on the wrong person.** With a `female` context, Russian and Thai made the speaker female instead of the player.
- **Formal and informal address get mixed** between rows, mostly in French and Russian.
- **Some plural forms are wrong** in Slovenian and Latvian. Irish and Maltese looked poor in the little that was tried.
- **No shared vocabulary.** Every text is translated on its own, so the same word can be translated two ways in two rows.
- **Comment columns are not sent to the model.** Notes for translators in `_` columns are ignored.
- **Only comma-separated CSVs**, although Godot also accepts semicolons and tabs.
- **Text files:** line breaks inside a paragraph may be joined, and a very long paragraph may not fit the model.
- **No variants:** `zh` does not choose between Simplified and Traditional, nor `pt` between Brazil and Portugal.
- **It is slow locally:** about 2 seconds per text on the Mac it was built on, so 1,000 texts into 4 languages take over two hours.

Most of these were seen with TranslateGemma, the default model. On the five messages the Anthropic models were tried on, the key did not leak and the gender landed on the right person. That is too small a sample to promise anything.

## Development

```
git clone https://github.com/egobiian/transl-ai
cd transl-ai
uv sync
uv run pytest
uv run mypy
uv run ruff check .
uv run transl-ai --help
```

The tests do not call any model.

## License

MIT. See [LICENSE](LICENSE).
