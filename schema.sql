create table if not exists cycle_stats (
    id              serial primary key,
    cycle_timestamp timestamptz not null,
    event_count     integer not null,
    mean_overround  float,
    median_overround float,
    min_overround   float,
    max_overround   float
);

create table if not exists violations (
    id                  serial primary key,
    event_ticker        text not null,
    violation_type      text not null,
    violation_size      float,
    survived_after_fees text check (survived_after_fees in ('survived', 'erased', 'not_applicable')),
    min_spread          float,
    max_spread          float,
    median_spread       float,
    time_opened         timestamptz not null,
    time_closed         timestamptz
);

create table if not exists market_calibration (
    id                  serial primary key,
    market_ticker       text not null unique,
    price_90d           float,
    price_30d           float,
    price_14d           float,
    price_7d            float,
    price_3d            float,
    price_1d            float,
    price_12h           float,
    price_1h            float,
    resolved_yes        boolean
);