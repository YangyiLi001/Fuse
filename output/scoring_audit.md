# Scoring & routing audit

Formula: `score = (base + intensity + fit) × recency`; recency = 0.5^(age/half-life), anchor = newest signal (2026-08-16).
Half-lives (days): usage_spike 14, competitor_evaluation 14, intent_topic 21, funding_event 30, job_change 45.
Bands are percentile cuts on each sorted list: P1 = top 20%, P2 = next 30%, cuts extended through ties. severity_hint is unused.

## Per-signal scores (grouped by type, sorted by score)

### usage_spike (base 40)

| signal | account | payload | play | cust | arr_band | age_d | base | inten | fit | ×rec | score | seller |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SIG049 | Urchin Secure (not in CRM) | +315% vs baseline, 15,235 req/7d | — | ? | — | 0.2 | 40 | 28.0 | 0.0 | 0.99 | **67.4** | unmatched |
| SIG021 | Meridian Robotics (not in CRM) | +354% vs baseline, 40,160 req/7d | — | ? | — | 3.2 | 40 | 29.0 | 0.0 | 0.86 | **59.1** | unmatched |
| SIG045 | Yew Cloud (not in CRM) | +254% vs baseline, 25,958 req/7d | — | ? | — | 5.1 | 40 | 25.8 | 0.0 | 0.78 | **51.2** | unmatched |
| SIG018 | Cedar Defense (not in CRM) | +78% vs baseline, 3,551 req/7d | — | ? | — | 5.2 | 40 | 13.2 | 0.0 | 0.77 | **41.2** | unmatched |

### competitor_evaluation (base 35)

| signal | account | payload | play | cust | arr_band | age_d | base | inten | fit | ×rec | score | seller |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SIG043 | Solace Build | Anyscale comparison_search, 19d since last | displacement | prosp | $50M-$250M | 1.1 | 35 | 20.5 | 12 | 0.95 | **64.0** | S08 |
| SIG035 | Iris Secure (not in CRM) | Together AI comparison_search, 4d since last | — | ? | — | 0.9 | 35 | 28.0 | 0.0 | 0.96 | **60.3** | unmatched |
| SIG048 | Osprey Grid | Replicate comparison_search, 23d since last | displacement | prosp | $10M-$50M | 1.9 | 35 | 18.5 | 11 | 0.91 | **58.8** | S10 |
| SIG020 | Hemp Intelligence | Replicate docs_read, 26d since last | displacement | prosp | $250M+ | 0.0 | 35 | 11.9 | 11 | 1.0 | **57.8** | S06 |
| SIG050 | Heron Systems | Anyscale pricing_page_visit, 9d since last | displacement | prosp | $50M-$250M | 1.0 | 35 | 15.3 | 10 | 0.95 | **57.4** | S06 |
| SIG007 | Lupine Scale | Anyscale benchmark_download, 25d since last | displacement | prosp | $50M-$250M | 1.2 | 35 | 15.7 | 10 | 0.94 | **57.3** | S08 |
| SIG025 | Chert Scale | OpenAI pricing_page_visit, 12d since last | displacement | prosp | $10M-$50M | 2.0 | 35 | 14.4 | 11 | 0.91 | **54.8** | S10 |
| SIG005 | Helix Build | Replicate docs_read, 28d since last | displacement | prosp | $50M-$250M | 0.9 | 35 | 11.2 | 10 | 0.96 | **53.8** | S01 |
| SIG034 | Russet Defense (not in CRM) | Together AI pricing_page_visit, 4d since last | — | ? | — | 0.0 | 35 | 16.8 | 0.0 | 1.0 | **51.7** | unmatched |
| SIG032 | Lichen Cloud (not in CRM) | Replicate docs_read, 15d since last | — | ? | — | 2.2 | 35 | 15.7 | 0.0 | 0.9 | **45.5** | unmatched |
| SIG040 | Lark Health (not in CRM) | Replicate docs_read, 26d since last | — | ? | — | 5.1 | 35 | 11.9 | 0.0 | 0.78 | **36.5** | unmatched |

### funding_event (base 30)

