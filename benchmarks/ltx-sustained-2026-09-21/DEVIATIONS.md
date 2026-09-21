# Execution deviations

## fal status polling correction

The first paid request was accepted before a client observation bug was found: fal returns HTTP 202 with `IN_PROGRESS`, while the initial observer accepted only HTTP 200. The request remained active and was not resubmitted. The observer was corrected to accept 200/202, a regression test was added, and collection resumed using the original request ID. The first pair therefore uses a resumed wall-clock latency with an observation gap; it must be reported separately and excluded from uninterrupted client-latency summaries. Its original video remains the selected quality pair. This is a controller error, not a provider generation failure or a generation retry.

No LTX generation parameters, prompts, seeds, sample selection or budget changed.


## Final telemetry coverage and billing visibility

All 131 LTX request outcomes, original videos and decoding receipts were preserved, and the measured queue completed 3,622.211 seconds. The available one-second GPU CSV contains 3,591 valid samples. It begins 0.816 seconds after queue start and ends 29.855 seconds before queue finish, with one partial trailing CSV record. The buffered telemetry tail was not preserved before teardown; it is not reconstructed or presented as measured. Utilization and power statistics describe the available samples. This does not shorten the complete generation event journal or alter its cost/time denominator.

The post-teardown Runpod billing query returned only a partial earlier hourly bucket; the final usage bucket was not yet visible. That subtotal is published as incomplete evidence and is not treated as the experiment's full charge. The GPU reservation remains held until final billing reconciliation. Published GPU/disk costs use the verified quote and observed durations; fal's $2.00 is supported by all twenty per-response billing-unit counts.
