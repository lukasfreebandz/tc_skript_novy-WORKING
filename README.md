# tc-sniper v3

`tc-sniper v3` je desktop GUI verze pro hlidani a automatickou rezervaci terminu v Moodle Testovacim centru na `moodle.czu.cz`.

Projekt ted obsahuje tri vrstvy:

- `shared Python core` pro login, session, discovery, parsing a booking
- `local FastAPI backend` pro GUI komunikaci
- `desktop GUI` v `Tauri + React + TypeScript`

CLI zustava zachovane jako fallback a debug rozhrani.

## Co umi

- otevrit browser pro Moodle login a ulozit session
- nacist TCB stranku z `/mod/tcb/view.php?id=...`
- najit testy a jejich dostupne dny
- spustit watcher nad vybranym testem
- live zobrazovat stav watcheru a logy
- automaticky rezervovat matching slot
- zobrazit posledni uspesne rezervace z lokalniho event logu

## Struktura projektu

```text
src/tc_sniper/
  api.py
  auth.py
  cli.py
  client.py
  models.py
  parsing.py
  prompts.py
  services/
  session_store.py
  settings.py
  watcher.py

desktop/
  package.json
  src/
  src-tauri/

tests/
  fixtures/
  test_inputs.py
  test_parsing.py
  test_services.py

run_tc_sniper.py
run_tc_sniper_api.py
run_tc_sniper.exe
pyproject.toml
README.md
```

## Runtime Overview

### Python core

Sdilena business logika zustava v Pythonu:

- login/session handling
- HTTP discovery a booking
- watcher orchestrace
- event log

### Local API

GUI komunikuje s lokalnim backendem na:

```text
http://127.0.0.1:8765
```

Hlavni endpointy:

- `GET /session/status`
- `POST /session/login/start`
- `POST /session/login/confirm`
- `POST /session/logout`
- `POST /courses/discover`
- `POST /watch/start`
- `POST /watch/stop`
- `GET /watch/status`
- `GET /watch/events`
- `GET /events/recent`

### Desktop GUI

GUI je v:

```text
desktop/
```

Frontend stack:

- React
- TypeScript
- Zustand
- Vite
- Tauri shell

## Spusteni

### 1. CLI fallback

Porad funguje puvodni Python/CLI workflow:

```powershell
python run_tc_sniper.py login
python run_tc_sniper.py status
python run_tc_sniper.py watch
python run_tc_sniper.py logout
```

Nebo hotovy one-file fallback build:

```powershell
.\run_tc_sniper.exe login
.\run_tc_sniper.exe status
.\run_tc_sniper.exe watch
.\run_tc_sniper.exe logout
```

### 2. Local API

```powershell
python -m pip install -e .[dev]
python -m playwright install chromium
python run_tc_sniper_api.py
```

### 3. GUI frontend

V dalsim terminalu:

```powershell
cd desktop
npm install
npm run dev
```

Build frontendu:

```powershell
cd desktop
npm run build
```

## GUI flow

Hlavni dashboard ma 4 casti:

### Session

- stav session
- `Login`
- `Logout`
- `Revalidate`
- instrukce pro potvrzeni prihlaseni po browser loginu

### Watch Setup

- TCB URL
- `Load tests`
- vyber testu
- dny jako `list` nebo `range`, vybirane pres kalendar
- casy jako `list` nebo `window`
- poll interval
- `Start watching`

Po nacteni testu GUI zobrazi i jeho okno:

- `otevřen od`
- `otevřen do`
- `doba trvání`

Vyber dnu je automaticky omezeny na datumove rozmezi daneho testu a backend tenhle limit overuje znovu i pri startu watcheru.

### Live Monitor

- aktualni stav watcheru
- aktivni konfigurace
- live log pruchodu
- `Stop`

### Recent Activity

- posledni uspesne rezervace z `%USERPROFILE%\.tc-sniper\events.log`

## Testy

Python testy:

```powershell
python -m pytest
```

Aktualni stav:

- parser testy
- input parsing testy
- service utility testy

Frontend verification:

```powershell
cd desktop
npm run build
```

## Poznamky

- GUI verze cilene miri na Windows desktop.
- Login zustava pres externi Playwright browser.
- Session a event log zustavaji v `%USERPROFILE%\.tc-sniper\`.
- Backend je navrzeny pro jeden aktivni watcher najednou.
- Tauri shell je scaffoldnuty v `desktop/src-tauri/`, ale na tomto stroji nebyl overen full desktop bundle, protoze tu neni nainstalovany Rust toolchain.
