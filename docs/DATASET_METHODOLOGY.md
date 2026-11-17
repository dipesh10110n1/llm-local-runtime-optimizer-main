# Dataset methodology

The reviewed manifest identifies MMLU, GSM8K, MBPP, IFEval, and CNN/DailyMail, including source path, split, target sample count, license field, task, and evaluation type. The pipeline records a download date and provenance JSON and preserves upstream IDs in `metadata.source_identifier`.

Run one reviewed source explicitly, for example `python -m datasets.dataset_loader gsm8k --limit 50`. This command may download data; it is intentionally not run by application startup. Verify current upstream licenses, availability, and terms before each download. The pipeline does not generate substitute examples.
