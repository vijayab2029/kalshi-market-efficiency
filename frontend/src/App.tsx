import { useState, useEffect } from "react";
import { fetchViolations } from "./api";
import type { Violation, ViolationsResponse } from "./types";

const POLL_INTERVAL_MS = 480000;
const POLL_INTERVAL_SEC = POLL_INTERVAL_MS / 1000;

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatAge(isoString: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(isoString).getTime()) / 1000
  );
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

const TAG_STYLES: Record<Violation["violation_type"], string> = {
  overround: "bg-[#3987e5]/15 text-[#3987e5] ring-[#3987e5]/30",
  arbitrage: "bg-[#d95926]/15 text-[#d95926] ring-[#d95926]/30",
  monotonicity: "bg-[#199e70]/15 text-[#199e70] ring-[#199e70]/30",
};

function getViolationClass(type: Violation["violation_type"]): string {
  return `inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${TAG_STYLES[type]}`;
}

function App() {
  const [data, setData] = useState<ViolationsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [secondsUntilPoll, setSecondsUntilPoll] = useState(POLL_INTERVAL_SEC);

  useEffect(() => {
    const tick = setInterval(() => {
      setSecondsUntilPoll((prev) => (prev <= 1 ? POLL_INTERVAL_SEC : prev - 1));
    }, 1000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    const poll = async () => {
      try {
        const result = await fetchViolations()
        setData(result)
        setError(null)
        setLoading(false)
        setSecondsUntilPoll(POLL_INTERVAL_SEC)
      }
      catch (error) {
        setError(error instanceof Error ? error.message : "Unknown error")
        setLoading(false)
      }
    }
    poll()
    const pollInterval = setInterval(() => {
      poll()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(pollInterval)
  }, [])

  const violations = data?.violations ?? [];
  const overroundCount = violations.filter(
    (violation) => violation.violation_type === "overround"
  ).length;
  const arbitrageCount = violations.filter(
    (violation) => violation.violation_type === "arbitrage"
  ).length;
  const monotonicityCount = violations.filter(
    (violation) => violation.violation_type === "monotonicity"
  ).length;

  const sortedViolations = [...violations].sort(
    (a, b) => b.max_size - a.max_size
  );

  return (
    <div className="min-h-screen font-sans text-slate-100 bg-gradient-to-b from-slate-950 via-slate-950 to-slate-900">
      <div className="mx-auto px-6 py-10 max-w-6xl">
        <header className="mb-8 flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-end">
          <h1 className="text-2xl font-semibold text-white tracking-tight sm:text-3xl">
            Kalshi Market Efficiency Tracker
          </h1>
          <div className="flex flex-col gap-1 text-sm sm:items-end text-slate-400">
            {data?.updated_at && (
              <p className="tabular-nums">
                Last updated {formatAge(data.updated_at)}
              </p>
            )}
            <p className="tabular-nums">
              Next refresh in {Math.floor(secondsUntilPoll / 60)}:
              {String(secondsUntilPoll % 60).padStart(2, "0")}
            </p>
          </div>
        </header>

        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-xl border bg-slate-900/60 p-5 border-slate-800 shadow-lg shadow-black/20 backdrop-blur-sm transition-colors hover:border-slate-700">
            <span className="block text-3xl font-bold text-white tabular-nums">
              {violations.length}
            </span>
            <span className="mt-1 block text-xs font-medium uppercase text-slate-400 tracking-wider">
              Active violations
            </span>
          </div>
          <div className="rounded-xl border bg-slate-900/60 p-5 border-slate-800 shadow-lg shadow-black/20 backdrop-blur-sm transition-colors hover:border-slate-700">
            <span className="block text-3xl font-bold text-[#3987e5] tabular-nums">
              {overroundCount}
            </span>
            <span className="mt-1 block text-xs font-medium uppercase tracking-wider text-slate-400">
              Overround
            </span>
          </div>
          <div className="rounded-xl border bg-slate-900/60 p-5 border-slate-800 shadow-lg shadow-black/20 backdrop-blur-sm transition-colors hover:border-slate-700">
            <span className="block text-3xl font-bold tabular-nums text-[#d95926]">
              {arbitrageCount}
            </span>
            <span className="mt-1 block text-xs font-medium uppercase tracking-wider text-slate-400">
              Arbitrage
            </span>
          </div>
          <div className="rounded-xl border bg-slate-900/60 p-5 border-slate-800 shadow-lg shadow-black/20 backdrop-blur-sm transition-colors hover:border-slate-700">
            <span className="block text-3xl font-bold text-[#199e70] tabular-nums">
              {monotonicityCount}
            </span>
            <span className="mt-1 block text-xs font-medium uppercase tracking-wider text-slate-400">
              Monotonicity
            </span>
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border px-4 py-3 text-sm border-red-500/30 bg-red-500/10 text-red-300">
            {error}
          </div>
        )}

        {loading && !data ? (
          <div className="rounded-xl border py-16 text-center text-sm border-slate-800 bg-slate-900/40 text-slate-400">
            Loading violations...
          </div>
        ) : sortedViolations.length === 0 ? (
          <div className="rounded-xl border py-16 text-center text-sm border-slate-800 bg-slate-900/40 text-slate-400">
            No active violations detected.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b bg-slate-900/80 border-slate-800">
                  <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Event</th>
                  <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Type</th>
                  <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Markets</th>
                  <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Size</th>
                  <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">After Fees</th>
                  <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">First Seen</th>
                  <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {sortedViolations.map((violation) => (
                  <tr
                    key={`${violation.event_ticker}-${violation.violation_type}`}
                    className="border-b transition-colors border-slate-800/50 hover:bg-slate-800/30"
                  >
                    <td className="px-4 py-3 font-medium text-slate-200">{violation.event_ticker}</td>
                    <td className="px-4 py-3">
                      <span className={getViolationClass(violation.violation_type)}>{violation.violation_type}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-300 tabular-nums">{violation.market_count}</td>
                    <td className="px-4 py-3 text-slate-300 tabular-nums">{violation.max_size.toFixed(4)}</td>
                    <td className="px-4 py-3 text-slate-300 tabular-nums">
                      {violation.max_size_after_fees !== null ? violation.max_size_after_fees.toFixed(4) : "—"}
                    </td>
                    <td className="px-4 py-3 text-slate-400 tabular-nums">{formatTime(violation.first_seen)}</td>
                    <td className="px-4 py-3 text-slate-400 tabular-nums">{formatAge(violation.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

