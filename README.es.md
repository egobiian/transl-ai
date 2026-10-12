# transl-ai

Traduce un archivo CSV de localización de Godot, o un archivo de texto, a otros idiomas con un modelo de IA: uno que corre en tu equipo con Ollama, o uno de OpenAI o Anthropic.

[Read it in English](README.md)

**Estado: 0.1.0, inicial.** Es traducción automática. Lee el resultado antes de publicarlo, y lee antes [Problemas conocidos](#problemas-conocidos).

## Qué hace

- Añade al CSV de traducciones de Godot una columna por idioma destino y la rellena.
- Entiende las columnas `?context` y `?plural`: cada idioma recibe el número de formas de plural que Godot espera para él.
- Conserva los `\n` tal como están y quita el punto final que el original no tenía. Los marcadores (`%s`, `%d`, `{name}`) y las etiquetas BBCode se dejan en manos del modelo.
- Nunca cambia lo que ya hay en el archivo: un mensaje que ya tiene traducción se salta.
- Traduce archivos de texto párrafo a párrafo.

## Requisitos

- Python 3.12 o posterior y [uv](https://docs.astral.sh/uv/).
- Un proveedor de modelos:
  - **Ollama** (por defecto): gratis y en local. El modelo es una descarga de 8 GB.
  - **OpenAI** o **Anthropic**: una clave de API. Se paga por uso y tus textos se les envían.
- Godot 4.6 o posterior, solo si tu CSV usa `?context` o `?plural`.

## Instalación

No está en PyPI. Se instala desde este repositorio:

```
uv tool install git+https://github.com/egobiian/transl-ai
```

Para el proveedor por defecto, instala [Ollama](https://ollama.com/download) y descarga el modelo:

```
ollama pull translategemma:12b
```

## Uso

```
transl-ai translations.csv --from es --to en fr de
transl-ai story.txt --from es --to en
```

- `--from` es el idioma de origen y `--to` uno o varios idiomas destino.
- Un `.csv` se actualiza en el propio archivo; con `-o otro.csv` se escribe en otro sitio.
- Cualquier otro archivo se trata como texto y recibe una copia por idioma junto a él: `story.en.txt`. Una copia que ya existe no se sobrescribe.

[examples/translations.csv](examples/translations.csv) es un CSV de ejemplo en español con todos los tipos de fila.

### Otros proveedores

```
transl-ai translations.csv --from es --to en --provider anthropic
transl-ai translations.csv --from es --to en --provider anthropic --model claude-haiku-5-5
transl-ai translations.csv --from es --to en --provider openai --model MODELO
```

La clave va en un archivo `.env` en la carpeta desde la que ejecutas el comando, o en el entorno:

```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

- Anthropic usa `claude-opus-5-5` si no pasas `--model`. Es su gama cara; `claude-haiku-5-5` cuesta mucho menos.
- OpenAI no tiene modelo por defecto: `--model` es obligatorio.
- `--api-base URL` dirige el proveedor `openai` a cualquier otra API que use el mismo formato de chat completions.

## Qué le pasa a tu CSV

- Cada idioma nuevo es una columna después de la última columna de idioma. Las columnas de comentarios (cabeceras que empiezan por `_`) se quedan donde están.
- Los bloques de plural reciben una fila por cada forma de plural del idioma destino, así que un idioma con tres formas añade una fila al bloque. El orden de las filas es el de la regla que Godot aplica a ese idioma. En bengalí, persa, guyaratí, hindi, canarés, zulú, islandés y filipino eso pone el singular en segundo lugar.
- Si el archivo tiene una fila `?pluralrule`, se escribe en ella la regla de cada idioma nuevo.
- El noruego se pide como `no` y se escribe en la columna `nb`, el nombre que le da Godot.
- El archivo se guarda después de cada idioma. Si la ejecución se corta a mitad de un idioma, ese idioma se pierde y los terminados se conservan.

## Idiomas

Solo códigos de idioma, sin variantes regionales (`pt`, no `pt_BR`):

`ar bg bn ca cs da de el en es et fa fi fil fr ga gu he hi hr hu id is it ja kn ko lt lv ml mr mt nl no pa pl pt ro ru sk sl sr sv sw ta te th tr uk ur vi zh zu`

Son los idiomas con los que se evaluó TranslateGemma, más los oficiales de la UE.

## Qué se ha probado

Todo desde español, en macOS y con Godot 4.7.2.

| Qué | Hasta dónde |
|---|---|
| Español a inglés, francés, alemán y ruso | El ejemplo completo de 23 mensajes, con Ollama |
| Español a otros 39 idiomas | Un archivo de tres mensajes: se ejecuta y Godot importa el resultado |
| Guyaratí, canarés, malayalam, maratí, panyabí, tamil, telugu, urdu y zulú | Nunca han pasado por un modelo |
| Filas de plural en Godot, los 52 idiomas destino | Con textos inventados, Godot elige la fila esperada para cada número del 0 al 200 |
| Anthropic | Un archivo de cinco mensajes, con `claude-opus-5-5` y `claude-haiku-5-5` |
| OpenAI | Ninguna traducción real. Solo el formato de la petición, contra la API compatible de Ollama |
| Cualquier idioma de origen que no sea el español | Sin probar. Los ejemplos que lleva el prompt están escritos para el español |
| Windows y Linux | Sin probar |

## Problemas conocidos

- **No se detectan los marcadores perdidos.** Una traducción puede perder un `%d` o una etiqueta y la herramienta no avisa. Pasó en árabe, donde "una moneda" volvió sin el número. Revisa los marcadores tú.
- **La clave se puede colar en el texto.** Al modelo se le dice la clave y el contexto de cada fila. Con TranslateGemma, `JOB_COOK_F` produjo una vez "Cook (female)" y `TAVERN_STAFF` produjo "tavern staff member".
- **El género dado como contexto puede acabar en la persona equivocada.** Con el contexto `female`, el ruso y el tailandés pusieron en femenino a quien habla en vez de a la jugadora.
- **Se mezclan el trato formal y el informal** entre filas, sobre todo en francés y ruso.
- **Algunas formas de plural salen mal** en esloveno y letón. El irlandés y el maltés tenían mala pinta en lo poco que se probó.
- **No hay vocabulario común.** Cada texto se traduce por separado, así que la misma palabra puede salir traducida de dos maneras en dos filas.
- **Las columnas de comentarios no se envían al modelo.** Las notas para traductores de las columnas `_` se ignoran.
- **Solo CSV separados por comas**, aunque Godot también acepta punto y coma y tabuladores.
- **Archivos de texto:** los saltos de línea dentro de un párrafo se pueden unir, y un párrafo muy largo puede no caberle al modelo.
- **Sin variantes:** `zh` no elige entre simplificado y tradicional, ni `pt` entre Brasil y Portugal.
- **En local es lento:** unos 2 segundos por texto en el Mac donde se desarrolló, así que 1.000 textos a 4 idiomas son más de dos horas.

La mayoría se vieron con TranslateGemma, el modelo por defecto. En los cinco mensajes con que se probaron los modelos de Anthropic, la clave no se coló y el género acabó en la persona correcta. Es una muestra demasiado pequeña para prometer nada.

## Desarrollo

```
git clone https://github.com/egobiian/transl-ai
cd transl-ai
uv sync
uv run pytest
uv run mypy
uv run ruff check .
uv run transl-ai --help
```

Los tests no llaman a ningún modelo.

## Licencia

MIT. Consulta [LICENSE](LICENSE).
