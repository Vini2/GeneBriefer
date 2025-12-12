#!/usr/bin/env python3
import json
import re
import requests
import click
import os
from jinja2 import Environment, FileSystemLoader, Template

# --------------------------------------------
# Jinja2 environment for default templates
# --------------------------------------------

# Assume templates are in ./templates relative to this file
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


# --------------------------------------------
# Core logic
# --------------------------------------------

def fetch_uniprot_entry(accession: str) -> dict:
    click.echo(f"[{accession}] [1/5] Fetching UniProt entry...")
    url = f"https://rest.uniprot.org/uniprotkb/{accession}"
    headers = {"Accept": "application/json"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    click.echo(f"[{accession}] [1/5] Done fetching UniProt entry.")
    return r.json()

def extract_relevant_fields(uniprot_json: dict, accession: str) -> dict:
    click.echo(f"[{accession}] [2/5] Extracting relevant fields...")

    protein_name = uniprot_json["proteinDescription"]["recommendedName"]["fullName"]["value"]
    gene_names = [g["geneName"]["value"] for g in uniprot_json.get("genes", [])]
    organism = uniprot_json["organism"]["scientificName"]

    comments = uniprot_json.get("comments", [])
    function_texts = []
    disease_texts = []

    for c in comments:
        if c.get("commentType") == "FUNCTION":
            for t in c.get("texts", []):
                function_texts.append(t["value"])
        if c.get("commentType") == "DISEASE":
            for t in c.get("texts", []):
                disease_texts.append(t["value"])

    click.echo(f"[{accession}] [2/5] Done extracting fields.")
    return {
        "protein_name": protein_name,
        "gene_names": gene_names,
        "organism": organism,
        "function_text": "\n".join(function_texts),
        "disease_text": "\n".join(disease_texts),
    }

def build_prompt(info: dict, accession: str, prompt_file: str | None = None) -> str:
    """
    Build the LLM prompt using Jinja2.

    - If prompt_file is provided, load that file as a Jinja2 template (from string).
    - Otherwise, use the default templates/summary_prompt.j2 file.
    """
    click.echo(f"[{accession}] [3/5] Building prompt...")

    # Data available to the template
    context = {
        "accession": accession,
        **info,  # protein_name, gene_names, organism, function_text, disease_text
    }

    if prompt_file:
        # Custom template file passed from CLI (absolute or relative path).
        with open(prompt_file, "r", encoding="utf-8") as f:
            content = f.read()
        template = env.from_string(content)  # treat file as a Jinja2 template string
    else:
        # Default template from the templates directory
        template = env.get_template("summary_prompt.j2")

    prompt = template.render(**context)
    click.echo(f"[{accession}] [3/5] Prompt built.")
    return prompt

def _extract_json_from_text(text: str) -> dict:
    text = text.strip()
    if not text:
        raise ValueError("LLM returned empty response; cannot parse JSON.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response:\n{text}")

def call_llm(prompt: str, accession: str, model: str) -> dict:
    """
    Call a local LLM via Ollama (e.g. llama3, llama3:8b, phi3:instruct) and return JSON.
    """
    click.echo(f"[{accession}] [4/5] Sending prompt to LLM via Ollama (model='{model}')...")

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    r = requests.post(url, json=payload)
    r.raise_for_status()

    data = r.json()
    raw_text = data.get("response", "")

    click.echo(f"[{accession}] [4/5] LLM responded. Parsing...")

    parsed = _extract_json_from_text(raw_text)

    click.echo(f"[{accession}] [4/5] JSON extracted.")
    return parsed

def summarize_protein(
    accession: str,
    show_raw: bool = False,
    prompt_file: str | None = None,
    model: str = "llama3",
) -> dict:
    click.echo(f"=== [{accession}] Starting summarization ===")

    uniprot_json = fetch_uniprot_entry(accession)

    if show_raw:
        click.echo(f"\n=== RAW UNIPROT DATA ({accession}) ===")
        click.echo(json.dumps(uniprot_json, indent=2))
        click.echo("=== END RAW DATA ===\n")

    info = extract_relevant_fields(uniprot_json, accession)
    prompt = build_prompt(info, accession, prompt_file=prompt_file)
    summary = call_llm(prompt, accession, model=model)

    click.echo(f"[{accession}] [5/5] Done.\n")
    return summary


# --------------------------------------------
# CLI definition with Click
# --------------------------------------------

@click.command()
@click.argument("accessions", nargs=-1)
@click.option("--raw", is_flag=True, help="Show raw UniProt JSON.")
@click.option("--out", "-o", type=click.Path(), help="Save output to a JSON file.")
@click.option("--compact", is_flag=True, help="Compact JSON without indentation.")
@click.option(
    "--prompt-file",
    type=click.Path(exists=True, dir_okay=False),
    help="Use a custom Jinja2 template file for the LLM prompt.",
)
@click.option(
    "--model",
    "-m",
    default="llama3",
    show_default=True,
    help="Ollama model name to use (e.g. 'llama3', 'llama3:8b', 'phi3:instruct').",
)
def cli(accessions, raw, out, compact, prompt_file, model):
    """
    Summarize UniProt proteins using a local LLM (Ollama).

    Example:
      gene-briefer P04637 Q9T0Q8 --model llama3:8b --prompt-file my_prompt.j2 -o out.json
    """

    # Welcome Message
    click.echo("\n===============================================")
    click.echo(" 🧬  GeneBriefer - Protein Summary Generator   ")
    click.echo("       Using UniProt + Local LLM (Ollama)      ")
    click.echo("===============================================")
    click.echo(f" Using model: {model}\n")

    if not accessions:
        click.echo("Error: You must provide at least one UniProt accession.", err=True)
        raise SystemExit(1)

    results = {}

    for acc in accessions:
        try:
            results[acc] = summarize_protein(
                acc,
                show_raw=raw,
                prompt_file=prompt_file,
                model=model,
            )
        except Exception as e:
            click.echo(f"[{acc}] ERROR: {e}", err=True)

    if out:
        with open(out, "w", encoding="utf-8") as f:
            if compact:
                json.dump(results, f)
            else:
                json.dump(results, f, indent=2)
        click.echo(f"Saved summaries to {out}")
    else:
        if len(results) == 1:
            single = next(iter(results.values()))
            click.echo(json.dumps(single, indent=None if compact else 2))
        else:
            click.echo(json.dumps(results, indent=None if compact else 2))


if __name__ == "__main__":
    cli()