| signal | account | payload | play | cust | arr_band | age_d | base | inten | fit | ×rec | score | seller |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SIG037 | Tarragon Scale | Series A $200M (announced 2026-08-10) | new budget | prosp | $250M+ | 6.7 | 30 | 30.0 | 12 | 0.86 | **61.7** | S06 |
| SIG026 | Alabaster Mind | Series A $120M (announced 2026-08-11) | new budget | prosp | $250M+ | 6.1 | 30 | 24.0 | 10 | 0.87 | **55.5** | S08 |
| SIG044 | Quinoa Scale | Seed Extension $85M (announced 2026-08-09) | budget unlocked | cust | $50M-$250M | 7.7 | 30 | 17.0 | 10 | 0.84 | **47.8** | S08 |
| SIG003 | Thorn Data | Series A $60M (announced 2026-08-13) | new budget | prosp | $250M+ | 5.1 | 30 | 12.0 | 10 | 0.89 | **46.2** | S10 |
| SIG038 | Grove Grid | Series C $60M (announced 2026-08-09) | new budget | prosp | $250M+ | 7.7 | 30 | 12.0 | 10 | 0.84 | **43.6** | S12 |
| SIG001 | Pioneer Health | Seed Extension $60M (announced 2026-08-11) | new budget | prosp | <$1M | 5.7 | 30 | 12.0 | 7 | 0.88 | **43.0** | S09 |
| SIG027 | Gossamer Defense | Series C $60M (announced 2026-08-10) | budget unlocked | cust | $1M-$10M | 6.7 | 30 | 12.0 | 8 | 0.86 | **42.9** | S06 |
| SIG009 | Caliber Robotics | Series C $25M (announced 2026-08-13) | budget unlocked | cust | $250M+ | 3.7 | 30 | 5.0 | 11 | 0.92 | **42.3** | S06 |
| SIG046 | Garnet Networks | Seed Extension $25M (announced 2026-08-15) | budget unlocked | cust | $1M-$10M | 3.2 | 30 | 5.0 | 10 | 0.93 | **41.8** | S06 |
| SIG014 | Yarrow Build | Seed Extension $40M (announced 2026-08-08) | new budget | prosp | $250M+ | 8.7 | 30 | 8.0 | 12 | 0.82 | **40.9** | S01 |
| SIG022 | Umber Vision | Series D $25M (announced 2026-08-14) | new budget | prosp | <$1M | 3.2 | 30 | 5.0 | 7 | 0.93 | **39.0** | S06 |
| SIG016 | Hollow Labs | Series B $40M (announced 2026-08-09) | budget unlocked | cust | <$1M | 7.7 | 30 | 8.0 | 8 | 0.84 | **38.5** | S09 |
| SIG024 | Tundra Labs | Series A $25M (announced 2026-08-09) | new budget | prosp | <$1M | 7.7 | 30 | 5.0 | 9 | 0.84 | **36.9** | S06 |
| SIG017 | Bastion Systems (not in CRM) | Series B $15M (announced 2026-08-15) | — | ? | — | 2.0 | 30 | 3.0 | 0.0 | 0.95 | **31.5** | unmatched |

### job_change (base 25)

| signal | account | payload | play | cust | arr_band | age_d | base | inten | fit | ×rec | score | seller |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SIG036 | Fig Grid | Riley Patel: Director of ML Platform, arrived | champion change | cust | $1M-$10M | 2.0 | 25 | 30.0 | 5 | 0.97 | **58.2** | S10 |
| SIG042 | Helix Grid | Avery Nguyen: CTO, departed | champion change | cust | <$1M | 4.3 | 25 | 30.0 | 7 | 0.94 | **58.1** | S06 |
| SIG023 | Nook Flow | Casey Garcia: Chief Architect, departed | champion change | cust | $1M-$10M | 1.3 | 25 | 25.5 | 7 | 0.98 | **56.4** | S02 |
| SIG002 | Pioneer Health | Jordan Kim: Director of ML Platform, arrived | new decision maker | prosp | <$1M | 4.2 | 25 | 30.0 | 3 | 0.94 | **54.4** | S09 |
| SIG041 | Parallax Genomics | Jordan Kim: Head of AI, departed | new decision maker | prosp | $50M-$250M | 0.9 | 25 | 10.8 | 5 | 0.99 | **40.2** | S04 |
| SIG012 | Urchin Networks (not in CRM) | Avery Smith: Staff ML Engineer, arrived | — | ? | — | 5.0 | 25 | 18.0 | 0.0 | 0.93 | **39.8** | unmatched |
| SIG013 | Alabaster Data (not in CRM) | Morgan Smith: Staff ML Engineer, arrived | — | ? | — | 6.2 | 25 | 18.0 | 0.0 | 0.91 | **39.1** | unmatched |
| SIG019 | Onyx Genomics (not in CRM) | Avery Nguyen: VP Infrastructure, departed | — | ? | — | 0.1 | 25 | 10.8 | 0.0 | 1.0 | **35.7** | unmatched |
| SIG015 | Sentinel Mind | Casey Nguyen: Staff ML Engineer, departed | new decision maker | prosp | $50M-$250M | 6.3 | 25 | 7.2 | 5 | 0.91 | **33.8** | S08 |
| SIG029 | Vermilion Flow (not in CRM) | Avery Garcia: VP Infrastructure, departed | — | ? | — | 4.3 | 25 | 10.8 | 0.0 | 0.94 | **33.5** | unmatched |
| SIG011 | Saffron Grid (not in CRM) | Riley Kim: Chief Architect, departed | — | ? | — | 4.2 | 25 | 10.2 | 0.0 | 0.94 | **33.0** | unmatched |

