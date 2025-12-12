#!/usr/bin/env python3

import json
import re
import requests
import click

# --------------------------------------------
# Core logic functions
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

def build_prompt(info: dict, accession: str) -> str:
    click.echo(f"[{accession}] [3/5] Building prompt...")
    gene = info["gene_names"][0] if info["gene_names"] else "N/A"

    template = f"""
You are a bioinformatics assistant.

I will give you information about a protein from UniProt (function, disease relevance, etc.).
Using ONLY that information, produce a concise summary in the following JSON format:

{{
  "gene": "<main gene symbol>",
  "protein_name": "<short descriptive name>",
  "organism": "<species>",
  "summary_student": "<2–3 sentence explanation for a biology student>",
  "summary_researcher": "<2–3 sentence explanation for a researcher>",
  "key_functions": ["...", "..."],
  "pathways_or_processes": ["...", "..."],
  "disease_relevance": ["...", "..."],
  "experimental_notes": ["...", "..."]
}}

If information is not available, use an empty list or null.

Here is the protein metadata:

Gene names: {", ".join(info["gene_names"]) if info["gene_names"] else "N/A"}
Protein name: {info["protein_name"]}
Organism: {info["organism"]}

FUNCTION:
{info["function_text"]}

DISEASE:
{info["disease_text"]}
"""
    click.echo(f"[{accession}] [3/5] Prompt built.")
    return template

def _extract_json_from_text(text: str) -> dict:
    text = text.strip()
    if not text:
        raise ValueError("LLM returned empty response; cannot parse JSON.")

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract { ... } block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response:\n{text}")

def call_llm(prompt: str, accession: str) -> dict:
    click.echo(f"[{accession}] [4/5] Sending prompt to LLM via Ollama...")

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3",
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

def summarize_protein(accession: str, show_raw: bool = False) -> dict:
    click.echo(f"=== [{accession}] Starting summarization ===")
    
    uniprot_json = fetch_uniprot_entry(accession)

    if show_raw:
        click.echo(f"\n=== RAW UNIPROT DATA ({accession}) ===")
        click.echo(json.dumps(uniprot_json, indent=2))
        click.echo("=== END RAW DATA ===\n")

    info = extract_relevant_fields(uniprot_json, accession)
    prompt = build_prompt(info, accession)
    summary = call_llm(prompt, accession)

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
def cli(accessions, raw, out, compact):
    """
    Summarize UniProt proteins using a local LLM (Ollama).
    
    Example:
      gene-brief P04637 Q9T0Q8 --raw -o output.json
    """
    if not accessions:
        click.echo("Error: You must provide at least one UniProt accession.", err=True)
        raise SystemExit(1)

    results = {}

    for acc in accessions:
        try:
            results[acc] = summarize_protein(acc, show_raw=raw)
        except Exception as e:
            click.echo(f"[{acc}] ERROR: {e}", err=True)

    # Output handling
    if out:
        with open(out, "w") as f:
            if compact:
                json.dump(results, f)
            else:
                json.dump(results, f, indent=2)
        click.echo(f"Saved summaries to {out}")
    else:
        # Print to stdout
        if len(results) == 1:
            single = next(iter(results.values()))
            click.echo(json.dumps(single, indent=None if compact else 2))
        else:
            click.echo(json.dumps(results, indent=None if compact else 2))


if __name__ == "__main__":
    cli()
