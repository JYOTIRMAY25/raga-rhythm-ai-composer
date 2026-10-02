# RagaRhythm AI - Full Composition Validation Report

**Generated:** 2026-10-02T06:08:26Z  
**Scope:** 70 Ragas × 9 Talas (630 combinations)  
**Compositions Generated:** 7560 across 4 seeds and 3 durations  
**Pass Rate:** **100.0%** (630/630 PASS)  
**Execution Runtime:** 105.86s (71.41 comp/s)

---

## 1. Executive Metrics

| Metric | Value | Status |
| :--- | :--- | :--- |
| **Total Ragas Evaluated** | 70 | PASS |
| **Total Talas Evaluated** | 9 | PASS |
| **Raga × Tala Combinations** | 630 | PASS |
| **Successful Runs** | 7560 / 7560 | PASS |
| **Invariant Violations** | 0 | ZERO FAILURES |
| **Deterministic Replay (Invariant 17)** | 630/630 (100%) | PASS |
| **Seed Diversity (Invariant 18)** | 630/630 (100%) | PASS |
| **Min / Avg / Max Event Count** | 22 / 90.08 / 169 | PASS |

---

## 2. 18 Composition Invariants Verification Summary

1. **Structural Validity**: All compositions contain valid `cycles` and `events` structure. (`PASS`)
2. **SwaraEvent Integrity**: Every event has valid swara symbol, octave in `[-1, 1]`, duration `> 0`, matra in `[1, matras]`, subdivision in `[0, 3]`. (`PASS`)
3. **Forbidden Swaras (Varjit)**: 0 forbidden swaras generated across all 70 ragas. (`PASS`)
4. **Raga Scale Grammar**: 100% of notes conform to canonical aroha / avaroha allowed swaras. (`PASS`)
5. **Aroha/Avaroha Constraints**: Melodic direction adheres to classical scale rules. (`PASS`)
6. **Vadi/Samvadi Weighting**: Melodic hierarchy assigns prominent durations and Sam landings to Vadi/Samvadi notes. (`PASS`)
7. **Pakad / Catch Phrase Alignment**: Characteristic melodic contours seeded accurately. (`PASS`)
8. **Tala Metric Positioning**: Every event correctly aligns with its Tala vibhag and matra offset. (`PASS`)
9. **Matra Count Parity**: Every cycle sums exactly to the Tala's canonical matra count. (`PASS`)
10. **Sam Representation**: Beat 1 properly identified with `is_sam_landing` flags on cadence. (`PASS`)
11. **Khali / Tali Representation**: Accompanying theka bols and wave/clap markers strictly positioned. (`PASS`)
12. **Cadential Tihai Resolution**: 3-part rhythmic repetition resolves cleanly to Sam on the final cycle. (`PASS`)
13. **Duration Bounds**: Total duration closely matches target duration parameters without drift. (`PASS`)
14. **Tempo BPM Bounds**: Playback tempo exactly reflects specified BPM (`40` to `240`). (`PASS`)
15. **Event Count Safety**: All compositions generate between 10 and 300 discrete events (no runaway loops). (`PASS`)
16. **Serialization Round-Trip**: Pydantic `model_dump()` -> `model_validate()` preserves exact parity. (`PASS`)
17. **Deterministic Repeatability**: Identical inputs and seeds yield bitwise identical scores. (`PASS`)
18. **Seed Variation**: Varied seeds generate rich melodic variations within grammatical bounds. (`PASS`)

---

## 3. Raga × Tala Full Validation Matrix (70 × 9)

| Raga | Teental | Ektaal | Jhaptaal | Rupak | Keherwa | Dadra | Tilwada | Jhoomra | Addha |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Abhogi** (`abhogi`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Ahir Bhairav** (`ahir_bhairav`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Asavari** (`asavari`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bageshri** (`bageshri`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bahar** (`bahar`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bairagi** (`bairagi`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Basanti Kedar** (`basanti_kedar`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bhairav** (`bhairav`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bhairavi** (`bhairavi`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bhatiyar** (`bhatiyar`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bhimpalasi** (`bhimpalasi`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bhoopali** (`bhoopali`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bibhas** (`bibhas`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bihag** (`bihag`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Bilaskhani Todi** (`bilaskhani_todi`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Chandrakauns** (`chandrakauns`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Dagori Deepki** (`dagori_deepki`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Desh** (`desh`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Dhani** (`dhani`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Durga** (`durga`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Gaud Malhar** (`gaud_malhar`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Gauri** (`gauri`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Gawti** (`gawti`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Hameer** (`hameer`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Hindol Pancham** (`hindol_pancham`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Jaijaiwanti** (`jaijaiwanti`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Jait Kalyan** (`jait_kalyan`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Jaunpuri** (`jaunpuri`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Jog** (`jog`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Jogiya** (`jogiya`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Kafi** (`kafi`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Kalavati** (`kalavati`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Kedar** (`kedar`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Khamaj** (`khamaj`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Khat** (`khat`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Khokar** (`khokar`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Kirwani** (`kirwani`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Komal Rishabh Asavari** (`komal_rishabh_asavari`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Lagan Gandhar** (`lagan_gandhar`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Lalit** (`lalit`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Lalit Pancham** (`lalit_pancham`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Madhukauns** (`madhukauns`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Malkauns** (`malkauns`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Maru Bihag** (`maru_bihag`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Marwa** (`marwa`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Megh** (`megh`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Mian Malhar** (`mian_malhar`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Mishra Kalingada** (`mishra_kalingada`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Mishra Piloo** (`mishra_piloo`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Multani** (`multani`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Nat Bhairav** (`nat_bhairav`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Nat Kamod** (`nat_kamod`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Paraj** (`paraj`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Poorva** (`poorva`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Puriya** (`puriya`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Puriya Dhanashree** (`puriya_dhanashree`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Rageshree** (`rageshree`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Ramdasi Malhar** (`ramdasi_malhar`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Saraswati** (`saraswati`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Sawani** (`sawani`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Shankara** (`shankara`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Shree** (`shree`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Shuddh Sarang** (`shuddh_sarang`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Shuddha Kalyan** (`shuddha_kalyan`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Sohani** (`sohani`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Suha** (`suha`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Tilak Kamod** (`tilak_kamod`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Todi** (`todi`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Triveni Gauri** (`triveni_gauri`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| **Yaman** (`yaman`) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
