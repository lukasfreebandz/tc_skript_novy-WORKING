# tc-sniper v2

`tc-sniper v2` je nova CLI aplikace pro hlidani a automatickou rezervaci terminu v Moodle Testovacim centru na `moodle.czu.cz`.

Projekt nahradil puvodni zabaleny `.exe` build. Repo ted obsahuje jen novy Python projekt.

## Co umi

- otevrit browser a ulozit prihlasenou Moodle session
- nacist TCB stranku kurzu z `/mod/tcb/view.php?id=...`
- najit vsechny testy na TCB strance
- vybrat konkretni test podle `quiz_id`
- nacist dostupne dny a sloty
- filtrovat dny a casy podle preferenci uzivatele
- pri nalezu matching slotu automaticky odeslat rezervaci

## Stack

- Python 3.12+
- Playwright
- httpx
- Typer
- Rich
- Pydantic
- pytest

## Struktura projektu

```text
src/tc_sniper/
  auth.py
  cli.py
  client.py
  models.py
  parsing.py
  prompts.py
  session_store.py
  settings.py
  watcher.py

tests/
  fixtures/
  test_inputs.py
  test_parsing.py

run_tc_sniper.py
pyproject.toml
```

## Instalace

V koreni projektu:

```powershell
python -m pip install -e .[dev]
python -m playwright install chromium
```

## Spusteni

Nejjednodussi je pouzivat root launcher:

```powershell
python run_tc_sniper.py --help
```

Hlavni prikazy:

```powershell
python run_tc_sniper.py login
python run_tc_sniper.py status
python run_tc_sniper.py watch
python run_tc_sniper.py logout
```

## Workflow

### 1. Login

```powershell
python run_tc_sniper.py login
```

Aplikace otevre Chromium okno. Prihlas se rucne do Moodle a vrat se do terminalu. Po potvrzeni se session ulozi lokalne do:

```text
%USERPROFILE%\.tc-sniper\
```

### 2. Kontrola session

```powershell
python run_tc_sniper.py status
```

### 3. Watch

```powershell
python run_tc_sniper.py watch
```

App se postupne zepta na:

1. TCB odkaz kurzu
2. vyber testu
3. dny
4. casy
5. interval mezi pruchody

Podporovane formaty dnu:

- `2026-05-30..2026-06-20`
- `2026-30-05..2026-20-06`
- `30.05.2026..20.06.2026`
- `2026-05-30,2026-06-03`

Podporovane casy:

- `list`: `08:40,14:30,16:00`
- `window`: od-do + krok v minutach

## Jak funguje booking

Discovery:

- dny se nacitaji pres `GET /mod/tcb/view.php?id=<tcb_id>&quiz=<quiz_id>`
- sloty se nacitaji pres `GET /mod/tcb/view.php?id=<tcb_id>&day=<date>&quiz=<quiz_id>`

Mutace:

- registrace pres `POST /mod/tcb/view.php`
- odhlaseni pres `POST /mod/tcb/view.php`
- zmena terminu je pripravena v booking klientovi

## Testy

```powershell
python -m pytest
```

Aktualne jsou pokryte hlavne:

- parsovani TCB stranky
- parsovani dnu a slotu
- parsovani rezervace
- vstupni formaty dnu a casu

## Poznamky

- Projekt zatim cilene podporuje `moodle.czu.cz`.
- Aplikace je zatim `CLI only`.
- Session soubory nejsou verzovane a jsou v `.gitignore`.
- Lokalni event log uspesnych rezervaci se uklada do `%USERPROFILE%\.tc-sniper\events.log`.
