# InstaPrep

Web app per preparare foto e testi Instagram:
- **Ritaglio automatico centrato** in due formati: post feed **4:5** (1080×1350) e storia **9:16** (1080×1920)
- **Correzione automatica** (autocontrast) **+ slider manuali** per luminosità, contrasto, saturazione, nitidezza
- **Caption + hashtag** generati con l'**API di Claude** a partire da una descrizione e un tono a scelta
- Download diretto delle immagini elaborate

Stack: **FastAPI** + **Pillow** (backend), frontend statico single-page. Deploy su **Railway**.

---

## Struttura

```
instaprep/
├─ app/
│  ├─ main.py              # backend: /api/process (immagini) + /api/caption (Claude)
│  └─ static/index.html    # interfaccia
├─ requirements.txt
├─ Procfile
├─ railway.json
└─ .gitignore
```

## Avvio in locale

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...    # la tua chiave
uvicorn app.main:app --reload
```
Apri http://localhost:8000

## Deploy su Railway

1. Crea un repo su GitHub e fai push di questa cartella.
2. Su Railway: **New Project → Deploy from GitHub repo** → seleziona il repo.
3. Railway rileva Python (Nixpacks) e usa lo `startCommand` di `railway.json`.
4. In **Variables** aggiungi:
   - `ANTHROPIC_API_KEY` = la tua chiave Anthropic
5. Railway espone automaticamente la porta tramite `$PORT`. Al termine avrai l'URL pubblico.

## Note

- Il modello usato è `claude-sonnet-4-6`. Puoi cambiarlo in `app/main.py`.
- I formati di ritaglio sono definiti nel dict `FORMATS` in `app/main.py`: modificali lì se ti servono altre dimensioni.
- Nessun dato viene salvato: le immagini sono processate in memoria e restituite subito.
