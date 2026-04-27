import { create } from "zustand";
import { apiGet, apiPost } from "./api";
import type { CourseDiscovery, QuizOption, RecentEventItem, SessionStatus, WatchLogEvent, WatchRunState } from "./types";

type DayMode = "list" | "range";
type TimeMode = "list" | "window";

function dedupeSortedDays(days: string[]): string[] {
  return [...new Set(days.filter(Boolean))].sort();
}

function clampDateToQuiz(dateValue: string, quiz: QuizOption | null): string {
  if (!dateValue || !quiz?.open_from_date || !quiz?.open_to_date) {
    return dateValue;
  }
  if (dateValue < quiz.open_from_date) {
    return quiz.open_from_date;
  }
  if (dateValue > quiz.open_to_date) {
    return quiz.open_to_date;
  }
  return dateValue;
}

interface AppState {
  session: SessionStatus | null;
  course: CourseDiscovery | null;
  watchState: WatchRunState | null;
  recentEvents: RecentEventItem[];
  liveLogs: WatchLogEvent[];
  loading: boolean;
  error: string | null;
  tcbUrl: string;
  selectedQuizId: number | null;
  selectedQuizTitle: string;
  dayMode: DayMode;
  selectedDays: string[];
  pendingDay: string;
  rangeStart: string;
  rangeEnd: string;
  timeMode: TimeMode;
  timesRaw: string;
  windowStart: string;
  windowEnd: string;
  windowStepMinutes: number;
  pollIntervalSeconds: number;
  setField: (field: string, value: string | number | null) => void;
  refreshSession: (revalidate?: boolean) => Promise<void>;
  loadRecentEvents: () => Promise<void>;
  startLogin: () => Promise<void>;
  confirmLogin: () => Promise<void>;
  logout: () => Promise<void>;
  discoverCourse: () => Promise<void>;
  selectQuiz: (quizId: number) => void;
  setPendingDay: (value: string) => void;
  addSelectedDay: () => void;
  removeSelectedDay: (day: string) => void;
  setRangeStart: (value: string) => void;
  setRangeEnd: (value: string) => void;
  startWatch: () => Promise<void>;
  stopWatch: () => Promise<void>;
  pushLog: (event: WatchLogEvent) => void;
  setWatchState: (state: WatchRunState) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  session: null,
  course: null,
  watchState: null,
  recentEvents: [],
  liveLogs: [],
  loading: false,
  error: null,
  tcbUrl: "",
  selectedQuizId: null,
  selectedQuizTitle: "",
  dayMode: "range",
  selectedDays: [],
  pendingDay: "",
  rangeStart: "",
  rangeEnd: "",
  timeMode: "list",
  timesRaw: "",
  windowStart: "08:00",
  windowEnd: "18:00",
  windowStepMinutes: 10,
  pollIntervalSeconds: 10,
  setField: (field, value) => set({ [field]: value } as Partial<AppState>),
  refreshSession: async (revalidate = false) => {
    const session = await apiGet<SessionStatus>(`/session/status${revalidate ? "?revalidate=true" : ""}`);
    set({ session, error: null });
  },
  loadRecentEvents: async () => {
    const payload = await apiGet<{ items: RecentEventItem[] }>("/events/recent");
    set({ recentEvents: payload.items, error: null });
  },
  startLogin: async () => {
    await apiPost("/session/login/start", { host: "moodle.czu.cz" });
    await get().refreshSession(false);
  },
  confirmLogin: async () => {
    await apiPost("/session/login/confirm");
    await get().refreshSession(true);
  },
  logout: async () => {
    const session = await apiPost<SessionStatus>("/session/logout");
    set({ session, course: null, watchState: null, liveLogs: [] });
  },
  discoverCourse: async () => {
    const course = await apiPost<CourseDiscovery>("/courses/discover", { tcb_url: get().tcbUrl });
    const quiz = course.quizzes[0] ?? null;
    set({
      course,
      selectedQuizId: quiz?.quiz_id ?? null,
      selectedQuizTitle: quiz?.title ?? "",
      pendingDay: quiz?.open_from_date ?? "",
      selectedDays: [],
      rangeStart: quiz?.open_from_date ?? "",
      rangeEnd: quiz?.open_to_date ?? quiz?.open_from_date ?? "",
      error: null,
    });
  },
  selectQuiz: (quizId) => {
    const quiz = get().course?.quizzes.find((item) => item.quiz_id === quizId) ?? null;
    set({
      selectedQuizId: quizId,
      selectedQuizTitle: quiz?.title ?? "",
      pendingDay: quiz?.open_from_date ?? "",
      selectedDays: (get().selectedDays || []).map((day) => clampDateToQuiz(day, quiz)).filter(Boolean),
      rangeStart: clampDateToQuiz(get().rangeStart || quiz?.open_from_date || "", quiz) || quiz?.open_from_date || "",
      rangeEnd: clampDateToQuiz(get().rangeEnd || quiz?.open_to_date || "", quiz) || quiz?.open_to_date || "",
    });
  },
  setPendingDay: (value) => {
    const quiz = get().course?.quizzes.find((item) => item.quiz_id === get().selectedQuizId) ?? null;
    set({ pendingDay: clampDateToQuiz(value, quiz) });
  },
  addSelectedDay: () => {
    const quiz = get().course?.quizzes.find((item) => item.quiz_id === get().selectedQuizId) ?? null;
    const pending = clampDateToQuiz(get().pendingDay, quiz);
    if (!pending) {
      return;
    }
    set({ selectedDays: dedupeSortedDays([...get().selectedDays, pending]) });
  },
  removeSelectedDay: (day) => {
    set({ selectedDays: get().selectedDays.filter((item) => item !== day) });
  },
  setRangeStart: (value) => {
    const quiz = get().course?.quizzes.find((item) => item.quiz_id === get().selectedQuizId) ?? null;
    const nextStart = clampDateToQuiz(value, quiz);
    const currentEnd = clampDateToQuiz(get().rangeEnd, quiz);
    set({
      rangeStart: nextStart,
      rangeEnd: currentEnd && nextStart && currentEnd < nextStart ? nextStart : currentEnd,
    });
  },
  setRangeEnd: (value) => {
    const quiz = get().course?.quizzes.find((item) => item.quiz_id === get().selectedQuizId) ?? null;
    const nextEnd = clampDateToQuiz(value, quiz);
    const currentStart = clampDateToQuiz(get().rangeStart, quiz);
    set({
      rangeStart: currentStart && nextEnd && currentStart > nextEnd ? nextEnd : currentStart,
      rangeEnd: nextEnd,
    });
  },
  startWatch: async () => {
    const daysRaw =
      get().dayMode === "range"
        ? `${get().rangeStart}..${get().rangeEnd}`
        : dedupeSortedDays(get().selectedDays).join(",");
    const state = await apiPost<WatchRunState>("/watch/start", {
      tcb_url: get().tcbUrl,
      quiz_id: get().selectedQuizId,
      quiz_title: get().selectedQuizTitle,
      day_mode: get().dayMode,
      days_raw: daysRaw,
      time_mode: get().timeMode,
      times_raw: get().timeMode === "list" ? get().timesRaw : null,
      window_start: get().timeMode === "window" ? get().windowStart : null,
      window_end: get().timeMode === "window" ? get().windowEnd : null,
      window_step_minutes: get().timeMode === "window" ? get().windowStepMinutes : null,
      poll_interval_seconds: get().pollIntervalSeconds,
    });
    set({ watchState: state, liveLogs: [], error: null });
  },
  stopWatch: async () => {
    const state = await apiPost<WatchRunState>("/watch/stop");
    set({ watchState: state });
  },
  pushLog: (event) =>
    set((state) => ({
      liveLogs: [...state.liveLogs, event].slice(-200),
    })),
  setWatchState: (watchState) => set({ watchState }),
}));
