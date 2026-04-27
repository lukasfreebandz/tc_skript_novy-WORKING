import { useEffect, useMemo } from "react";
import type { ReactNode } from "react";
import { apiGet } from "./api";
import { useAppStore } from "./store";
import type { WatchLogEvent, WatchRunState } from "./types";

function Section(props: { title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>{props.title}</h2>
        <div className="panel-actions">{props.actions}</div>
      </div>
      <div className="panel-body">{props.children}</div>
    </section>
  );
}

function StatusPill(props: { value: string }) {
  return <span className={`status-pill status-${props.value.replace(/_/g, "-")}`}>{props.value}</span>;
}

export function App() {
  const session = useAppStore((state) => state.session);
  const course = useAppStore((state) => state.course);
  const watchState = useAppStore((state) => state.watchState);
  const recentEvents = useAppStore((state) => state.recentEvents);
  const liveLogs = useAppStore((state) => state.liveLogs);
  const {
    tcbUrl,
    selectedQuizId,
    selectedQuizTitle,
    dayMode,
    selectedDays,
    pendingDay,
    rangeStart,
    rangeEnd,
    timeMode,
    timesRaw,
    windowStart,
    windowEnd,
    windowStepMinutes,
    pollIntervalSeconds,
  } = useAppStore((state) => state);
  const setField = useAppStore((state) => state.setField);
  const refreshSession = useAppStore((state) => state.refreshSession);
  const loadRecentEvents = useAppStore((state) => state.loadRecentEvents);
  const startLogin = useAppStore((state) => state.startLogin);
  const confirmLogin = useAppStore((state) => state.confirmLogin);
  const logout = useAppStore((state) => state.logout);
  const discoverCourse = useAppStore((state) => state.discoverCourse);
  const selectQuiz = useAppStore((state) => state.selectQuiz);
  const setPendingDay = useAppStore((state) => state.setPendingDay);
  const addSelectedDay = useAppStore((state) => state.addSelectedDay);
  const removeSelectedDay = useAppStore((state) => state.removeSelectedDay);
  const setRangeStart = useAppStore((state) => state.setRangeStart);
  const setRangeEnd = useAppStore((state) => state.setRangeEnd);
  const startWatch = useAppStore((state) => state.startWatch);
  const stopWatch = useAppStore((state) => state.stopWatch);
  const pushLog = useAppStore((state) => state.pushLog);
  const setWatchState = useAppStore((state) => state.setWatchState);

  useEffect(() => {
    void refreshSession(false);
    void loadRecentEvents();
    void apiGet<WatchRunState>("/watch/status").then(setWatchState).catch(() => undefined);
  }, [loadRecentEvents, refreshSession, setWatchState]);

  useEffect(() => {
    const source = new EventSource("http://127.0.0.1:8765/watch/events");
    source.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { type: "state" | "log"; payload: WatchRunState | WatchLogEvent };
      if (payload.type === "state") {
        setWatchState(payload.payload as WatchRunState);
      } else {
        pushLog(payload.payload as WatchLogEvent);
      }
    };
    return () => source.close();
  }, [pushLog, setWatchState]);

  const selectedQuiz = useMemo(
    () => course?.quizzes.find((quiz) => quiz.quiz_id === selectedQuizId) ?? null,
    [course?.quizzes, selectedQuizId],
  );

  const loginWaiting = session?.login_flow?.status === "waiting_for_confirmation";
  const watchBusy = watchState?.active;
  const selectedDaysSummary = selectedDays.join(", ");
  const daysReady =
    dayMode === "range"
      ? Boolean(rangeStart && rangeEnd)
      : selectedDays.length > 0;

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Desktop Dashboard</p>
          <h1>tc-sniper v3</h1>
          <p className="subtitle">GUI nad existujicim Python jadrem pro login, discovery, watch a live monitoring.</p>
        </div>
        <div className="hero-status">
          <span>Session</span>
          <StatusPill value={session?.status ?? "unknown"} />
        </div>
      </header>

      <div className="grid">
        <Section
          title="Session"
          actions={
            <>
              <button onClick={() => void refreshSession(true)}>Revalidate</button>
              <button onClick={() => void logout()}>Logout</button>
            </>
          }
        >
          <div className="row">
            <StatusPill value={session?.status ?? "unknown"} />
            <span>{session?.message ?? "Kontroluji session..."}</span>
          </div>
          <p className="muted">Storage: {session?.storage_state_path ?? "%USERPROFILE%\\.tc-sniper\\session\\storage_state.json"}</p>
          <div className="inline-actions">
            <button className="primary" onClick={() => void startLogin()}>
              Login
            </button>
            {loginWaiting ? (
              <button className="primary ghost" onClick={() => void confirmLogin()}>
                Potvrdit login
              </button>
            ) : null}
          </div>
          {session?.login_flow ? (
            <div className="callout">
              <strong>Login flow:</strong> <StatusPill value={session.login_flow.status} />
              <p>{session.login_flow.message}</p>
            </div>
          ) : null}
        </Section>

        <Section title="Watch Setup" actions={<button onClick={() => void discoverCourse()}>Load tests</button>}>
          <label>
            TCB URL
            <input value={tcbUrl} onChange={(event) => setField("tcbUrl", event.target.value)} placeholder="https://moodle.czu.cz/mod/tcb/view.php?id=..." />
          </label>
          <label>
            Test
            <select
              value={selectedQuizId ?? ""}
              onChange={(event) => {
                const quizId = Number(event.target.value);
                selectQuiz(quizId);
              }}
            >
              <option value="" disabled>
                {course ? "Vyber test" : "Nejdriv nacti TCB"}
              </option>
              {course?.quizzes.map((quiz) => (
                <option key={quiz.quiz_id} value={quiz.quiz_id}>
                  {quiz.title}
                </option>
              ))}
            </select>
          </label>
          {selectedQuiz ? (
            <div className="callout">
              <p><strong>Okno testu:</strong> {selectedQuiz.open_from ?? "?"} až {selectedQuiz.open_to ?? "?"}</p>
              <p><strong>Doba trvání:</strong> {selectedQuiz.duration ?? "?"}</p>
            </div>
          ) : null}
          {selectedQuiz?.reservation ? (
            <div className="callout warning">
              Rezervace uz existuje: {selectedQuiz.reservation.day} {selectedQuiz.reservation.time}
            </div>
          ) : null}
          <div className="split">
            <label>
              Dny
              <select value={dayMode} onChange={(event) => setField("dayMode", event.target.value)}>
                <option value="range">range</option>
                <option value="list">list</option>
              </select>
            </label>
            {dayMode === "range" ? (
              <>
                <label>
                  Od
                  <input
                    type="date"
                    value={rangeStart}
                    min={selectedQuiz?.open_from_date ?? undefined}
                    max={selectedQuiz?.open_to_date ?? undefined}
                    onChange={(event) => setRangeStart(event.target.value)}
                  />
                </label>
                <label>
                  Do
                  <input
                    type="date"
                    value={rangeEnd}
                    min={selectedQuiz?.open_from_date ?? undefined}
                    max={selectedQuiz?.open_to_date ?? undefined}
                    onChange={(event) => setRangeEnd(event.target.value)}
                  />
                </label>
              </>
            ) : (
              <div className="calendar-list-picker grow">
                <div className="split">
                  <label className="grow">
                    Vyber den
                    <input
                      type="date"
                      value={pendingDay}
                      min={selectedQuiz?.open_from_date ?? undefined}
                      max={selectedQuiz?.open_to_date ?? undefined}
                      onChange={(event) => setPendingDay(event.target.value)}
                    />
                  </label>
                  <button className="align-end" type="button" onClick={() => addSelectedDay()}>
                    Pridat den
                  </button>
                </div>
                <div className="chip-row">
                  {selectedDays.map((day) => (
                    <button key={day} type="button" className="day-chip" onClick={() => removeSelectedDay(day)}>
                      {day} ×
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          <p className="muted">
            {dayMode === "range"
              ? `Vybrany rozsah: ${rangeStart || "?"} .. ${rangeEnd || "?"}`
              : `Vybrane dny: ${selectedDaysSummary || "zatim zadne"}`}
          </p>
          <div className="split">
            <label>
              Casy
              <select value={timeMode} onChange={(event) => setField("timeMode", event.target.value)}>
                <option value="list">list</option>
                <option value="window">window</option>
              </select>
            </label>
            {timeMode === "list" ? (
              <label className="grow">
                Input
                <input value={timesRaw} onChange={(event) => setField("timesRaw", event.target.value)} placeholder="08:40,14:30,16:00" />
              </label>
            ) : (
              <>
                <label>
                  OD
                  <input value={windowStart} onChange={(event) => setField("windowStart", event.target.value)} />
                </label>
                <label>
                  DO
                  <input value={windowEnd} onChange={(event) => setField("windowEnd", event.target.value)} />
                </label>
                <label>
                  Step
                  <input
                    type="number"
                    value={windowStepMinutes}
                    onChange={(event) => setField("windowStepMinutes", Number(event.target.value))}
                  />
                </label>
              </>
            )}
          </div>
          <label>
            Poll interval (s)
            <input
              type="number"
              min={1}
              value={pollIntervalSeconds}
              onChange={(event) => setField("pollIntervalSeconds", Number(event.target.value))}
            />
          </label>
          <div className="inline-actions">
            <button className="primary" disabled={!selectedQuizId || !!selectedQuiz?.reservation || !daysReady} onClick={() => void startWatch()}>
              Start watching
            </button>
            <button disabled={!watchBusy} onClick={() => void stopWatch()}>
              Stop
            </button>
          </div>
          {selectedQuizTitle ? <p className="muted">Vybrany test: {selectedQuizTitle}</p> : null}
        </Section>

        <Section title="Live Monitor">
          <div className="row">
            <StatusPill value={watchState?.status ?? "idle"} />
            <span>{watchState?.message ?? "Watcher zatim nebezi."}</span>
          </div>
          {watchState?.preferences ? (
            <div className="callout">
              <p>
                <strong>{watchState.preferences.quiz_title}</strong>
              </p>
              <p>Dny: {watchState.preferences.days.join(", ")}</p>
              <p>Casy: {watchState.preferences.times.join(", ")}</p>
            </div>
          ) : null}
          <div className="log-panel">
            {liveLogs.length === 0 ? <p className="muted">Zatim bez live logu.</p> : null}
            {liveLogs.map((event, index) => (
              <div key={`${event.timestamp}-${index}`} className={`log-line log-${event.level}`}>
                <span>{event.message}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Recent Activity" actions={<button onClick={() => void loadRecentEvents()}>Refresh</button>}>
          <div className="events-list">
            {recentEvents.length === 0 ? <p className="muted">Zatim bez uspesnych rezervaci.</p> : null}
            {recentEvents.map((event) => (
              <article key={`${event.timestamp}-${event.action}`} className="event-card">
                <div>
                  <strong>{event.action}</strong>
                  <p>Quiz {event.quiz_id ?? "?"}</p>
                </div>
                <div className="event-meta">
                  <span>{event.day ?? "-"}</span>
                  <span>{event.time ?? "-"}</span>
                </div>
              </article>
            ))}
          </div>
        </Section>
      </div>
    </main>
  );
}