### intent_topic (base 20)

| signal | account | payload | play | cust | arr_band | age_d | base | inten | fit | ×rec | score | seller |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SIG028 | Dolomite Systems | 'GPU alternatives' 0.94 via G2 | early research | prosp | $1M-$10M | 3.1 | 20 | 30.0 | 1 | 0.9 | **46.0** | S09 |
| SIG006 | Helix Build | 'function calling API' 0.92 via web_traffic | early research | prosp | $50M-$250M | 4.3 | 20 | 27.6 | 3 | 0.87 | **43.9** | S01 |
| SIG047 | Quill Flow | 'GPU alternatives' 0.63 via Harmonic | early research | prosp | $1M-$10M | 0.0 | 20 | 20.8 | 3 | 1.0 | **43.8** | S06 |
| SIG004 | Thorn Data | 'function calling API' 0.85 via 6sense | early research | prosp | $250M+ | 6.1 | 20 | 25.5 | 4 | 0.82 | **40.4** | S10 |
| SIG039 | Zinnia Mind | 'LLM inference cost optimization' 0.74 via G2 | early research | prosp | $10M-$50M | 6.2 | 20 | 24.4 | 4 | 0.82 | **39.5** | S02 |
| SIG031 | Lupine Scale | 'GPU alternatives' 0.49 via web_traffic | early research | prosp | $50M-$250M | 0.9 | 20 | 16.2 | 3 | 0.97 | **38.0** | S08 |
| SIG010 | Caliber Robotics | 'fine-tuning platform' 0.48 via Harmonic | expansion research | cust | $250M+ | 3.3 | 20 | 14.4 | 6 | 0.9 | **36.2** | S06 |
| SIG008 | Lupine Scale | 'RAG pipeline infrastructure' 0.54 via G2 | early research | prosp | $50M-$250M | 3.0 | 20 | 16.2 | 3 | 0.91 | **35.5** | S08 |
| SIG030 | Hatchet Health | 'open-source LLM hosting' 0.42 via G2 | expansion research | cust | $1M-$10M | 3.9 | 20 | 13.9 | 3 | 0.88 | **32.4** | S10 |
| SIG033 | Pulse Grid (not in CRM) | 'model serving latency' 0.35 via web_traffic | — | ? | — | 5.1 | 20 | 11.6 | 0.0 | 0.84 | **26.6** | unmatched |

## Bundle → seller (sorted by bundle score)

