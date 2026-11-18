# Limitations

- MySQL is not detected in the audited environment, so production persistence cannot be verified until it is installed/configured.
- No local llama.cpp server was running during audit, so end-to-end inference is implemented but unverified in this session.
- External datasets are intentionally not downloaded automatically; source licences and versions must be confirmed before preparation.
- MBPP code execution is disabled by default (`ALLOW_UNSAFE_CODE_EVAL` is not set) because a temporary Python process on Windows is not a hardened security boundary. Enable it only inside a disposable container/VM with explicit resource/network restrictions.
- Integrated graphics reporting and CPU/GPU utilisation are not energy measurements. Energy values remain unavailable without supported telemetry.
- Historic CSV schemas lack some required metadata. The optimizer preserves this uncertainty rather than claiming quality or energy measurements.
