\
@echo off
REM Triad369 Launchpad demo (Windows)
python -m venv .venv
call .\.venv\Scripts\activate
pip install -e .
triad369 init
triad369 generate --prompt "A tiny CLI that prints Hello 369" --target python --out build\hello369
triad369 pack --in build\hello369 --zip build\hello369.zip
echo Done. Zip at build\hello369.zip
pause
