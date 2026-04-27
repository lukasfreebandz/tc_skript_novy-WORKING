export type LoginFlowState =
  | "idle"
  | "opening_browser"
  | "waiting_for_confirmation"
  | "completing"
  | "success"
  | "error";

export type WatchState =
  | "idle"
  | "validating_session"
  | "discovering_course"
  | "running"
  | "attempting_booking"
  | "booked"
  | "already_reserved"
  | "stopped"
  | "error";

export interface SessionStatus {
  status: "logged_out" | "valid" | "expired" | "unknown";
  host?: string | null;
  storage_state_path?: string | null;
  created_at?: string | null;
  validated_at?: string | null;
  message?: string | null;
  login_flow?: {
    status: LoginFlowState;
    host?: string | null;
    message?: string | null;
    started_at?: string | null;
    finished_at?: string | null;
  } | null;
}

export interface AvailableDay {
  date: string;
  seats: number;
  url: string;
}

export interface Reservation {
  quiz_id: number;
  day: string;
  time: string;
  arrive_at?: string | null;
  unregister_slot_id?: number | null;
  unregister_deadline?: string | null;
}

export interface QuizOption {
  quiz_id: number;
  title: string;
  quiz_url: string;
  open_from?: string | null;
  open_to?: string | null;
  open_from_date?: string | null;
  open_to_date?: string | null;
  duration?: string | null;
  available_days: AvailableDay[];
  reservation?: Reservation | null;
}

export interface CourseDiscovery {
  host: string;
  tcb_id: number;
  course_title?: string | null;
  sesskey?: string | null;
  quizzes: QuizOption[];
}

export interface WatchLogEvent {
  timestamp: string;
  level: "info" | "success" | "warning" | "error" | "state";
  message: string;
  attempt?: number | null;
  day?: string | null;
  time?: string | null;
  seats?: number | null;
  state?: WatchState | null;
}

export interface WatchRunState {
  status: WatchState;
  message: string;
  active: boolean;
  attempt: number;
  started_at?: string | null;
  updated_at: string;
  preferences?: {
    tcb_url: string;
    quiz_id: number;
    quiz_title: string;
    days: string[];
    times: string[];
    poll_interval_seconds: number;
  } | null;
  reservation?: Reservation | null;
  recent_logs: WatchLogEvent[];
}

export interface RecentEventItem {
  timestamp: string;
  action: string;
  quiz_id?: number | null;
  day?: string | null;
  time?: string | null;
}
