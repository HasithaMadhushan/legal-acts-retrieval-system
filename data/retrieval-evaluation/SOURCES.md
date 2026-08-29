# Retrieval corpus provenance

The candidate judgments were checked against locally held Gazette PDFs using rendered/native text, not against retrieval output. SHA-256 pins the exact source bytes. PDFs remain outside this dataset directory; they are corpus inputs rather than generated benchmark artifacts.

| Document identifier | SHA-256 | Sections used in candidate judgments |
|---|---|---|
| `01_anti-corruption-act-9-of-2023.pdf` | `e6d40c137d383e88fee98fdf57b80c79b18e9563f9c0eeaff91a98bba8035530` | 1, 3, 18 |
| `02_anti-corruption-amendment-act-28-of-2023.pdf` | `47b5d55b761c920a79d2df71385d2c0dbdbeee118f787cfd4118dad3b67c47c8` | 1, 2 |
| `03_personal-data-protection-act-9-of-2022.pdf` | `6fcdf94fe219d9f7cd18c4790a2c6332568c65eb72846790480e65834012ef46` | 1, 13, 23, 24 |
| `04_personal-data-protection-amendment-act-22-of-2025.pdf` | `6186f402309b19987e2a0ff759e9085b369357b0230f5034b0a6523d72b9760e` | 1, 2, 7 |
| `05_value-added-tax-amendment-act-32-of-2023.pdf` | `05f7755578f0135eedd93b27c613d387b696bde6781373c0d27ca94f699c65bc` | 1, 2, 3 |
| `06_inland-revenue-amendment-act-14-of-2023.pdf` | `2a086eb2ab9b222f2f707486ef32436fe5a500ccd4e84530e38cb7aacdd476e2` | 1, 2 |
| `07_elections-special-provisions-act-21-of-2023.pdf` | `f0754d8b8209ac581485804f43388d0f856ffd6f3d1ff1d2f1f94bdd29bc88b0` | 1, 2, 3, 5, 7, 9 |
| `08_civil-procedure-code-amendment-act-29-of-2023.pdf` | `5a6dc6e11f6024db3268ab6b19bba61778a6098da4ecc90f1a5b6be3ab70fee1` | 1, 5, 6 |
| `09_code-of-criminal-procedure-amendment-act-2-of-2022.pdf` | `47799206cee2fb988266e32a660fbf3f4a375f1ec42412d05d62ed8ab5c26b39` | 1, 3 |
| `10_right-to-information-act-12-of-2016.pdf` | `8420eed89d5c789ab05ae2015f16fc872c1b1713a5c3377118dc6c5186d945cc` | 1, 24, 32, 35 |
| `11_banking-special-provisions-act-17-of-2023.pdf` | `b60dd60a7455979a8aa18064216de10af88ea54c89b20b2b6b5fe1576ebb1c1a` | 1, 9, 11 |
| `12_proceeds-of-crime-act-5-of-2025.pdf` | `81120b9f762a3c9aa94832cebcb9dca154afa7e35c450c2750d4702a490bb705` | 1, 6, 12 |

The two negative queries were checked for absence at the corpus level. A document identifier is retained on those rows only as a deterministic corpus anchor; it does not imply that document is relevant.
