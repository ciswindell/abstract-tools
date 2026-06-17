# AA State Abstract Tool

Internal Windows desktop tool for segmenting and indexing New Mexico State
Land Office lease files. Merges a lease folder's PDFs, lets a user mark the
first page of each document, and exports a bookmarked combined PDF plus an
Excel index.

## Develop (Linux/macOS/Windows)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
QT_QPA_PLATFORM=offscreen python -m pytest      # run tests headless
python main.py                                  # launch the app
```

## Build the Windows .exe

Push a tag (`git tag v0.1.0 && git push --tags`) or run the
**Build Windows EXE** workflow manually from the Actions tab. Download the
`aa-state-abstract-tool` artifact — it contains `AA State Abstract Tool.exe`,
which staff run by double-clicking. No Python install required.
