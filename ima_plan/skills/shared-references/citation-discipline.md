# Citation Discipline for Architecture Papers

> Adapted from ARIS citation-discipline.md. Adjusted for ACM citation style.

---

## Core Principle

**Never generate BibTeX from memory.** LLM-generated citations often contain plausible but incorrect metadata (real authors + fake title, real title + wrong year). Architecture reviewers are domain experts and will catch these errors.

---

## Citation Style (ACM sigconf)

```latex
% Single citation:
\cite{yu2015imp}

% Multiple citations:
\cite{yu2015imp,fu2024dmp,mostofi2023snake}

% DO NOT use natbib commands:
% \citep{} and \citet{} are for ML venues (ICLR, NeurIPS)
% MICRO/ISCA/HPCA use standard \cite{}
```

---

## BibTeX Key Convention

Format: `firstauthor_year_keyword`

```bibtex
@inproceedings{yu2015imp,        % Yu et al., MICRO 2015, IMP
@inproceedings{fu2024dmp,        % Fu et al., HPCA 2024, DMP
@inproceedings{mostofi2023snake, % Mostofi et al., MICRO 2023, Snake
@inproceedings{lakshminarayana2014spare, % HPCA 2014, Spare Register
```

---

## Verification Workflow

### Step 1: Search
Use DBLP as primary source for architecture papers:
- DBLP: `https://dblp.org/search?q=<title keywords>`
- Google Scholar as backup

### Step 2: Verify
Confirm the paper exists with correct:
- Author list (first and last author minimum)
- Exact title
- Venue (conference name)
- Year

### Step 3: Retrieve BibTeX
Prefer DBLP BibTeX (most reliable for CS conferences):
```
https://dblp.org/rec/<key>.bib
```

### Step 4: Validate Claims
Before writing "X shows that Y \cite{paper}", verify that the cited paper actually supports claim Y. Do not assume based on title alone.

### Step 5: Add to references.bib
Only add entries that are actually cited. No bibliography padding.

---

## Placeholder Policy

If a citation cannot be verified during writing:

```bibtex
% [VERIFY] Title and year unconfirmed
@misc{unknown2024placeholder,
  title={Approximate Title},
  author={Unknown},
  year={2024},
  note={[VERIFY] needs DBLP confirmation}
}
```

In the LaTeX source:
```latex
% TODO: verify this citation before submission
prior work~\cite{unknown2024placeholder} shows...
```

**Before submission**: All `[VERIFY]` markers must be resolved or the entry removed.

---

## Our Paper's Citation Inventory

### §1 Introduction (~15 citations)
- IMA problem definition: IMP, DMP, Tyche, Prodigy
- GPU frameworks: Gunrock, cuGraph, Gardenia
- CPU→GPU migration: Lee et al. [MICRO'10]
- GPU prefetching: Many-Thread, CAPS, Snake
- GPU IMA: Spare Register

### §2 Background (~5 citations)
- GPU architecture references
- Little's Law / warp scheduling references

### §3 Design (~3 citations)
- Minimal — design section cites prior work only for comparison

### §5 Evaluation (~5 citations)
- Baseline descriptions: Snake, CAPS, Spare Register, stride-INTRA
- Accel-Sim / GPGPU-Sim

### §6 Related Work (~20 citations)
- CPU IMA: IMP, ATP, Gretch, DMP, Tyche + SW: Prodigy, Magellan, DX100, ASaP
- GPU PF: Many-Thread, Orchestrated, APOGEE, WASP, CAPS, APRES, Snake, COMPASS, Treelet
- GPU IMA: Spare Register, DSAP, Deng et al.

### Total: ~45-50 unique citations

Reference: `introduction.md` §1.7 has the full citation inventory.