| account | prio | bundle | calc | region → tier | seller | reason |
|---|---|---|---|---|---|---|
| Lupine Scale (A164) | P1 | **79.0** | 57.3 + 0.3×38.0 + 0.15×35.5 + 5 combo | EMEA → Enterprise | S08 Tom O'Brien | EMEA / Enterprise |
| Helix Build (A269) | P1 | **72.0** | 53.8 + 0.3×43.9 + 5 combo | US-East → Enterprise | S01 Alex Rivera | US-East / Enterprise |
| Pioneer Health (A177) | P1 | **67.3** | 54.4 + 0.3×43.0 | EMEA → Mid-Market | S09 Lena Vogt | EMEA / Mid-Market |
| Solace Build (A251) | P1 | **64.0** | 64.0 | EMEA → Enterprise | S08 Tom O'Brien | EMEA / Enterprise |
| Tarragon Scale (A013) | P1 | **61.7** | 61.7 | US-Central → Strategic | S06 Diego Morales | US-Central / Strategic: no active seller — fell back to Enterprise tier in-territory |
| Osprey Grid (A197) | P1 | **58.8** | 58.8 | APAC → Mid-Market | S10 Hiro Tanaka | APAC / Mid-Market |
| Thorn Data (A196) | P2 | **58.3** | 46.2 + 0.3×40.4 | APAC → Strategic | S10 Hiro Tanaka | APAC / Strategic |
| Fig Grid (A133) | P2 | **58.2** | 58.2 | APAC → Mid-Market | S10 Hiro Tanaka | APAC / Mid-Market |
| Helix Grid (A110) | P2 | **58.1** | 58.1 | US-Central → Mid-Market | S06 Diego Morales | US-Central / Mid-Market |
| Hemp Intelligence (A124) | P2 | **57.8** | 57.8 | US-Central → Strategic | S06 Diego Morales | US-Central / Strategic: no active seller — fell back to Enterprise tier in-territory |
| Heron Systems (A235) | P2 | **57.4** | 57.4 | US-Central → Enterprise | S06 Diego Morales | US-Central / Enterprise |
| Nook Flow (A152) | P2 | **56.4** | 56.4 | US-East → Mid-Market | S02 Priya Shah | US-East / Mid-Market |
| Alabaster Mind (A167) | P2 | **55.5** | 55.5 | EMEA → Strategic | S08 Tom O'Brien | EMEA / Strategic |
| Chert Scale (A230) | P2 | **54.8** | 54.8 | APAC → Mid-Market | S10 Hiro Tanaka | APAC / Mid-Market |
| Caliber Robotics (A214) | P3 | **53.2** | 42.3 + 0.3×36.2 | US-Central → Strategic | S06 Diego Morales | US-Central / Strategic: no active seller — fell back to Enterprise tier in-territory |
| Quinoa Scale (A181) | P3 | **47.8** | 47.8 | EMEA → Enterprise | S08 Tom O'Brien | EMEA / Enterprise |
| Dolomite Systems (A223) | P3 | **46.0** | 46.0 | EMEA → Mid-Market | S09 Lena Vogt | EMEA / Mid-Market |
| Quill Flow (A096) | P3 | **43.8** | 43.8 | US-Central → Mid-Market | S06 Diego Morales | US-Central / Mid-Market |
| Grove Grid (A176) | P3 | **43.6** | 43.6 | US-East → Strategic | S12 Chris Walsh | US-East / Strategic |
| Gossamer Defense (A087) | P3 | **42.9** | 42.9 | US-Central → Mid-Market | S06 Diego Morales | US-Central / Mid-Market |
| Garnet Networks (A295) | P3 | **41.8** | 41.8 | US-Central → Mid-Market | S06 Diego Morales | US-Central / Mid-Market |
| Yarrow Build (A283) | P3 | **40.9** | 40.9 | US-East → Strategic | S01 Alex Rivera | US-East / Strategic |
| Parallax Genomics (A095) | P3 | **40.2** | 40.2 | US-West → Enterprise | S04 Jordan Kim | US-West / Enterprise |
| Zinnia Mind (A232) | P3 | **39.5** | 39.5 | US-East → Mid-Market | S02 Priya Shah | US-East / Mid-Market |
| Umber Vision (A229) | P3 | **39.0** | 39.0 | US-Central → Mid-Market | S06 Diego Morales | US-Central / Mid-Market |
| Hollow Labs (A204) | P3 | **38.5** | 38.5 | EMEA → Mid-Market | S09 Lena Vogt | EMEA / Mid-Market |
| Tundra Labs (A047) | P3 | **36.9** | 36.9 | US-Central → Mid-Market | S06 Diego Morales | US-Central / Mid-Market |
| Sentinel Mind (A221) | P3 | **33.8** | 33.8 | EMEA → Enterprise | S08 Tom O'Brien | EMEA / Enterprise |
| Hatchet Health (A070) | P3 | **32.4** | 32.4 | APAC → Mid-Market | S10 Hiro Tanaka | APAC / Mid-Market |