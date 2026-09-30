export interface Violation {
  event_ticker: string
  violation_type: "overround" | "arbitrage" | "monotonicity"
  market_count: number
  first_seen: string
  last_seen: string
  max_size: number
  max_size_after_fees: number | null
  sub_violation_count: number | null
}

export interface ViolationsResponse {
  updated_at: string | null;
  violation_count: number;
  violations: Violation[];
}