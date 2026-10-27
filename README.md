# io-agent · IO's agent for chargebacks

**Language:** English · [Español](README.es.md)

An agent that investigates why payment disputes (chargebacks) go up: it proposes explanations, tests them against the data and discards the ones the evidence does not support, recording every test. If it cannot back a conclusion with rows of evidence, it abstains.

Built during the Open Agent Hackathon 2026 (Track 02 · *The Agent That Can Explain Why*), starting 22 Oct 2026. Everything in this repo is new hackathon work, except the previous component declared under "Where the data comes from".

> **Read this first: sample mode is the default.** `SAMPLE_MODE=true` replays **pre-recorded real runs**: the Nemotron responses (via Meterless Nightshift) and the rows io-engine returned, for the three example questions in `ejemplos/`. The agent logic (Investigator, Evaluator, approval queue, memory) runs for real on top of those recordings; the model and the data engine are not called. Any other question has no recording, so the agent abstains. To run new questions, use live mode (section "Live mode: new questions" below). The data is synthetic.
>
> The organizers confirmed that this is acceptable: *"yes a pre-recorded sample mode acceptable, please make sure its highlighted in your submission and README"* (Janson Lim, HackOS #Help desk, 24 Oct 2026).
>
> Note: the agent answers in Spanish (the store owner's language), and its report and trace are in Spanish. Code identifiers, file names and commands are as written below.

## Try it in 2 minutes

No keys, no model and no data engine are needed. By default the agent runs in **sample mode**: it replays **real recorded runs** (what Nemotron answered via Meterless Nightshift and the rows io-engine returned, as they were) and answers in milliseconds. The trace, the evidence, the report and the approval queue are those of that real run.

With Python 3.12 or newer:

```
pip install -r requirements.txt
python run.py ejemplos/caso3_entrada.json
```

Or with Docker (runs case 3):

```
docker compose run --rm agente
```

The readable report is written to `salidas/<run_id>.md`. That is the file to read.

### The questions sample mode answers

| File | Question | What it shows |
| --- | --- | --- |
| `ejemplos/caso1_entrada.json` | Is it worth fighting dispute du_cuKtmopzODI37h? | **Yes**: delivered with a signature, no prior complaint, no fraud signals. It leaves the reply to the bank in the queue. |
| `ejemplos/caso2_entrada.json` | Is it worth fighting dispute du_LRbXAOhoJgujrS? | **No**: although it was delivered with a photo, it has 4 fraud signals. It discards the opposite hypothesis with evidence. |
| `ejemplos/caso3_entrada.json` | Why did disputes go up in the second half of September 2026? | The spike (from 4 to 18) is not fraud: RapidEnvio in the North explains it (14 of 18). It separates which disputes to fight and drafts their replies; the policy rejects one (`du_HlcQ…`, 1 fraud signal) so a person decides. |

(The questions are asked in Spanish, exactly as in the `ejemplos/*_entrada.json` files.)

The outputs of these three runs are already in `ejemplos/*_salida.md`, in case you want to read them without running anything. **In English:** [case 1](ejemplos/caso1_salida.en.md) · [case 2](ejemplos/caso2_salida.en.md) · [case 3](ejemplos/caso3_salida.en.md) (translations of the agent's Spanish output; SQL and data unchanged).

**A different question** (or the same one written differently: upper/lower case and spaces are ignored, other words are not) has no recorded run, and the agent **abstains** instead of making something up: "No hay una corrida grabada (o se terminó) para esta pregunta en modo de muestra. Para preguntas nuevas usa el modo real / For new questions use live mode: SAMPLE_MODE=false (README.md, «Live mode: new questions»; README.es.md, «Modo real: preguntas nuevas»)." For new questions, use live mode (below).

### The comparisons, also instant

```
python scripts/comparar_capa.py        # the same question with and without IO's layer
python scripts/comparar_memoria.py     # with and without Meterless (H-MEM and World Model)
```

- `comparar_capa.py` writes the side-by-side to [`ejemplos/comparacion_capa.md`](ejemplos/comparacion_capa.md). Without the layer, case 1 says "don't fight" on a dispute that could be won, because it cannot match the order across systems.
- The measurement over the 42 disputes of the test set is already in [`evaluacion/medicion.md`](evaluacion/medicion.md): **42 of 42 with the layer, 8 of 42 without it**. Running it again needs live mode, because these are new questions. How to read it: the 42 of 42 measures that the agent reproduces the definition of the set (`vale_pelear`, from the canonical schema), not an external truth; and the 20 defenses lost without the layer are a single repeated error (it does not match `ORD-1574` with `1574`), not 20 different errors.

### As a service

```
python run.py --servir
```

And a `POST http://localhost:8080/run` with, for example, `{"pregunta": "¿Vale la pena pelear la disputa du_cuKtmopzODI37h?"}`.

### What each run leaves behind

- `logs/<run_id>.jsonl`: the trace, one event per line (who did what, with which evidence, how long it took);
- `logs/<run_id>.evidencia.jsonl`: each query with its rows and the hypothesis it was testing;
- `logs/cola_aprobacion.jsonl`: the queue, with what the policy decided for each entry and why;
- `salidas/<run_id>.json` and `.md`: the answer and the report.

### Live mode: new questions

To ask anything, the agent needs its two dependencies up:

1. **io-engine**, the data engine (previous component, another repo): `docker compose up` in that repo.
2. **Meterless Nightshift** with an NVIDIA Nemotron lane and its Runtime token.

Copy `.env.example` as `.env.local`, fill in `METERLESS_RUNTIME_TOKEN` and set `SAMPLE_MODE=false`. Then save the question in a file (for example `mi_pregunta.json` with `{"pregunta": "..."}`) and run `python run.py mi_pregunta.json`. On macOS or Linux `python run.py '{"pregunta": "..."}'` also works.

**A question in live mode takes 1 to 8 minutes.** Nemotron reasons before each answer, an investigation is 2 to 6 rounds with the model, and Nightshift cuts each call at 45 seconds (the agent retries it, and if it keeps failing it moves to a fallback Nemotron). That is why the demo is shown in sample mode.

## How it investigates

The **Investigator** talks to the model (Nemotron, via Meterless Nightshift). In each round the model answers with one action in JSON, and our code executes and records it:

1. **Proposes hypotheses** (H1, H2…), including the most obvious explanation even if it is false (for example, "it is fraud").
2. **Tests them** with `consultar(sql)` against io-engine. Each result is kept as evidence E1, E2…
3. **Gives a verdict** (upheld or discarded) citing the evidence. The **Evaluator** reviews it and sends it back if the evidence does not exist, failed or has no rows.
4. **Concludes** only if the Evaluator accepts: every hypothesis has a verdict and at least one is upheld. If the data is not enough, it **abstains**.

Everything in the report (statements, reasons, conclusion and recommendation) is read by the store owner, so the Evaluator also sends back anything that contains technical terms (`product_not_received`, `zona_con_atrasos=true`). If it sends back the same thing more than `AGENTE_TOPE_DEVOLUCIONES` times, the agent abstains.

The AI thinks; the code acts and records. Limits: `AGENTE_MAX_ITERACIONES` rounds and `AGENTE_TIMEOUT_S` per call.

## With and without IO's layer

IO's differentiator is the semantic layer: the same question is answered badly over the raw sources and well with the layer. A switch shows it:

```
SEMANTIC_LAYER=off
```

With the layer off, the agent queries the raw tables of io-engine (`crudo.pagos_disputes`, `crudo.envios`, `crudo.soporte_tickets`…), as they arrive from each system:

- amounts in cents and dates in different formats;
- orders written as `ORD-1574`, `1574` or `#1574`;
- support linked by email and not by customer.

It is also left **without** the canonical schema, **without** its definitions (what confirmed delivery, prior complaint, delay zone or fraud signal mean) and **without** Meterless (H-MEM and World Model). Everything else is the same: same model, same question, same data and the same Evaluator, except for the rules that use definitions from the layer.

```
python scripts/comparar_capa.py
```

It runs the three examples with and without the layer and writes the side-by-side to [`ejemplos/comparacion_capa.md`](ejemplos/comparacion_capa.md), with the two traces in `logs/`. The runs without the layer are recorded with `SEMANTIC_LAYER=off python scripts/grabar_corridas.py` (on Windows: `set SEMANTIC_LAYER=off` first) and are saved as `samples/corridas/*-sincapa.json`.

### In numbers: the test set

Besides the three demo cases, the agent is measured over all the disputes in the synthetic data, each with its expected answer according to the definition of the canonical schema (worth fighting, not worth fighting, or operational cause):

```
python scripts/armar_set_prueba.py           # evaluacion/set_prueba.csv and .md (with io-engine up)
python scripts/medir_set.py --primeros 5      # short test
python scripts/medir_set.py                   # the full set, with and without the layer (can be stopped and resumed)
```

The table with both results side by side is written to `evaluacion/medicion.md`: hits, defenses that should not have been built, defenses lost and abstentions with their reason. The answers are in `evaluacion/resultados/` and the traces in `evaluacion/logs/`.

## After investigating: the approval queue

The agent does not stop at an explanation: with the conclusion accepted, it separates the disputes worth fighting from those that are not, drafts the reply to the bank for each one worth fighting and leaves everything in an approval queue. **It sends nothing.**

- **Which disputes.** If the question names disputes, those. If it is about an increase, the ones from the carrier and region that the World Model anchored in the conclusion, in the period of the question.
- **With what data.** It fetches them with `consultar(sql)`, as evidence E#: the row of each dispute and the support messages of their orders.
- **How it separates.** With io-engine's decision (`vale_pelear`, `razon_decision`).
- **What it drafts.**
  - One reply to the bank for each dispute worth fighting, with delivery, customer history, support and fraud signals, each fact with its E#.
  - For an increase, one entry with the cause and which disputes of the group are not worth fighting, grouped by reason and with what to do with each group.
- **Who decides.** While the agent runs there is no human: the rule `politica_v1` approves or rejects each entry and leaves the reason in `logs/cola_aprobacion.jsonl`. It only approves on its own what has no doubts (complete evidence, open dispute, no fraud signals, amount up to `AGENTE_POLITICA_MONTO_MAX`); everything else it rejects so a person decides.

The rules and the format are in [`CONTRATO.md`](CONTRATO.md). The report shows the queue under "Qué conviene hacer" (What to do).

## Memory across runs (H-MEM, from Meterless)

The agent does not start from zero in each run. We implemented **H-MEM**, Meterless's memory engine (`agente/memoria.py`, following `engines/hmem` in Meterless's repo):

- **Before the first round, it remembers.** It searches its memory with H-MEM's hybrid ranking and feeds the Investigator two things:
  - the **Evaluator's lessons**: every reason a verdict or a conclusion was sent back before ("test at least 2 hypotheses…", "count the decisions before recommending…");
  - the **findings** of previous runs on that same question, as hints and never as evidence: the Evaluator still requires a query from this run for every statement.
- **When it finishes, it learns.**
  - It stores the new lessons and, if it concluded, the findings.
  - It replaces the old findings of the same question: they are penalized, never deleted.
  - It raises or lowers the confidence of what it used (+0.05 if it helped, −0.03 if not).
  - It promotes to long term what helped 3 times.
- **Everything is audited**:
  - `memoria/memorias.json` stores the records with their source (`corrida:<run_id>`);
  - `memoria/ledger.jsonl` is the append-only trust ledger, with the previous and the new state of each change;
  - the trace gets the events `recordar` (remember) and `aprender` (learn) from the `memoria` agent.
- **Adapter with timeout and fallback.** If H-MEM is off (`AGENTE_HMEM=false`), takes longer than `AGENTE_HMEM_TIMEOUT_S` or fails, the agent continues without memory and the trace says so (`omitido` or `error` with "respaldo").
- **What it shows and what it does not.** `comparar_memoria.py` shows that the agent remembers what the Evaluator corrected before (fewer returns and rounds when the same question is repeated). It does not prove that this memory generalizes to new questions.

## What was seen and where it came from (World Model, from Meterless)

H-MEM remembers; the **World Model** keeps the canonical record of the *things* the agent saw in the data. We implemented it following `engines/world-model` in Meterless's repo (`agente/mundo.py`):

- **Idempotent ingestion.** Every query that returns rows goes into the World Model:
  - disputes, orders, payments, shipments and customers are stored with their io-engine id (`disputa:io:du_…`);
  - carriers and regions, with an id derived from the normalized name (`ent_<sha256>`);
  - their relations (dispute → order, carrier → region…) and their facts (`razon_decision`, `senales_fraude`…) are stored, with the run and the evidence E# they came from;
  - ingesting the same rows again adds nothing.
- **Append-only record.** Everything lives in `mundo/eventos.jsonl` and the state is rebuilt from there. A write without provenance is rejected.
- **Anchoring the conclusion.** Before accepting it, the Evaluator asks the World Model whether each dispute, carrier and region it names came out of a query in this run. If the model names something it only remembers from another run (H-MEM) or made up, it is sent back. The trace gets the `anclar` (anchor) event, with the evidence for each name: `RapidEnvio (E2); Norte (E2)`.
- **Id resolution.** If a query returns no rows because the model misspelled an id (`du_…jgujrs` instead of `du_…jgujrS`), the World Model answers with the canonical id.
- **Same adapter with timeout and fallback** as H-MEM: with `AGENTE_MUNDO=false`, or if it takes too long or fails, the agent continues without anchoring or id resolution, and the trace marks it.

## With and without Meterless

```
python scripts/comparar_memoria.py
```

It runs the three examples with and without Meterless (H-MEM and World Model). For each one it shows rounds, Evaluator returns, queries, memories fed back, entities anchored and the trace in `logs/`. The runs with Meterless are real, recorded with both engines on (`samples/corridas/*-hmem.json`), and start from what was recorded in `samples/memoria/` and `samples/mundo/`.

## Where the data comes from

The agent does not read databases or files directly: it asks the **io-engine** engine with the `consultar(sql)` tool over MCP. The engine is a **previous component** (built before 22 Oct 2026 00:00 UTC, tag `previo-22oct`, declared in the submission form) and is started separately.

- **Sample mode** (`SAMPLE_MODE=true`, default): replays **real recorded runs** in `samples/corridas/`: what Nemotron answered and the rows io-engine returned, as they were. It needs neither the engine, nor Nightshift, nor keys. A question with no recorded run ends in abstention.
- **Live mode** (`SAMPLE_MODE=false`): start io-engine (`docker compose up --build` in that repo), open Nightshift with a Nemotron lane, copy `.env.example` as `.env.local` and fill in the engine URL and the Nightshift token.
- **Recording runs**: with everything from live mode up, `python scripts/grabar_corridas.py` runs the three examples, records them in `samples/corridas/` (with memory, as `*-hmem.json`) and regenerates `ejemplos/`.
- **Queue queries**: the ones the agent builds on its own (the group's disputes, the support messages) are recorded with `python scripts/completar_muestras.py`, with io-engine up and without calling the model.
- **Memory and World Model**: in live mode they live in `memoria/` and `mundo/` (not uploaded). `python scripts/sembrar_memoria.py` seeds the memory with what the already recorded runs teach, and `python scripts/congelar_memoria.py` copies both to `samples/`, which is what sample mode uses.

## Contract

The answer (with its evidence rows and the Markdown report), the approval queue and the JSONL trace have a fixed format: see [`CONTRATO.md`](CONTRATO.md) and `contrato/*.schema.json`.

## Examples

`ejemplos/` has three questions (the three planted cases) with their outputs, generated by real runs with `python scripts/generar_ejemplos.py`, never written by hand. The `*_salida.en.md` files are translations of those outputs, made afterwards for readers who do not read Spanish; the script does not generate them.

## Tests

```
python -m pytest
```

They run without network or keys. Most use a scripted model and a fake engine (`tests/falsos.py`) to test each piece: the Investigator loop, the Evaluator, H-MEM, the World Model, the queue and its policy, the layer switch and the measurement. `tests/test_investigador_rojo.py` replays the recorded runs of the three cases and checks their conclusions.

## Limits

| Variable | Default | What it limits |
| --- | --- | --- |
| `AGENTE_TIMEOUT_S` | `60` | each external call (engine and model), with one retry if exceeded |
| `AGENTE_MAX_ITERACIONES` | `16` | rounds with the model per run |
| `AGENTE_PRESUPUESTO_USD` | `1.0` | spend at the model provider: if exceeded, an alert is left in the trace |
| `SEMANTIC_LAYER` | `on` | `off` turns off IO's layer: raw tables, no definitions and no Meterless (for comparison) |
| `AGENTE_POLITICA_MONTO_MAX` | `500` | amount (USD) up to which the policy approves a reply to the bank on its own |
| `AGENTE_TOPE_DEVOLUCIONES` | `2` | times the Evaluator can send back the same statement; after that, the agent abstains |
| `AGENTE_HMEM` | `true` | H-MEM on; `false` runs without memory |
| `AGENTE_HMEM_TIMEOUT_S` | `2` | each memory operation; if exceeded, it continues without memory |
| `AGENTE_HMEM_UMBRAL` | `0.30` | minimum score for a finding to be fed back (lessons use 0.20) |
| `AGENTE_MUNDO` | `true` | World Model on; `false` runs without anchoring or id resolution |
| `AGENTE_MUNDO_TIMEOUT_S` | `2` | each World Model operation; if exceeded, it continues without it |

## Sponsors

- **Meterless:**
  - **Nightshift** is the agent's main AI provider (OpenAI-compatible API, with the Runtime contract from the guide), behind an adapter with timeout, retries and a fallback Nemotron model. Each round records in the trace which model answered.
  - **H-MEM** is the agent's memory across runs, and the **World Model** is the record of what it saw and where it came from (see above).
  - **What breaks if Meterless is removed:**
    - without Nightshift, the agent has no model and abstains;
    - without H-MEM, every run starts from zero: the Investigator repeats mistakes the Evaluator had already corrected (more returns and rounds);
    - without the World Model, the Evaluator can no longer check that what the conclusion names came out of a query in that run, so a remembered or invented dispute, carrier or region can reach the answer;
    - `python scripts/comparar_memoria.py` shows the difference in `logs/`.
- **NVIDIA:** the model is Nemotron, served through Nightshift: `nvidia/nemotron-3.5-super-vl-120b-a12b` as primary and `nvidia/nemotron-3.5-lightning-30b-a3b` as fallback. The recorded runs in `samples/corridas/` include answers from both; the trace records which model answered each round.
- **Zetaris:** answers `consultar(sql)` in io-engine by joining the three sources without copying them, with DuckDB as a fallback; each answer records which engine responded. The sample-mode recordings used the DuckDB fallback; the live runs in `samples/corridas/jptrs112/` (case 3) were answered by Zetaris (`motor=zetaris`), with each Nightshift call's signed receipt verified (`tests/test_recibo.py` checks a real Nightshift receipt).
- **Development tool:** see `metadata.json`.

## License

PolyForm Noncommercial 1.0.0 · see `LICENSE`.
