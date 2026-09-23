# results/

Output delle run LIMES, una directory per `wave/model/config/`:

    results/wave-0/<model>/<config>/
      wave.json                          # i cinque SHA + tag + commit del freeze
      <item_id>/
        attempt-N.json                   # transcript completo dell'attempt (tool results inclusi)
        outcome.json                     # outcome del runner (attempts, exclusion, durata)
        verdict.json                     # esiti meccanici (Q, S, gemelle, P)
      scorecard.json                     # vettore C P H A U M R della cella
      discrimination.json                # esito delle coppie gemelle (§4.2)

Tutto ciò che è qui è rigenerabile dai record: l'identità di un run vive
nei cinque SHA (`bank_sha`, `protocol_sha`, `model_sha`, `config_sha`,
`judge_sha`), non nel filesystem (DESIGN §2). Nessun numero senza il suo
record di provenienza.

Le run escluse (`excluded: true` in `outcome.json`) restano qui e entrano
nelle metriche di affidabilità **R**: l'error rate è metrica pubblicata,
non rumore da cancellare (DESIGN §6).
