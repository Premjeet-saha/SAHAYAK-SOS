# 📊 SAHAYAK SOS Emergency Distress Benchmark Dataset (v1.1 - Group-Aware)

## 1. Overview & Provenance
The **SAHAYAK SOS Emergency Distress Benchmark** (`data/emergency_distress_benchmark.jsonl`) is a standardized, multilingual emergency distress dataset constructed to evaluate and train machine learning triage classifiers for disaster and emergency response in India.

### Data Sources & Provenance:
- **Public-Derived Patterns (`public_derived`)**: Newly authored high-fidelity emergency distress phrases structured and styled after public crisis response taxonomies (CrisisLexT26 and TREC-IS disaster stream categories).
  > **Explicit Clarification**: `public_derived` refers to newly authored benchmark examples inspired by public crisis taxonomy categories and patterns; **it does NOT contain raw third-party records copied from CrisisLexT26 or TREC-IS datasets**.
- **Curated Field Scenarios (`curated`)**: Expert-curated high-fidelity distress formulations modeling Indian emergency response dispatches (fire outbreaks, cylinder blasts, cyclone/flood waterlogging, venomous snakebites, and highway collisions).
- **Contextual Expansions (`synthetic`)**: Controlled geographic and phonetic permutations reflecting localized distress phrasing across Odisha and Pan-India regional contexts.

---

## 2. Grouping & Leakage Prevention (`template_id`)
To prevent **train/test template leakage** and ensure that reported metrics reflect genuine linguistic generalization rather than template memorization, every record is assigned a unique `template_id`:

- **Synthetic Grouping (`TPL-SYN-xxx`)**: All slot-expanded synthetic samples derived from the same base template share the exact same `template_id`. When performing train/test splits, a **Group-Stratified Split** (`StratifiedGroupKFold`) ensures that all variations of a base template reside exclusively in the training split or exclusively in the test split (**0 cross-split template overlap**).
- **Curated Samples (`TPL-CUR-xxx`)**: Unique individual curated distress samples receive distinct template IDs.
- **Public-Derived Samples (`TPL-PUB-xxx`)**: Unique individual public-taxonomy-inspired samples receive distinct template IDs.

---

## 3. Dataset Schema
Each sample is stored as a JSON object per line in `.jsonl` format:

```json
{
  "id": "EMG-0001",
  "template_id": "TPL-PUB-001",
  "text": "Huge fire broke out in the commercial complex near station, thick black smoke trapping workers on 3rd floor!",
  "language": "en",
  "incident_type": "Major Fire Outbreak",
  "severity": "CRITICAL",
  "medical_urgency": "NO",
  "source_type": "public_derived"
}
```

| Field | Type | Allowed Values / Description |
| :--- | :--- | :--- |
| `id` | String | Unique sample identifier (`EMG-0001` to `EMG-0399`). |
| `template_id` | String | Unique template group identifier (`TPL-SYN-xxx`, `TPL-CUR-xxx`, `TPL-PUB-xxx`) used for group-aware splitting. |
| `text` | String | Raw citizen distress call transcript / text in English, Hindi, or Hinglish. |
| `language` | String | `en` (English), `hi` (Hindi in Devanagari script), `hinglish` (Hindi in Latin script). |
| `incident_type` | String | Primary emergency category (6 standard emergency domains). |
| `severity` | String | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`. |
| `medical_urgency` | String | `YES` (paramedic/hospital needed), `NO` (no direct bodily injury/medical trauma). |
| `source_type` | String | `public_derived`, `curated`, `synthetic`. |

---

## 4. Class Definitions & Labels

### Target 1: Incident Type (`incident_type`)
1. **`Major Fire Outbreak`**: Structural fires, commercial building fires, LPG cylinder blasts, chemical/factory smoke hazards.
2. **`Flash Flood / Waterlogging`**: River breaches, urban inundation, submerged homes, drowning risks, cloudbursts.
3. **`Earthquake & Landslide`**: Seismic building collapse, debris entrapment, mountain landslides, ghat road blockages.
4. **`Medical Emergency`**: Cardiac arrests, unconsciousness, severe hemorrhaging/trauma, venomous snakebites, acute labor.
5. **`Road Traffic Collision`**: Highway head-on collisions, bus overturns, vehicle pileups, auto-rickshaw crashes.
6. **`General Emergency Assistance`**: Fallen trees/live wires, power outages in shelters, stranded citizens, relief information.

### Target 2: Hazard Severity (`severity`)
- **`CRITICAL`**: Immediate threat to life/limb, active burning building, drowning/submergence, active cardiac arrest, deep trauma.
- **`HIGH`**: Urgent threat requiring rapid dispatch, structural damage with trapped individuals, snakebite, severe fracture.
- **`MEDIUM`**: Moderate threat with limited immediate bodily harm, localized flooding, road blockages, food/water shortage.
- **`LOW`**: Minor non-urgent events, general inquiries, minor scrapes, safe shelter queries.

### Target 3: Medical Urgency (`medical_urgency`)
- **`YES`**: Casualties, physical injury, cardiac symptoms, unconsciousness, poisoning, burns, pediatric/obstetric emergencies.
- **`NO`**: Property threats, evacuation without injuries, utility disruptions, information requests.

---

## 5. Distribution Statistics (Total Samples: 399, Unique Templates: 214)

### By Language:
- **`en`**: 166 (41.6%)
- **`hi`**: 95 (23.8%)
- **`hinglish`**: 138 (34.6%)

### By Incident Type:
- **`Earthquake & Landslide`**: 53 (13.3%)
- **`Flash Flood / Waterlogging`**: 61 (15.3%)
- **`General Emergency Assistance`**: 61 (15.3%)
- **`Major Fire Outbreak`**: 75 (18.8%)
- **`Medical Emergency`**: 87 (21.8%)
- **`Road Traffic Collision`**: 62 (15.5%)

### By Severity:
- **`CRITICAL`**: 172 (43.1%)
- **`HIGH`**: 125 (31.3%)
- **`LOW`**: 45 (11.3%)
- **`MEDIUM`**: 57 (14.3%)

### By Medical Urgency:
- **`NO`**: 182 (45.6%)
- **`YES`**: 217 (54.4%)

### By Source Type:
- **`curated`**: 101 (25.3%)
- **`public_derived`**: 24 (6.0%)
- **`synthetic`**: 274 (68.7%)
