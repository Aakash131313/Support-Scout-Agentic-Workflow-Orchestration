# Phases 9-12 Implementation Notes

## Important Udacity Adapter Note

The exact Udacity endpoint request and response shape was not present in the phase documents. `UdacityModelClient` therefore uses an injected `transport` callable. Paste the request mechanism already verified in your Udacity project into a provider transport function later, without changing agents or schemas.

Example shape only:

```python
def verified_udacity_transport(system_prompt: str, user_prompt: str, timeout: int):
    # Reuse the exact verified request code from the prior Udacity project.
    # Return either a JSON string or a Python dictionary.
    ...
```

Do not invent endpoint paths, headers, model names, or payload fields. Keep credentials in `.env` and ensure `.env` remains ignored.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m support_scout.main --help
pytest
```
