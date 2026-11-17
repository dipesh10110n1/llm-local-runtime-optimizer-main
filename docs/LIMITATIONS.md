# Limitations

* The live llama.cpp server was unavailable during audit; a real local inference integration remains environment-dependent.
* MySQL credentials/service state were unavailable, so production database connection is unverified.
* Official datasets were not downloaded automatically; no fabricated samples or scores were added.
* Legacy quality and performance records cannot be paired per prompt/trial. The optimizer exposes them only as one labelled aggregate general profile.
* Energy is unavailable until real hardware telemetry or an external power meter adapter is supplied. CPU/GPU utilization cannot substitute for joules.
* MBPP's subprocess controls reduce risk but are not a secure sandbox; use a VM/container for untrusted generated code.
