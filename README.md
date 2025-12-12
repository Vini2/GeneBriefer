# GeneBriefer

GeneBriefer is a command-line tool that transforms UniProt protein entries into clear, structured summaries using a local LLM running through Ollama. It automatically retrieves protein metadata, extracts key biological details, and generates student-friendly and researcher-level explanations in JSON format.

**Note:** This is just a hobby project I built for fun and learning. Expect rough edges!

## Getting started

### Step 1 - Setting up Ollama locally

You can download Ollama from the [Download Ollama](https://ollama.com/download) page. 

Then double click on the Ollama executable and make sure it is running. You can test if Ollama is running using the following command (generally Ollama runs at `http://localhost:11434`).

```shell
curl http://localhost:11434/api/tags
```

If Ollama is running you will see a similar message as follows.

```shell
{"models":[{"name":"llama3:latest","model":"llama3:latest","modified_at":"2025-12-12T14:17:50.316533+10:30","size":4661224676,"digest":"365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1","details":{"parent_model":"","format":"gguf","family":"llama","families":["llama"],"parameter_size":"8.0B","quantization_level":"Q4_0"}}]}%  
```

Now Ollama is running locally on your machine. You can download the available models (check the [Ollama library](https://ollama.com/library) for available models). For example, let's download the `llama3` model using the following command.

```shell
ollama pull llama3
```

### Step 2 - Setting up GeneBriefer

Clone the GeneBriefer repository to your machine and move into the `GeneBriefer` folder using the following commands.

```shell
git clone https://github.com/Vini2/GeneBriefer.git
cd GeneBriefer
```

Then run the following command to install GeneBriefer.

```shell
pip install -e .
```

You can print the help message to test whether the installation.

```shell
gene-briefer --help
```

## Running GeneBriefer

You can run `gene-briefer --help` to list the available parameters.

```shell
Usage: gene-briefer [OPTIONS] [ACCESSIONS]...

  Summarise UniProt proteins using a local LLM (Ollama).

  Example:   gene-briefer Q9T0Q8

Options:
  --raw               Show raw UniProt JSON.
  -o, --out PATH      Save output to a JSON file.
  --compact           Compact JSON without indentation.
  --prompt-file FILE  Use a custom Jinja2 template file for the LLM prompt.
  -m, --model TEXT    Ollama model name to use (e.g. 'llama3', 'llama3.2',
                      'gpt-oss').  [default: llama3]
  --help              Show this message and exit.
```

### Example commands

Summarise a single protein

```shell
gene-briefer P04637
```

Summarise multiple proteins at once

```shell
gene-briefer P04637 Q9T0Q8 P03698
```

Use a different LLM model (via Ollama) like `llama3.2`. Make sure to have it downloaded using the command `ollama pull llama3.2`.

```shell
gene-briefer Q9T0Q8 --model llama3.2
```

Show the raw UniProt JSON response

```shell
gene-briefer P04637 --raw
```

Save output to a file

```shell
gene-briefer P04637 -o tp53_summary.json
```

Compact (single-line) JSON output

```shell
gene-briefer P04637 --compact
```

Provide a custom prompt template

```shell
gene-briefer Q9T0Q8 --prompt-file templates/custom_prompt.j2
```

Combine features: custom model + template + output file

```shell
gene-briefer Q9T0Q8 --model llama3:8b-instruct --prompt-file templates/research_summary.j2 --out summary.json
```

## Acknowledgements

This project was developed through vibe coding sessions with ChatGPT. This project prompted me to learn a lot about LLMs and prompt engineering.
