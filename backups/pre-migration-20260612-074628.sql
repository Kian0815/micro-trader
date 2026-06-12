--
-- PostgreSQL database dump
--

\restrict IrzCqz3Q91UzExcznoEeuGjqvtKxfhwhh5vGcco6q1jPtkcy4nXRpkBKcUBsUjf

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: assetkind; Type: TYPE; Schema: public; Owner: microtrader
--

CREATE TYPE public.assetkind AS ENUM (
    'CRYPTO',
    'ETF',
    'STOCK'
);


ALTER TYPE public.assetkind OWNER TO microtrader;

--
-- Name: executionintentstatus; Type: TYPE; Schema: public; Owner: microtrader
--

CREATE TYPE public.executionintentstatus AS ENUM (
    'PENDING',
    'FILLED',
    'SKIPPED',
    'FAILED'
);


ALTER TYPE public.executionintentstatus OWNER TO microtrader;

--
-- Name: positionstatus; Type: TYPE; Schema: public; Owner: microtrader
--

CREATE TYPE public.positionstatus AS ENUM (
    'OPEN',
    'CLOSED'
);


ALTER TYPE public.positionstatus OWNER TO microtrader;

--
-- Name: signalaction; Type: TYPE; Schema: public; Owner: microtrader
--

CREATE TYPE public.signalaction AS ENUM (
    'BUY',
    'SELL',
    'HOLD'
);


ALTER TYPE public.signalaction OWNER TO microtrader;

--
-- Name: simulationstatus; Type: TYPE; Schema: public; Owner: microtrader
--

CREATE TYPE public.simulationstatus AS ENUM (
    'ACTIVE',
    'CLOSED'
);


ALTER TYPE public.simulationstatus OWNER TO microtrader;

--
-- Name: trademode; Type: TYPE; Schema: public; Owner: microtrader
--

CREATE TYPE public.trademode AS ENUM (
    'PAPER'
);


ALTER TYPE public.trademode OWNER TO microtrader;

--
-- Name: tradeside; Type: TYPE; Schema: public; Owner: microtrader
--

CREATE TYPE public.tradeside AS ENUM (
    'BUY',
    'SELL'
);


ALTER TYPE public.tradeside OWNER TO microtrader;

--
-- Name: tradestatus; Type: TYPE; Schema: public; Owner: microtrader
--

CREATE TYPE public.tradestatus AS ENUM (
    'FILLED',
    'SKIPPED'
);


ALTER TYPE public.tradestatus OWNER TO microtrader;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: assets; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.assets (
    id integer NOT NULL,
    symbol character varying(16) NOT NULL,
    name character varying(64) NOT NULL,
    kind public.assetkind NOT NULL,
    external_id character varying(64) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.assets OWNER TO microtrader;

--
-- Name: assets_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.assets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.assets_id_seq OWNER TO microtrader;

--
-- Name: assets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.assets_id_seq OWNED BY public.assets.id;


--
-- Name: engine_runs; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.engine_runs (
    id integer NOT NULL,
    status character varying(16) NOT NULL,
    assets_count integer NOT NULL,
    news_items_count integer NOT NULL,
    signals_count integer NOT NULL,
    message text NOT NULL,
    started_at timestamp without time zone NOT NULL,
    completed_at timestamp without time zone NOT NULL
);


ALTER TABLE public.engine_runs OWNER TO microtrader;

--
-- Name: engine_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.engine_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.engine_runs_id_seq OWNER TO microtrader;

--
-- Name: engine_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.engine_runs_id_seq OWNED BY public.engine_runs.id;


--
-- Name: execution_intents; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.execution_intents (
    id integer NOT NULL,
    intent_key character varying(160) NOT NULL,
    asset_id integer NOT NULL,
    signal_id integer,
    position_id integer,
    mode character varying(16) NOT NULL,
    execution_target character varying(16) NOT NULL,
    side public.tradeside NOT NULL,
    status public.executionintentstatus NOT NULL,
    source character varying(24) NOT NULL,
    notional_eur double precision NOT NULL,
    price_hint double precision,
    quantity double precision,
    reason text NOT NULL,
    broker_provider character varying(32),
    broker_order_id character varying(80),
    broker_status character varying(32),
    error_message text NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.execution_intents OWNER TO microtrader;

--
-- Name: execution_intents_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.execution_intents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.execution_intents_id_seq OWNER TO microtrader;

--
-- Name: execution_intents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.execution_intents_id_seq OWNED BY public.execution_intents.id;


--
-- Name: market_ticks; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.market_ticks (
    id integer NOT NULL,
    asset_id integer NOT NULL,
    price double precision NOT NULL,
    change_24h_pct double precision NOT NULL,
    volume_24h double precision NOT NULL,
    source character varying(32) NOT NULL,
    captured_at timestamp without time zone NOT NULL
);


ALTER TABLE public.market_ticks OWNER TO microtrader;

--
-- Name: market_ticks_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.market_ticks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.market_ticks_id_seq OWNER TO microtrader;

--
-- Name: market_ticks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.market_ticks_id_seq OWNED BY public.market_ticks.id;


--
-- Name: news_items; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.news_items (
    id integer NOT NULL,
    asset_id integer,
    source character varying(64) NOT NULL,
    title character varying(280) NOT NULL,
    summary text NOT NULL,
    url character varying(1024) NOT NULL,
    sentiment_score double precision NOT NULL,
    event_type character varying(64) NOT NULL,
    published_at timestamp without time zone NOT NULL,
    ingested_at timestamp without time zone NOT NULL
);


ALTER TABLE public.news_items OWNER TO microtrader;

--
-- Name: news_items_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.news_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.news_items_id_seq OWNER TO microtrader;

--
-- Name: news_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.news_items_id_seq OWNED BY public.news_items.id;


--
-- Name: positions; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.positions (
    id integer NOT NULL,
    asset_id integer NOT NULL,
    status public.positionstatus NOT NULL,
    quantity double precision NOT NULL,
    entry_price double precision NOT NULL,
    stop_loss double precision NOT NULL,
    take_profit double precision NOT NULL,
    opened_at timestamp without time zone NOT NULL,
    closed_at timestamp without time zone,
    exit_price double precision,
    pnl_eur double precision
);


ALTER TABLE public.positions OWNER TO microtrader;

--
-- Name: positions_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.positions_id_seq OWNER TO microtrader;

--
-- Name: positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.positions_id_seq OWNED BY public.positions.id;


--
-- Name: provider_health_samples; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.provider_health_samples (
    id integer NOT NULL,
    provider character varying(128) NOT NULL,
    asset_kind character varying(16) NOT NULL,
    status character varying(16) NOT NULL,
    attempted_assets integer NOT NULL,
    successful_assets integer NOT NULL,
    failed_assets integer NOT NULL,
    stale_assets integer NOT NULL,
    cache_used boolean NOT NULL,
    message text NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.provider_health_samples OWNER TO microtrader;

--
-- Name: provider_health_samples_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.provider_health_samples_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.provider_health_samples_id_seq OWNER TO microtrader;

--
-- Name: provider_health_samples_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.provider_health_samples_id_seq OWNED BY public.provider_health_samples.id;


--
-- Name: reconciliation_snapshots; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.reconciliation_snapshots (
    id integer NOT NULL,
    status character varying(16) NOT NULL,
    mode character varying(16) NOT NULL,
    execution_target character varying(16) NOT NULL,
    provider character varying(32) NOT NULL,
    ledger_open_positions integer NOT NULL,
    ledger_closed_positions integer NOT NULL,
    ledger_open_notional_eur double precision NOT NULL,
    ledger_realized_pnl_eur double precision NOT NULL,
    pending_intents integer NOT NULL,
    failed_intents integer NOT NULL,
    broker_connected boolean NOT NULL,
    broker_account_id character varying(80),
    broker_buying_power character varying(80),
    message text NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.reconciliation_snapshots OWNER TO microtrader;

--
-- Name: reconciliation_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.reconciliation_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reconciliation_snapshots_id_seq OWNER TO microtrader;

--
-- Name: reconciliation_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.reconciliation_snapshots_id_seq OWNED BY public.reconciliation_snapshots.id;


--
-- Name: signal_outcome_snapshots; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.signal_outcome_snapshots (
    id integer NOT NULL,
    signal_id integer NOT NULL,
    horizon_hours integer NOT NULL,
    signal_price double precision NOT NULL,
    observed_price double precision,
    market_move_pct double precision,
    decision_edge_pct double precision,
    pnl_pct double precision,
    outcome_label character varying(32) NOT NULL,
    outcome_status character varying(16) NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.signal_outcome_snapshots OWNER TO microtrader;

--
-- Name: signal_outcome_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.signal_outcome_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.signal_outcome_snapshots_id_seq OWNER TO microtrader;

--
-- Name: signal_outcome_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.signal_outcome_snapshots_id_seq OWNED BY public.signal_outcome_snapshots.id;


--
-- Name: signals; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.signals (
    id integer NOT NULL,
    asset_id integer NOT NULL,
    action public.signalaction NOT NULL,
    score double precision NOT NULL,
    sentiment_score double precision NOT NULL,
    momentum_score double precision NOT NULL,
    rationale text NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.signals OWNER TO microtrader;

--
-- Name: signals_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.signals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.signals_id_seq OWNER TO microtrader;

--
-- Name: signals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.signals_id_seq OWNED BY public.signals.id;


--
-- Name: simulation_alerts; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.simulation_alerts (
    id integer NOT NULL,
    simulation_id integer NOT NULL,
    level character varying(16) NOT NULL,
    title character varying(120) NOT NULL,
    message text NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.simulation_alerts OWNER TO microtrader;

--
-- Name: simulation_alerts_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.simulation_alerts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.simulation_alerts_id_seq OWNER TO microtrader;

--
-- Name: simulation_alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.simulation_alerts_id_seq OWNED BY public.simulation_alerts.id;


--
-- Name: state_events; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.state_events (
    id integer NOT NULL,
    event_key character varying(64) NOT NULL,
    category character varying(32) NOT NULL,
    severity character varying(16) NOT NULL,
    title character varying(160) NOT NULL,
    message text NOT NULL,
    fingerprint character varying(255) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.state_events OWNER TO microtrader;

--
-- Name: state_events_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.state_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.state_events_id_seq OWNER TO microtrader;

--
-- Name: state_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.state_events_id_seq OWNED BY public.state_events.id;


--
-- Name: strategy_simulations; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.strategy_simulations (
    id integer NOT NULL,
    asset_id integer NOT NULL,
    scenario_key character varying(32) NOT NULL,
    scenario_label character varying(64) NOT NULL,
    setup_type character varying(32) NOT NULL,
    opened_signal_score double precision NOT NULL,
    status public.simulationstatus NOT NULL,
    initial_notional_eur double precision NOT NULL,
    quantity double precision NOT NULL,
    entry_price double precision NOT NULL,
    latest_price double precision NOT NULL,
    pnl_eur double precision NOT NULL,
    pnl_pct double precision NOT NULL,
    stop_price double precision NOT NULL,
    take_profit_price double precision NOT NULL,
    trailing_stop_price double precision NOT NULL,
    alert_flags text NOT NULL,
    opened_reason text NOT NULL,
    started_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    closed_at timestamp without time zone
);


ALTER TABLE public.strategy_simulations OWNER TO microtrader;

--
-- Name: strategy_simulations_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.strategy_simulations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.strategy_simulations_id_seq OWNER TO microtrader;

--
-- Name: strategy_simulations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.strategy_simulations_id_seq OWNED BY public.strategy_simulations.id;


--
-- Name: trades; Type: TABLE; Schema: public; Owner: microtrader
--

CREATE TABLE public.trades (
    id integer NOT NULL,
    asset_id integer NOT NULL,
    mode public.trademode NOT NULL,
    execution_target character varying(16) NOT NULL,
    side public.tradeside NOT NULL,
    status public.tradestatus NOT NULL,
    notional_eur double precision NOT NULL,
    quantity double precision NOT NULL,
    price double precision NOT NULL,
    reason text NOT NULL,
    executed_at timestamp without time zone NOT NULL
);


ALTER TABLE public.trades OWNER TO microtrader;

--
-- Name: trades_id_seq; Type: SEQUENCE; Schema: public; Owner: microtrader
--

CREATE SEQUENCE public.trades_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.trades_id_seq OWNER TO microtrader;

--
-- Name: trades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: microtrader
--

ALTER SEQUENCE public.trades_id_seq OWNED BY public.trades.id;


--
-- Name: assets id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.assets ALTER COLUMN id SET DEFAULT nextval('public.assets_id_seq'::regclass);


--
-- Name: engine_runs id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.engine_runs ALTER COLUMN id SET DEFAULT nextval('public.engine_runs_id_seq'::regclass);


--
-- Name: execution_intents id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.execution_intents ALTER COLUMN id SET DEFAULT nextval('public.execution_intents_id_seq'::regclass);


--
-- Name: market_ticks id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.market_ticks ALTER COLUMN id SET DEFAULT nextval('public.market_ticks_id_seq'::regclass);


--
-- Name: news_items id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.news_items ALTER COLUMN id SET DEFAULT nextval('public.news_items_id_seq'::regclass);


--
-- Name: positions id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.positions ALTER COLUMN id SET DEFAULT nextval('public.positions_id_seq'::regclass);


--
-- Name: provider_health_samples id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.provider_health_samples ALTER COLUMN id SET DEFAULT nextval('public.provider_health_samples_id_seq'::regclass);


--
-- Name: reconciliation_snapshots id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.reconciliation_snapshots ALTER COLUMN id SET DEFAULT nextval('public.reconciliation_snapshots_id_seq'::regclass);


--
-- Name: signal_outcome_snapshots id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.signal_outcome_snapshots ALTER COLUMN id SET DEFAULT nextval('public.signal_outcome_snapshots_id_seq'::regclass);


--
-- Name: signals id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.signals ALTER COLUMN id SET DEFAULT nextval('public.signals_id_seq'::regclass);


--
-- Name: simulation_alerts id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.simulation_alerts ALTER COLUMN id SET DEFAULT nextval('public.simulation_alerts_id_seq'::regclass);


--
-- Name: state_events id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.state_events ALTER COLUMN id SET DEFAULT nextval('public.state_events_id_seq'::regclass);


--
-- Name: strategy_simulations id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.strategy_simulations ALTER COLUMN id SET DEFAULT nextval('public.strategy_simulations_id_seq'::regclass);


--
-- Name: trades id; Type: DEFAULT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.trades ALTER COLUMN id SET DEFAULT nextval('public.trades_id_seq'::regclass);


--
-- Data for Name: assets; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.assets (id, symbol, name, kind, external_id, is_active, created_at) FROM stdin;
1	BTC	Bitcoin	CRYPTO	bitcoin	t	2026-06-12 07:31:00.496658
2	ETH	Ethereum	CRYPTO	ethereum	t	2026-06-12 07:31:00.498962
3	SOL	Solana	CRYPTO	solana	t	2026-06-12 07:31:00.50048
4	LINK	Chainlink	CRYPTO	chainlink	t	2026-06-12 07:31:00.501885
5	SPY	SPDR S&P 500 ETF Trust	ETF	SPY	t	2026-06-12 07:31:00.503327
6	QQQ	Invesco QQQ Trust	ETF	QQQ	t	2026-06-12 07:31:00.504847
7	VTI	Vanguard Total Stock Market ETF	ETF	VTI	t	2026-06-12 07:31:00.506413
8	AAPL	Apple Inc.	STOCK	AAPL	t	2026-06-12 07:31:00.507659
9	MSFT	Microsoft Corporation	STOCK	MSFT	t	2026-06-12 07:31:00.508909
10	NVDA	NVIDIA Corporation	STOCK	NVDA	t	2026-06-12 07:31:00.510107
\.


--
-- Data for Name: engine_runs; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.engine_runs (id, status, assets_count, news_items_count, signals_count, message, started_at, completed_at) FROM stdin;
1	ok	10	175	10	Engine cycle completed successfully. News ingested 96, rescored 79.	2026-06-12 07:31:00.511016	2026-06-12 07:31:06.815136
2	ok	10	86	10	Engine cycle completed successfully. News ingested 4, rescored 82.	2026-06-12 07:33:19.146882	2026-06-12 07:33:25.044763
3	ok	10	86	10	Engine cycle completed successfully. News ingested 2, rescored 84.	2026-06-12 07:38:25.059992	2026-06-12 07:38:30.921636
4	ok	10	90	10	Engine cycle completed successfully. News ingested 3, rescored 87.	2026-06-12 07:43:30.931464	2026-06-12 07:43:36.98778
\.


--
-- Data for Name: execution_intents; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.execution_intents (id, intent_key, asset_id, signal_id, position_id, mode, execution_target, side, status, source, notional_eur, price_hint, quantity, reason, broker_provider, broker_order_id, broker_status, error_message, created_at, updated_at) FROM stdin;
1	signal:5:market-closed	5	5	\N	paper	internal	BUY	SKIPPED	engine	0	738.15	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:31:05.814362	2026-06-12 07:31:05.816219
2	signal:6:market-closed	6	6	\N	paper	internal	BUY	SKIPPED	engine	0	715.46	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:31:05.821723	2026-06-12 07:31:05.822458
3	signal:7:market-closed	7	7	\N	paper	internal	BUY	SKIPPED	engine	0	364.5	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:31:05.825493	2026-06-12 07:31:05.826229
4	signal:8:market-closed	8	8	\N	paper	internal	BUY	SKIPPED	engine	0	295.56	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:31:05.829365	2026-06-12 07:31:05.830009
5	signal:9:market-closed	9	9	\N	paper	internal	BUY	SKIPPED	engine	0	391.47	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:31:05.832898	2026-06-12 07:31:05.833493
6	signal:10:market-closed	10	10	\N	paper	internal	BUY	SKIPPED	engine	0	204.86	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:31:05.836654	2026-06-12 07:31:05.837455
7	signal:15:market-closed	5	15	\N	paper	internal	BUY	SKIPPED	engine	0	738.15	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:33:24.032396	2026-06-12 07:33:24.03421
8	signal:16:market-closed	6	16	\N	paper	internal	BUY	SKIPPED	engine	0	715.46	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:33:24.040429	2026-06-12 07:33:24.04112
9	signal:17:market-closed	7	17	\N	paper	internal	BUY	SKIPPED	engine	0	364.5	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:33:24.044028	2026-06-12 07:33:24.044671
10	signal:18:market-closed	8	18	\N	paper	internal	BUY	SKIPPED	engine	0	295.56	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:33:24.047593	2026-06-12 07:33:24.048213
11	signal:19:market-closed	9	19	\N	paper	internal	BUY	SKIPPED	engine	0	391.47	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:33:24.051013	2026-06-12 07:33:24.051587
12	signal:20:market-closed	10	20	\N	paper	internal	BUY	SKIPPED	engine	0	204.86	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:33:24.054488	2026-06-12 07:33:24.055224
13	signal:25:market-closed	5	25	\N	paper	internal	BUY	SKIPPED	engine	0	738.15	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:38:29.942378	2026-06-12 07:38:29.943007
14	signal:26:market-closed	6	26	\N	paper	internal	BUY	SKIPPED	engine	0	715.46	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:38:29.945774	2026-06-12 07:38:29.946331
15	signal:27:market-closed	7	27	\N	paper	internal	BUY	SKIPPED	engine	0	364.5	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:38:29.948978	2026-06-12 07:38:29.949497
16	signal:28:market-closed	8	28	\N	paper	internal	BUY	SKIPPED	engine	0	295.56	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:38:29.952178	2026-06-12 07:38:29.95276
17	signal:29:market-closed	9	29	\N	paper	internal	BUY	SKIPPED	engine	0	391.47	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:38:29.955433	2026-06-12 07:38:29.955969
18	signal:30:market-closed	10	30	\N	paper	internal	BUY	SKIPPED	engine	0	204.86	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:38:29.958737	2026-06-12 07:38:29.959238
19	signal:35:market-closed	5	35	\N	paper	internal	BUY	SKIPPED	engine	0	738.15	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:43:36.010994	2026-06-12 07:43:36.011625
20	signal:36:market-closed	6	36	\N	paper	internal	BUY	SKIPPED	engine	0	715.46	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:43:36.01424	2026-06-12 07:43:36.014708
21	signal:37:market-closed	7	37	\N	paper	internal	BUY	SKIPPED	engine	0	364.5	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:43:36.01733	2026-06-12 07:43:36.017787
22	signal:38:market-closed	8	38	\N	paper	internal	BUY	SKIPPED	engine	0	295.56	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:43:36.020291	2026-06-12 07:43:36.020747
23	signal:39:market-closed	9	39	\N	paper	internal	BUY	SKIPPED	engine	0	391.47	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:43:36.02329	2026-06-12 07:43:36.023749
24	signal:40:market-closed	10	40	\N	paper	internal	BUY	SKIPPED	engine	0	204.86	\N	Skipped because the US market session is closed.	alpaca	\N	\N	Skipped because the US market session is closed.	2026-06-12 07:43:36.026339	2026-06-12 07:43:36.026945
\.


--
-- Data for Name: market_ticks; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.market_ticks (id, asset_id, price, change_24h_pct, volume_24h, source, captured_at) FROM stdin;
1	1	54473.6	0.316	19958682.6932156	binance	2026-06-12 07:31:01.602745
2	2	1433.84	0.063	9225943.363726	binance	2026-06-12 07:31:01.60275
3	3	57.31	1.776	2296218.23874	binance	2026-06-12 07:31:01.602752
4	4	6.737	0.178	141173.86688	binance	2026-06-12 07:31:01.602753
5	5	738.15	1.7324	3118813	alpaca	2026-06-12 07:31:01.919584
6	6	715.46	3.1368	1102245	alpaca	2026-06-12 07:31:01.919588
7	7	364.5	1.8356	105995	alpaca	2026-06-12 07:31:01.919589
8	8	295.56	1.3998	1372585	alpaca	2026-06-12 07:31:01.919591
9	9	391.47	-1.4947	1282778	alpaca	2026-06-12 07:31:01.919592
10	10	204.86	2.2204	5648208	alpaca	2026-06-12 07:31:01.919594
11	1	54443.8	0.277	19956859.1831913	binance	2026-06-12 07:33:20.252556
12	2	1433.03	0.078	9232535.646338	binance	2026-06-12 07:33:20.25256
13	3	57.25	1.705	2297550.7771	binance	2026-06-12 07:33:20.252562
14	4	6.742	0.253	141179.05822	binance	2026-06-12 07:33:20.252564
15	5	738.15	1.7324	3118813	alpaca	2026-06-12 07:33:20.561079
16	6	715.46	3.1368	1102245	alpaca	2026-06-12 07:33:20.561083
17	7	364.5	1.8356	105995	alpaca	2026-06-12 07:33:20.561085
18	8	295.56	1.3998	1372585	alpaca	2026-06-12 07:33:20.561087
19	9	391.47	-1.4947	1282778	alpaca	2026-06-12 07:33:20.561088
20	10	204.86	2.2204	5648208	alpaca	2026-06-12 07:33:20.561089
21	1	54430.48	0.376	20018382.9428409	binance	2026-06-12 07:38:26.115326
22	2	1434.88	0.312	9238576.976537	binance	2026-06-12 07:38:26.11533
23	3	57.26	1.995	2289018.62689	binance	2026-06-12 07:38:26.115332
24	4	6.739	0.417	141192.13581	binance	2026-06-12 07:38:26.115333
25	5	738.15	1.7324	3118813	alpaca	2026-06-12 07:38:26.416438
26	6	715.46	3.1368	1102245	alpaca	2026-06-12 07:38:26.416443
27	7	364.5	1.8356	105995	alpaca	2026-06-12 07:38:26.416444
28	8	295.56	1.3998	1372585	alpaca	2026-06-12 07:38:26.416446
29	9	391.47	-1.4947	1282778	alpaca	2026-06-12 07:38:26.416447
30	10	204.86	2.2204	5648208	alpaca	2026-06-12 07:38:26.416448
31	1	54495.95	0.472	20045774.4982813	binance	2026-06-12 07:43:31.972756
32	2	1434.98	0.309	9245029.578411	binance	2026-06-12 07:43:31.97276
33	3	57.28	2.012	2293426.23293	binance	2026-06-12 07:43:31.972762
34	4	6.745	0.327	141229.09658	binance	2026-06-12 07:43:31.972763
35	5	738.15	1.7324	3118813	alpaca	2026-06-12 07:43:32.269296
36	6	715.46	3.1368	1102245	alpaca	2026-06-12 07:43:32.2693
37	7	364.5	1.8356	105995	alpaca	2026-06-12 07:43:32.269302
38	8	295.56	1.3998	1372585	alpaca	2026-06-12 07:43:32.269304
39	9	391.47	-1.4947	1282778	alpaca	2026-06-12 07:43:32.269305
40	10	204.86	2.2204	5648208	alpaca	2026-06-12 07:43:32.269307
\.


--
-- Data for Name: news_items; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.news_items (id, asset_id, source, title, summary, url, sentiment_score, event_type, published_at, ingested_at) FROM stdin;
1	1	CoinDesk: Bitcoin, Ethereum, Crypto News and Price Data	Live updates: Bitcoin holds above $63,000, Japan set to hike rates to 31-year high		https://www.coindesk.com/tech/2026/06/12/live-updates-bitcoin-in-volatile-trading-above-usd63-000-doge-unchanged	0	general	2026-06-12 06:32:02	2026-06-12 07:31:02.296276
2	1	CoinDesk: Bitcoin, Ethereum, Crypto News and Price Data	Bitcoin climbs back into the green as Trump signals an end to the Iran war		https://www.coindesk.com/markets/2026/06/12/bitcoin-climbs-back-into-the-green-as-trump-signals-an-end-to-the-iran-war	0	general	2026-06-12 05:14:33	2026-06-12 07:31:02.30094
3	3	CoinDesk: Bitcoin, Ethereum, Crypto News and Price Data	SpaceX stock is coming to Solana on the same day it lists on Nasdaq		https://www.coindesk.com/tech/2026/06/10/spacex-stock-is-coming-to-solana-on-the-same-day-it-lists-on-nasdaq	0	general	2026-06-11 14:00:00	2026-06-12 07:31:02.305962
4	1	CoinDesk: Bitcoin, Ethereum, Crypto News and Price Data	It's not SpaceX. Bitcoin ETF outflows may be an arbitrage story		https://www.coindesk.com/markets/2026/06/11/bitcoin-etf-outflows-may-be-more-about-arbitrage-unwinds-than-spacex-fomo	0	etf	2026-06-11 12:42:19	2026-06-12 07:31:02.31134
5	1	CoinDesk: Bitcoin, Ethereum, Crypto News and Price Data	Michael Saylor and Jack Mallers go toe-to-toe over Strategy's bitcoin reporting metrics		https://www.coindesk.com/markets/2026/06/11/michael-saylor-and-jack-mallers-go-toe-to-toe-over-strategy-s-bitcoin-reporting-metrics	0	general	2026-06-11 11:52:57	2026-06-12 07:31:02.313185
6	1	Cointelegraph.com News	Big Tech crash, oil volatility rattles markets: Will Bitcoin hold above $60K?	<p style="float: right; margin: 0 0 10px 15px; width: 240px;"><img alt="Big Tech crash, oil volatility rattles markets: Will Bitcoin hold above $60K?" class="type:primaryImage" src="https://images.cointelegraph.com/images/528_aHR0cHM6Ly9zMy1pbWFnZXMuY3RtZWRpYS5pby9tZWRpYS9hcnRpY2xlLWNvdmVycy9hcnRpY2xlLWNvdmVycy02OTM0Mi1iaXRjb2luLW1heS1oYXZlLXBsYXllZC1hLXJvbGUtaW4tdGVzbGEtcy1kZWNvcnJlbGF0aW9uLWZyb20tYmlnLXRlY2guanBn.jpg" /></p><p>With $1.9 billion exiting the spot Bitcoin ETFs and tech stocks under pressure, BTC is failing as a hedge and at risk of falling below the $60,000 support.</p>	https://cointelegraph.com/markets/big-tech-crash-oil-volatility-rattles-markets-will-bitcoin-hold-above-60k?utm_source=rss_feed&utm_medium=rss&utm_campaign=rss_partner_inbound	-0.13333333333333333	etf	2026-06-11 22:58:52	2026-06-12 07:31:02.396185
7	2	Cointelegraph.com News	ETH futures traders lean into $1.6K range lows: Will Ether lead market recovery?	<p style="float: right; margin: 0 0 10px 15px; width: 240px;"><img alt="ETH futures traders lean into $1.6K range lows: Will Ether lead market recovery?" class="type:primaryImage" src="https://images.cointelegraph.com/images/528_aHR0cHM6Ly9zMy1pbWFnZXMuY3RtZWRpYS5pby9tZWRpYS9hcnRpY2xlLWNvdmVycy9hcnRpY2xlLWNvdmVycy0xOTg4MjAtbGV2ZXJhZ2VkLWJlYXJzLXByZXNzdXJlLWJpdGNvaW4td2hpbGUtYnVsbHMtYXR0ZW1wdC1ldGhlcmV1bS1yYWxseS5qcGc=.jpg" /></p><p>ETH traders increased their long positions as Ether price traded near 2026 lows. Will ETH’s rebound eclipse the BTC recovery? </p>	https://cointelegraph.com/markets/ether-bulls-ramp-up-risk-above-16k-can-buyers-regain-control?utm_source=rss_feed&utm_medium=rss&utm_campaign=rss_partner_inbound	0.16666666666666666	general	2026-06-11 19:37:41	2026-06-12 07:31:02.398528
8	1	Cointelegraph.com News	Bitcoin tags $63.2K as BTC price action ignores inflation, Iran Hormuz closure	<p style="float: right; margin: 0 0 10px 15px; width: 240px;"><img alt="Bitcoin tags $63.2K as BTC price action ignores inflation, Iran Hormuz closure" class="type:primaryImage" src="https://images.cointelegraph.com/images/528_aHR0cHM6Ly9zMy1pbWFnZXMuY3RtZWRpYS5pby9tZWRpYS9hcnRpY2xlLWNvdmVycy9iYXNrZXRiYWxsLXByaWNlLWdyZWVuLWdyb3ctanVtcC1jcnlwdG8tYml0Y29pbi5qcGc=.jpg" /></p><p>Bitcoin mostly preserved a recent rebound despite the highest US PPI inflation since October 2022 and Iran closing the Strait of Hormuz oil route.</p>	https://cointelegraph.com/markets/bitcoin-tags-632k-as-btc-price-action-ignores-new-iran-hormuz-closure?utm_source=rss_feed&utm_medium=rss&utm_campaign=rss_partner_inbound	0.16666666666666666	general	2026-06-11 13:41:47	2026-06-12 07:31:02.402394
9	2	Cointelegraph.com News	Audiera’s AI token BEAT beats Bitcoin, Ethereum as price surges 1,500% in a month	<p style="float: right; margin: 0 0 10px 15px; width: 240px;"><img alt="Audiera’s AI token BEAT beats Bitcoin, Ethereum as price surges 1,500% in a month" class="type:primaryImage" src="https://images.cointelegraph.com/images/528_aHR0cHM6Ly9zMy1pbWFnZXMuY3RtZWRpYS5pby9tZWRpYS9hcnRpY2xlLWNvdmVycy9wbGFuZS1wcmljZS5qcGc=.jpg" /></p><p>BEAT has reached its most overbought readings on record, raising the odds of a 35% price decline in the coming days.</p>	https://cointelegraph.com/markets/audieras-ai-token-beat-beats-bitcoin-ethereum-as-price-surges-1500-in-a-month?utm_source=rss_feed&utm_medium=rss&utm_campaign=rss_partner_inbound	0.9066666666666668	general	2026-06-11 12:08:03	2026-06-12 07:31:02.405581
10	1	Cointelegraph.com News	TradFi advisers want stablecoins, tokenization over Bitcoin: Bitwise	<p style="float: right; margin: 0 0 10px 15px; width: 240px;"><img alt="TradFi advisers want stablecoins, tokenization over Bitcoin: Bitwise" class="type:primaryImage" src="https://images.cointelegraph.com/images/528_aHR0cHM6Ly9zMy1pbWFnZXMuY3RtZWRpYS5pby9tZWRpYS9hcnRpY2xlLWNvdmVycy9oaS1iaXRjb2luLWlzLWl0LWdvbGQtbW9uZXktb3Itc29tZXRoaW5nLWVsc2UzLmpwZw==.jpg" /></p><p>Bitwise’s Matt Hougan says it was “pretty hard to engage with advisers on Bitcoin” during recent discussions, who are more interested in stablecoins and tokenization.</p>	https://cointelegraph.com/news/tradfi-advisors-want-stablecoins-tokenization-over-bitcoin-bitwise?utm_source=rss_feed&utm_medium=rss&utm_campaign=rss_partner_inbound	0	general	2026-06-11 07:01:31	2026-06-12 07:31:02.40761
11	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Spy law on track to lapse after Congress rejects extension - Politico	<a href="https://news.google.com/rss/articles/CBMiqAFBVV95cUxOd3M0Z015Qlpsa2NlQU5HZDVQR2R3TDhMMS11bFF0eWM3OFlDSjFKX29wdl9yeFEyWHpMQ1Y4aWk3ZE9YQTFQb084SExyaHBwWXQzY19KanpyWW9pcjM1YXV5WGljc1pyYlB2YmFrckdtSlczZEY5RTdub21JOHpFdzNLeGVTRThTelZVb05sbVZTNlNnQk1vZm1Wc3JfVlpESXZBUjZOb0I?oc=5" target="_blank">Spy law on track to lapse after Congress rejects extension</a>&nbsp;&nbsp;<font color="#6f6f6f">Politico</font>	https://news.google.com/rss/articles/CBMiqAFBVV95cUxOd3M0Z015Qlpsa2NlQU5HZDVQR2R3TDhMMS11bFF0eWM3OFlDSjFKX29wdl9yeFEyWHpMQ1Y4aWk3ZE9YQTFQb084SExyaHBwWXQzY19KanpyWW9pcjM1YXV5WGljc1pyYlB2YmFrckdtSlczZEY5RTdub21JOHpFdzNLeGVTRThTelZVb05sbVZTNlNnQk1vZm1Wc3JfVlpESXZBUjZOb0I?oc=5	0	general	2026-06-11 19:53:35	2026-06-12 07:31:02.902642
12	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Jay Clayton: Trump names new spy chief after Pulte pushback - BBC	<a href="https://news.google.com/rss/articles/CBMiWkFVX3lxTE1mOGdaVU9Pdkg5ZVFDRjdVSENvOEs0SDNocU1PTWZwaFlEdU11ODI5OHE1Rk53RFdjbHZBNlF0aVJkS2JvLVE0WmVrYVZwY1VxR0tPaEVhSTdnQQ?oc=5" target="_blank">Jay Clayton: Trump names new spy chief after Pulte pushback</a>&nbsp;&nbsp;<font color="#6f6f6f">BBC</font>	https://news.google.com/rss/articles/CBMiWkFVX3lxTE1mOGdaVU9Pdkg5ZVFDRjdVSENvOEs0SDNocU1PTWZwaFlEdU11ODI5OHE1Rk53RFdjbHZBNlF0aVJkS2JvLVE0WmVrYVZwY1VxR0tPaEVhSTdnQQ?oc=5	0	general	2026-06-11 20:56:44	2026-06-12 07:31:02.904718
13	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Controversial spy program set to expire : Here & Now Anytime - NPR	<a href="https://news.google.com/rss/articles/CBMijAFBVV95cUxQems2LWJtcnBtOFhFMkhzeUNrWkZsYl9yZDRwOEN6MDQ0SzRmR0VpTkliUURpaFlwV2tXTUdabWJ0VlVsMnJDandoS0xJM093WlZyYXVCcG5rbF9KWkhnRUpxWXVkVkNYdTlILXNEQ1lqd2pSRXJKZ0JlOHNsN2locUJQMlI5RVRtbXVRaA?oc=5" target="_blank">Controversial spy program set to expire : Here & Now Anytime</a>&nbsp;&nbsp;<font color="#6f6f6f">NPR</font>	https://news.google.com/rss/articles/CBMijAFBVV95cUxQems2LWJtcnBtOFhFMkhzeUNrWkZsYl9yZDRwOEN6MDQ0SzRmR0VpTkliUURpaFlwV2tXTUdabWJ0VlVsMnJDandoS0xJM093WlZyYXVCcG5rbF9KWkhnRUpxWXVkVkNYdTlILXNEQ1lqd2pSRXJKZ0JlOHNsN2locUJQMlI5RVRtbXVRaA?oc=5	0	general	2026-06-11 19:59:58	2026-06-12 07:31:02.906088
14	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	FISA spy powers are almost certain to expire after Congress fails to act - AP News	<a href="https://news.google.com/rss/articles/CBMipAFBVV95cUxNWU42SkhpX2dDV2hOc0FIY0c0M0tqME5YN3U5ZFV2aWV4VXFXcEpuNWQ3MEt2OGd0aUhOS3U4MWYxdUxmMFYtWDBJNExxbl9leDd0NEVTLUFJWGZPSC1UQ2M1SXJwbDVxbkVPTzJCaTZLWkd3ZjhMb2ZJLVotUk56WV9GdVdzWGhhS0lvcVNGOVUzWlU3OW9MMU5UYjdrSi1fUWpBcw?oc=5" target="_blank">FISA spy powers are almost certain to expire after Congress fails to act</a>&nbsp;&nbsp;<font color="#6f6f6f">AP News</font>	https://news.google.com/rss/articles/CBMipAFBVV95cUxNWU42SkhpX2dDV2hOc0FIY0c0M0tqME5YN3U5ZFV2aWV4VXFXcEpuNWQ3MEt2OGd0aUhOS3U4MWYxdUxmMFYtWDBJNExxbl9leDd0NEVTLUFJWGZPSC1UQ2M1SXJwbDVxbkVPTzJCaTZLWkd3ZjhMb2ZJLVotUk56WV9GdVdzWGhhS0lvcVNGOVUzWlU3OW9MMU5UYjdrSi1fUWpBcw?oc=5	0	general	2026-06-11 23:01:00	2026-06-12 07:31:02.907559
15	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Still see a bullish trading cycle for the S&P 500 equal weight, says Jessica Inskip - CNBC	<a href="https://news.google.com/rss/articles/CBMiwgFBVV95cUxPeFBPRXlvYW1SZW9TZTdVNVpEam8wVGVQdXVHQUFtTW9rdUFMQUd5QW1PZ2FiRVQ0M1FLbEpDOFNpVV8wZU1BWGxXRUtCMHllTjlOZzNjUmVDSEhDNHJycVlCU1BMaGFRWGc0b1BCWWtIa0JwcmExMGtTOUQ0SHVVMkcyc1FQTDNnbTNQLW9EUy1iemd4a3dKVlJ5dHlGSG5kWHkyRlNhbTY5X3Y4U2N0V2RneTVnVEZrbTl4a1ZKZi1oZw?oc=5" target="_blank">Still see a bullish trading cycle for the S&amp;P 500 equal weight, says Jessica Inskip</a>&nbsp;&nbsp;<font color="#6f6f6f">CNBC</font>	https://news.google.com/rss/articles/CBMiwgFBVV95cUxPeFBPRXlvYW1SZW9TZTdVNVpEam8wVGVQdXVHQUFtTW9rdUFMQUd5QW1PZ2FiRVQ0M1FLbEpDOFNpVV8wZU1BWGxXRUtCMHllTjlOZzNjUmVDSEhDNHJycVlCU1BMaGFRWGc0b1BCWWtIa0JwcmExMGtTOUQ0SHVVMkcyc1FQTDNnbTNQLW9EUy1iemd4a3dKVlJ5dHlGSG5kWHkyRlNhbTY5X3Y4U2N0V2RneTVnVEZrbTl4a1ZKZi1oZw?oc=5	0.48000000000000004	general	2026-06-11 23:30:45	2026-06-12 07:31:02.908832
16	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Key U.S. spy powers act set to expire - WAVE News	<a href="https://news.google.com/rss/articles/CBMidEFVX3lxTFBNNC1qVkdheWZjLTR0bjdDbWwtUjdIT2hpenpueFNPQllIUmhXUmoxMnN2YWFmdlcwYU5SZTIzSlBqU0pRWTJVNmUwSlJwV1l3ekl1OVRlaURqVk5UQWdyTV9nR1Jzc2E0RHpTSWVxb0RMdEp50gGIAUFVX3lxTE9tS1RsaC1kNDQweU5JWUR1SkFuMW9TRElMLVlFVWZMOWpzUXhMU1Fxazd1Q04zTjVXZm9adEg3SVNUQ3MtYWpYX0o3Z0JtVHBiYmpMTk92SDhQUTUxQXNHMjF2UVh3U0p0TW1lU2pFU0tkODhJWW1wYXFNVjUzaW1nT2hFYWo5NWo?oc=5" target="_blank">Key U.S. spy powers act set to expire</a>&nbsp;&nbsp;<font color="#6f6f6f">WAVE News</font>	https://news.google.com/rss/articles/CBMidEFVX3lxTFBNNC1qVkdheWZjLTR0bjdDbWwtUjdIT2hpenpueFNPQllIUmhXUmoxMnN2YWFmdlcwYU5SZTIzSlBqU0pRWTJVNmUwSlJwV1l3ekl1OVRlaURqVk5UQWdyTV9nR1Jzc2E0RHpTSWVxb0RMdEp50gGIAUFVX3lxTE9tS1RsaC1kNDQweU5JWUR1SkFuMW9TRElMLVlFVWZMOWpzUXhMU1Fxazd1Q04zTjVXZm9adEg3SVNUQ3MtYWpYX0o3Z0JtVHBiYmpMTk92SDhQUTUxQXNHMjF2UVh3U0p0TW1lU2pFU0tkODhJWW1wYXFNVjUzaW1nT2hFYWo5NWo?oc=5	0	general	2026-06-11 21:56:00	2026-06-12 07:31:02.910106
17	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Johnson’s FISA extension fails spectacularly as spy powers poised to expire - Courthouse News	<a href="https://news.google.com/rss/articles/CBMiqgFBVV95cUxOaVlBbVlPWU1wQ0w1ZDEtcFlWdkpvVWlWdU56aVhtZVlEdHZSRW5HLUhMc0N5M09yeG5LVWtoc29WM0NkWkpCcTQ3eGpMY25qc1d5bU0zU3lOd25MZHRQSkhUempjODhGVjdUeDU1TVhQWHdZdmh1UmdWaDA4cHBRX2JtV1FPUUJ4R2JJNDFvZG9vRlJhYU42Wm1kNEt0ZmlURWRpUngzZGZQUQ?oc=5" target="_blank">Johnson’s FISA extension fails spectacularly as spy powers poised to expire</a>&nbsp;&nbsp;<font color="#6f6f6f">Courthouse News</font>	https://news.google.com/rss/articles/CBMiqgFBVV95cUxOaVlBbVlPWU1wQ0w1ZDEtcFlWdkpvVWlWdU56aVhtZVlEdHZSRW5HLUhMc0N5M09yeG5LVWtoc29WM0NkWkpCcTQ3eGpMY25qc1d5bU0zU3lOd25MZHRQSkhUempjODhGVjdUeDU1TVhQWHdZdmh1UmdWaDA4cHBRX2JtV1FPUUJ4R2JJNDFvZG9vRlJhYU42Wm1kNEt0ZmlURWRpUngzZGZQUQ?oc=5	0	general	2026-06-11 16:15:48	2026-06-12 07:31:02.911359
18	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	US Supreme Court overturns ex-Twitter employee's obstruction conviction in Saudi spy case - Reuters	<a href="https://news.google.com/rss/articles/CBMizgFBVV95cUxQeHBRb01FbkY4WXdfVDJDRGpFWEt1Z051QlpkbkFlTkxOamZnYWRYT1Q3MVJJQVZ4WnJSYlpTU0hZNTZKRk8zT0Z0NzFXUzk5V1psYXlSZFh4dHo4WHdkRmVzeEZLNVZmRVJkSm1NUDNOYzZxWUQwWTA1c2NkS2VfeHVqdnA0OHVMSThEMU9QRnpKRFdqZzRvVWEyUkFPSW1PY3FxcEtPbEJkLU03UllzOF84b1pKdUpuekk1Y1d3anJnbktqVXIxZmhrS0p4dw?oc=5" target="_blank">US Supreme Court overturns ex-Twitter employee's obstruction conviction in Saudi spy case</a>&nbsp;&nbsp;<font color="#6f6f6f">Reuters</font>	https://news.google.com/rss/articles/CBMizgFBVV95cUxQeHBRb01FbkY4WXdfVDJDRGpFWEt1Z051QlpkbkFlTkxOamZnYWRYT1Q3MVJJQVZ4WnJSYlpTU0hZNTZKRk8zT0Z0NzFXUzk5V1psYXlSZFh4dHo4WHdkRmVzeEZLNVZmRVJkSm1NUDNOYzZxWUQwWTA1c2NkS2VfeHVqdnA0OHVMSThEMU9QRnpKRFdqZzRvVWEyUkFPSW1PY3FxcEtPbEJkLU03UllzOF84b1pKdUpuekk1Y1d3anJnbktqVXIxZmhrS0p4dw?oc=5	0	general	2026-06-11 23:06:16	2026-06-12 07:31:02.912621
19	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	House vote puts Section 702 on brink of historic lapse amid fight over acting spy chief - Nextgov/FCW	<a href="https://news.google.com/rss/articles/CBMixwFBVV95cUxPVGRaWU9XRlhiNExVMk5DMDdYc3pvNWVYVi1FSHZBbUdQWEdYaUhFdzFZbDFuZmlJX2dGbkpNbENPM084b1lzdGxZSTg1T2tqUGtIMVRtd3JlaGhBQ1YwZ2JlVzlldE1CTmVVc1dJNjFPTm96b2dxRHZod0dSc1R5dVFaWDZPWVlyMW1Xd2lLLTdTTlJlQllHSnVEbVduY0sxMnlPVjVDelFabi1rZkZMUEE4MnFfSjZvSks4bU9CblVaTTd1WEVV?oc=5" target="_blank">House vote puts Section 702 on brink of historic lapse amid fight over acting spy chief</a>&nbsp;&nbsp;<font color="#6f6f6f">Nextgov/FCW</font>	https://news.google.com/rss/articles/CBMixwFBVV95cUxPVGRaWU9XRlhiNExVMk5DMDdYc3pvNWVYVi1FSHZBbUdQWEdYaUhFdzFZbDFuZmlJX2dGbkpNbENPM084b1lzdGxZSTg1T2tqUGtIMVRtd3JlaGhBQ1YwZ2JlVzlldE1CTmVVc1dJNjFPTm96b2dxRHZod0dSc1R5dVFaWDZPWVlyMW1Xd2lLLTdTTlJlQllHSnVEbVduY0sxMnlPVjVDelFabi1rZkZMUEE4MnFfSjZvSks4bU9CblVaTTd1WEVV?oc=5	0	general	2026-06-11 21:16:00	2026-06-12 07:31:02.913867
20	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Key U.S. spy powers act set to expire - WAFB	<a href="https://news.google.com/rss/articles/CBMie0FVX3lxTE9xYUxid0NJXzZtcHFGVDIwS2x4OERXUUwtY29SNU9KVk5kQWFkWE9kamQ0YXo2UHhITEtKMW82bURJOHQzS0ZueEE4LXdvTEtkNGFYRDZ6RGxpTncwVUg1TDRTT3RITUdsbmk2c19YTXZFbm0zdExjejZLUQ?oc=5" target="_blank">Key U.S. spy powers act set to expire</a>&nbsp;&nbsp;<font color="#6f6f6f">WAFB</font>	https://news.google.com/rss/articles/CBMie0FVX3lxTE9xYUxid0NJXzZtcHFGVDIwS2x4OERXUUwtY29SNU9KVk5kQWFkWE9kamQ0YXo2UHhITEtKMW82bURJOHQzS0ZueEE4LXdvTEtkNGFYRDZ6RGxpTncwVUg1TDRTT3RITUdsbmk2c19YTXZFbm0zdExjejZLUQ?oc=5	0	general	2026-06-11 21:51:00	2026-06-12 07:31:02.915162
21	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Trump (still) has a spy chief problem - vox.com	<a href="https://news.google.com/rss/articles/CBMitAFBVV95cUxPNFpyanY1bDE3djE2Vk1iTFZGWUhUNGdOekhFWTBLaDBUZjZNbW5EMlFkSlV1bmJrbUZRdllIb1dZYXBSM2ZjVS0xYXktTUFXQ296ZlhDb1h4Y2R5TFgzdDU5aWVYR3BteW8xUXVKdDlJMkZadkVETXJ0ZENELUVoYjFGQkotUmF4cXZTb2pSVGlpV1JVRnpfZWVnMWZ1cXh5SkFlRXc1ZUJDVERSODFIZURHTmE?oc=5" target="_blank">Trump (still) has a spy chief problem</a>&nbsp;&nbsp;<font color="#6f6f6f">vox.com</font>	https://news.google.com/rss/articles/CBMitAFBVV95cUxPNFpyanY1bDE3djE2Vk1iTFZGWUhUNGdOekhFWTBLaDBUZjZNbW5EMlFkSlV1bmJrbUZRdllIb1dZYXBSM2ZjVS0xYXktTUFXQ296ZlhDb1h4Y2R5TFgzdDU5aWVYR3BteW8xUXVKdDlJMkZadkVETXJ0ZENELUVoYjFGQkotUmF4cXZTb2pSVGlpV1JVRnpfZWVnMWZ1cXh5SkFlRXc1ZUJDVERSODFIZURHTmE?oc=5	0	general	2026-06-11 21:50:00	2026-06-12 07:31:02.916388
22	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Senate’s Latest Attempt to Renew Spy Power Tool Blocked on Floor - Bloomberg Government News	<a href="https://news.google.com/rss/articles/CBMisAFBVV95cUxQUlQtWlUwRWh1eHBmbG9zcHRqRXNSTHh3eWxnNUxjNVhDLWptTVd1SzlNSzd4dFBGbEtubDlIcDgwOGVQVWtPMXlBeG1wRHFkeTRCRWZpUFVuSFFYV19mLWc2d0NfVXp3eGJkQk5xTXRLUmpxTnhEMTZUNXJDd3hjS0NmLXE2MUFfR0JMaVVQSl9tcmlTanZBWTNkcUN4Wmx1SEFVSW04MldCc1VoaVQzcw?oc=5" target="_blank">Senate’s Latest Attempt to Renew Spy Power Tool Blocked on Floor</a>&nbsp;&nbsp;<font color="#6f6f6f">Bloomberg Government News</font>	https://news.google.com/rss/articles/CBMisAFBVV95cUxQUlQtWlUwRWh1eHBmbG9zcHRqRXNSTHh3eWxnNUxjNVhDLWptTVd1SzlNSzd4dFBGbEtubDlIcDgwOGVQVWtPMXlBeG1wRHFkeTRCRWZpUFVuSFFYV19mLWc2d0NfVXp3eGJkQk5xTXRLUmpxTnhEMTZUNXJDd3hjS0NmLXE2MUFfR0JMaVVQSl9tcmlTanZBWTNkcUN4Wmx1SEFVSW04MldCc1VoaVQzcw?oc=5	0	general	2026-06-11 17:35:00	2026-06-12 07:31:02.917713
23	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Spy program set to expire as Congress rejects FISA extension - THIRTEEN - New York Public Media	<a href="https://news.google.com/rss/articles/CBMiggFBVV95cUxNMFdYWklic1pqYTdMbU9naFVBUVd2MXN2dGV3VU5sV2pyUEJ3a3lPcElBNFZwY1FtQnlpeUp0VnUtalBDbld4WHQwaTkwaGJMUmtoTEdXM0pIZFJobWY2ZklfeDlHQ25uUkFKcmJ2TXVGTWJ5REJVdHRMNXcyWHlkZHh3?oc=5" target="_blank">Spy program set to expire as Congress rejects FISA extension</a>&nbsp;&nbsp;<font color="#6f6f6f">THIRTEEN - New York Public Media</font>	https://news.google.com/rss/articles/CBMiggFBVV95cUxNMFdYWklic1pqYTdMbU9naFVBUVd2MXN2dGV3VU5sV2pyUEJ3a3lPcElBNFZwY1FtQnlpeUp0VnUtalBDbld4WHQwaTkwaGJMUmtoTEdXM0pIZFJobWY2ZklfeDlHQ25uUkFKcmJ2TXVGTWJ5REJVdHRMNXcyWHlkZHh3?oc=5	0	general	2026-06-12 01:12:14	2026-06-12 07:31:02.918967
24	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Senate Democrats block short-term extensions of FISA 702 spy powers - The Hill	<a href="https://news.google.com/rss/articles/CBMihAFBVV95cUxNR0lGNmdBQjMxLTFXSVNPNVVpSGRibFFiQ094VWo3aThvOWdMQl8zdGt0UGEwMi1wOXBoenppWGhiaFlHV0RBbTRyUTZhY0ZYanJPSW1aanY5Nzh2UGgtZzN0aElKUUl4bXdObDNkRTRTV1QtV2lLM1lhS2pnMV9ZLU5CM2PSAYoBQVVfeXFMTkxHX1ZXZ3BEeGZZQVdzUEF5alp5ZG5sYk5LcnlvQ1dMNmd0eUQ0ekFFMkNxWERsZnY4NUwyQm8tYVFsc2xxSDVzX0RuajZQYTcxMkpiSFB3X0RnRGFYZG1vellKS3RHSXR4Y0IyeE4tYzA5V1g3YWs5YTdBbmxCRVJiZjhicTdDbUdn?oc=5" target="_blank">Senate Democrats block short-term extensions of FISA 702 spy powers</a>&nbsp;&nbsp;<font color="#6f6f6f">The Hill</font>	https://news.google.com/rss/articles/CBMihAFBVV95cUxNR0lGNmdBQjMxLTFXSVNPNVVpSGRibFFiQ094VWo3aThvOWdMQl8zdGt0UGEwMi1wOXBoenppWGhiaFlHV0RBbTRyUTZhY0ZYanJPSW1aanY5Nzh2UGgtZzN0aElKUUl4bXdObDNkRTRTV1QtV2lLM1lhS2pnMV9ZLU5CM2PSAYoBQVVfeXFMTkxHX1ZXZ3BEeGZZQVdzUEF5alp5ZG5sYk5LcnlvQ1dMNmd0eUQ0ekFFMkNxWERsZnY4NUwyQm8tYVFsc2xxSDVzX0RuajZQYTcxMkpiSFB3X0RnRGFYZG1vellKS3RHSXR4Y0IyeE4tYzA5V1g3YWs5YTdBbmxCRVJiZjhicTdDbUdn?oc=5	0	general	2026-06-11 18:10:00	2026-06-12 07:31:02.920248
25	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Opinion: S&P 500 indicators are breaking down — but this new buy signal is flashing green - MarketWatch	<a href="https://news.google.com/rss/articles/CBMiuwFBVV95cUxPdWhCblpEbnFORHVUTEdzQjJXUWJYaVRKSnhzbVJ3aTNhejFpRXNPem5vQ1NKT290RllYZHpPeFJEbzNhWHJlUXBRWWJ2dEdMY2s5dkVPZ2U0TGZ6V2lTQzRZVWlCOE1vMmN2TDVPcG5NVzFJRHF1R1ZyNE9KZzNDeFBwdjJOY01YX3VxRjQzdFdwZWVabWxJWXVrQ2V5TklRR2Zia3ZyYlUtRlY1NENrdXMxcEVWSm1ubHI4?oc=5" target="_blank">Opinion: S&amp;P 500 indicators are breaking down — but this new buy signal is flashing green</a>&nbsp;&nbsp;<font color="#6f6f6f">MarketWatch</font>	https://news.google.com/rss/articles/CBMiuwFBVV95cUxPdWhCblpEbnFORHVUTEdzQjJXUWJYaVRKSnhzbVJ3aTNhejFpRXNPem5vQ1NKT290RllYZHpPeFJEbzNhWHJlUXBRWWJ2dEdMY2s5dkVPZ2U0TGZ6V2lTQzRZVWlCOE1vMmN2TDVPcG5NVzFJRHF1R1ZyNE9KZzNDeFBwdjJOY01YX3VxRjQzdFdwZWVabWxJWXVrQ2V5TklRR2Zia3ZyYlUtRlY1NENrdXMxcEVWSm1ubHI4?oc=5	0	general	2026-06-11 18:03:00	2026-06-12 07:31:02.921531
26	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	S&P 500 rallies 1.7% for its biggest gain in 2 months on hopes for a US-Iran deal to get oil flowing again - KVUE	<a href="https://news.google.com/rss/articles/CBMiqAJBVV95cUxONjk5X0V0a0hLLW5ZSW1jU0Q2aW1mNVlWYkg2ZHlmTnlZMG9xTEVrc0QwQVVlTUFkTF9zVmFxVVJWMXdtRVVxTXo2U3locmFUTkdvZnFtb2lGS3JqY2VYT3hkSm42ZmpTNTR5V2dzeWZ4czdzSi04a2lERGFJN04tOEhjRkRBX1BNczAta2FZcERVNWhTZ2t5YzA2VVVzcElQY2lMd2lkd3kxTGlBSEJxMkEtZkw2X281NE9DLVhjdHJ5STNmZVhvOXJuOHVlNEY0TWJtbFpValE4VEtpWkNVTF9TajhZWG1vck9SRjgzUjZPcy1YcWp4VUdNU2YwQkd4WDBjTmlVNTd0c2Jld05hbXZod3ZqT2F5Yk0xX2VhdHZmcnp0d3JCQw?oc=5" target="_blank">S&amp;P 500 rallies 1.7% for its biggest gain in 2 months on hopes for a US-Iran deal to get oil flowing again</a>&nbsp;&nbsp;<font color="#6f6f6f">KVUE</font>	https://news.google.com/rss/articles/CBMiqAJBVV95cUxONjk5X0V0a0hLLW5ZSW1jU0Q2aW1mNVlWYkg2ZHlmTnlZMG9xTEVrc0QwQVVlTUFkTF9zVmFxVVJWMXdtRVVxTXo2U3locmFUTkdvZnFtb2lGS3JqY2VYT3hkSm42ZmpTNTR5V2dzeWZ4czdzSi04a2lERGFJN04tOEhjRkRBX1BNczAta2FZcERVNWhTZ2t5YzA2VVVzcElQY2lMd2lkd3kxTGlBSEJxMkEtZkw2X281NE9DLVhjdHJ5STNmZVhvOXJuOHVlNEY0TWJtbFpValE4VEtpWkNVTF9TajhZWG1vck9SRjgzUjZPcy1YcWp4VUdNU2YwQkd4WDBjTmlVNTd0c2Jld05hbXZod3ZqT2F5Yk0xX2VhdHZmcnp0d3JCQw?oc=5	0.21333333333333337	contract	2026-06-11 20:01:00	2026-06-12 07:31:02.922815
27	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	National Security Law’s Expiration Likely in Dispute Over Proposed Spy Chief - The Well News	<a href="https://news.google.com/rss/articles/CBMivwFBVV95cUxQZXJzQWt0Y2NsU2ZyQVBCczN4bklrZHR3SnRHdE4zQ0RTbl96Y1NnMTBYSjRIZlJqVXlWbGVGWTZkUmtDMHNqNDNGQ2dYd1FWQkZ5UGpiTjdzUlRFZ2VSOEJ6MjJsYmFqTllENlJaSERsejZYdExtdzFkR2Q2a051aVVGQW1KS3c0VU9oU0xSU1Z5azFodGhlQjV1ZHc1WGM5UHpZUDN4bzlLajlhRkpQWU52WmtmQkZkcm5QNWRxWQ?oc=5" target="_blank">National Security Law’s Expiration Likely in Dispute Over Proposed Spy Chief</a>&nbsp;&nbsp;<font color="#6f6f6f">The Well News</font>	https://news.google.com/rss/articles/CBMivwFBVV95cUxQZXJzQWt0Y2NsU2ZyQVBCczN4bklrZHR3SnRHdE4zQ0RTbl96Y1NnMTBYSjRIZlJqVXlWbGVGWTZkUmtDMHNqNDNGQ2dYd1FWQkZ5UGpiTjdzUlRFZ2VSOEJ6MjJsYmFqTllENlJaSERsejZYdExtdzFkR2Q2a051aVVGQW1KS3c0VU9oU0xSU1Z5azFodGhlQjV1ZHc1WGM5UHpZUDN4bzlLajlhRkpQWU52WmtmQkZkcm5QNWRxWQ?oc=5	0	general	2026-06-11 21:45:17	2026-06-12 07:31:02.924082
28	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	Hakeem Jeffries Finally Finds a Spine: Dem Leaders Rallied Against Extending Domestic Spy Law - The Intercept	<a href="https://news.google.com/rss/articles/CBMiekFVX3lxTE1jcVJBYXZTMW82T1c1MEFZdE9sUmkzVHY2Tm14c3hfZDA0WmpJM1hYZHVuSGJXOXY4RGhjbzdzcVA5Vlc0WGwzUEVYUGR3WGJjUXd0aGxaODhNLWttcFQyR3hRTkhQeDBSZFFvUUVyN2dSMnZ2STJTMDFB?oc=5" target="_blank">Hakeem Jeffries Finally Finds a Spine: Dem Leaders Rallied Against Extending Domestic Spy Law</a>&nbsp;&nbsp;<font color="#6f6f6f">The Intercept</font>	https://news.google.com/rss/articles/CBMiekFVX3lxTE1jcVJBYXZTMW82T1c1MEFZdE9sUmkzVHY2Tm14c3hfZDA0WmpJM1hYZHVuSGJXOXY4RGhjbzdzcVA5Vlc0WGwzUEVYUGR3WGJjUXd0aGxaODhNLWttcFQyR3hRTkhQeDBSZFFvUUVyN2dSMnZ2STJTMDFB?oc=5	0	general	2026-06-11 19:42:31	2026-06-12 07:31:02.925357
29	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	House rejects last-minute extension for key FISA spy power amid Bill Pulte uproar - CBS News	<a href="https://news.google.com/rss/articles/CBMimAFBVV95cUxOTVBHS2RFYXNyRmpJV0VXQUhwWko1cnpkbXFpaTdWVUVYU3JiRU01RmRtUnRLd2NEYnBFRDBLOEJodEViVm9haE54c2ZoVGpvSDZLb2xzQkxMRmgzVElMVjVpRWRrTHlnZFcweFhDa18tZS1zbWdkY1VkYnJtcHpacldBOFUtanFvNkwyX1JpUTBsaDFra2x0bw?oc=5" target="_blank">House rejects last-minute extension for key FISA spy power amid Bill Pulte uproar</a>&nbsp;&nbsp;<font color="#6f6f6f">CBS News</font>	https://news.google.com/rss/articles/CBMimAFBVV95cUxOTVBHS2RFYXNyRmpJV0VXQUhwWko1cnpkbXFpaTdWVUVYU3JiRU01RmRtUnRLd2NEYnBFRDBLOEJodEViVm9haE54c2ZoVGpvSDZLb2xzQkxMRmgzVElMVjVpRWRrTHlnZFcweFhDa18tZS1zbWdkY1VkYnJtcHpacldBOFUtanFvNkwyX1JpUTBsaDFra2x0bw?oc=5	0	general	2026-06-11 10:00:00	2026-06-12 07:31:03.483121
30	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	Rocket Lab Joins Nasdaq 100 As Index Upgrade Tests Growth Story - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMilwFBVV95cUxOU2RQV0M0OGFLcEd4YktYemdld1ViTnBPTm5Tajl1aFFHclBCa1lrUVRpb3I5ODR5NmZNdVk2a3FMSDBNM3pPSmRzSmtUc19vMzAzdFJadXptQXNnbWZIV3R1czR6ckVxQ04zaWJIUkprLUFtbHR2eGJPTHpPM2x1NVdGTEd3Z1p4aWtsNkNRcTF4ZzV6TGVv?oc=5" target="_blank">Rocket Lab Joins Nasdaq 100 As Index Upgrade Tests Growth Story</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMilwFBVV95cUxOU2RQV0M0OGFLcEd4YktYemdld1ViTnBPTm5Tajl1aFFHclBCa1lrUVRpb3I5ODR5NmZNdVk2a3FMSDBNM3pPSmRzSmtUc19vMzAzdFJadXptQXNnbWZIV3R1czR6ckVxQ04zaWJIUkprLUFtbHR2eGJPTHpPM2x1NVdGTEd3Z1p4aWtsNkNRcTF4ZzV6TGVv?oc=5	0.64	upgrade	2026-06-12 05:11:00	2026-06-12 07:31:03.485654
31	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	Rocket Lab and these four stocks are joining the Nasdaq 100, with SpaceX waiting in the wings - MarketWatch	<a href="https://news.google.com/rss/articles/CBMi0AFBVV95cUxOSW9wdlRlTWJXMVlUZFFLelBvaFl5M3lxY09DTFNrR2hMN3BOMjZYNF9PbU5fdmZHTmttSGZucUJqdUhjU01HWmVNS3pYN1huX04yeGlObnN3TnZiOGxCRHN0Y2NubDRVNGsxNVNkcnRMYnAtRnNRMTZ1Q1lvQjVhTUNDUXkzR2diOURhTTR6THRjTUdLYzZfb0x1M1RJUkxuQUw4bzVkVnV2Sy1wVGNyeTA3OWFDQ3M3QUU0N2FTdmJvOTRldlVTSmVFQUNVQUhG?oc=5" target="_blank">Rocket Lab and these four stocks are joining the Nasdaq 100, with SpaceX waiting in the wings</a>&nbsp;&nbsp;<font color="#6f6f6f">MarketWatch</font>	https://news.google.com/rss/articles/CBMi0AFBVV95cUxOSW9wdlRlTWJXMVlUZFFLelBvaFl5M3lxY09DTFNrR2hMN3BOMjZYNF9PbU5fdmZHTmttSGZucUJqdUhjU01HWmVNS3pYN1huX04yeGlObnN3TnZiOGxCRHN0Y2NubDRVNGsxNVNkcnRMYnAtRnNRMTZ1Q1lvQjVhTUNDUXkzR2diOURhTTR6THRjTUdLYzZfb0x1M1RJUkxuQUw4bzVkVnV2Sy1wVGNyeTA3OWFDQ3M3QUU0N2FTdmJvOTRldlVTSmVFQUNVQUhG?oc=5	0	general	2026-06-12 01:56:00	2026-06-12 07:31:03.486961
32	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	Final Trade: DAL, QQQ, META, GDX - CNBC	<a href="https://news.google.com/rss/articles/CBMie0FVX3lxTE1JbExIbVVZRThaVXlmTmhSMTNKS2JnM2JNMFdEd3JzeENCR0J0d0pwN3RGQjhsUDJPS2g0bkJZX3p1Qzkwb3VCU3daclRWMDBWSVpxTlVxYzh4Z29hT2FLRzRjNU52cDVfT2FFZnY3QVYzd3lHSWR4UWpRSQ?oc=5" target="_blank">Final Trade: DAL, QQQ, META, GDX</a>&nbsp;&nbsp;<font color="#6f6f6f">CNBC</font>	https://news.google.com/rss/articles/CBMie0FVX3lxTE1JbExIbVVZRThaVXlmTmhSMTNKS2JnM2JNMFdEd3JzeENCR0J0d0pwN3RGQjhsUDJPS2g0bkJZX3p1Qzkwb3VCU3daclRWMDBWSVpxTlVxYzh4Z29hT2FLRzRjNU52cDVfT2FFZnY3QVYzd3lHSWR4UWpRSQ?oc=5	0	general	2026-06-11 22:04:00	2026-06-12 07:31:03.488236
33	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	Astera, Rocket Lab shares surge after hours on addition to Nasdaq 100 - Investing.com	<a href="https://news.google.com/rss/articles/CBMiwwFBVV95cUxPUTRkbXZKR1ZsV1dla09zbF9SMU5FRnpyZC1zcE1wcUNFZFdHVjVIU09MVXNXT3NvaXV3dm5RRXJsajRBRV95RUF1MUFpZGRRWWVQQXpIeFM1d21iTVQ0YnB1dXF6WkVwWGdyeG9CMHpyQjR1ajc4NGJVZEtWcHQzdHNndkhvWHA2cGd4a0QtZm5SRjJwWE9ZcTVuNVdmNko3ZnZqR0M1Yk1JZWdBc2x6VjFobEpLVVNOU0JqM1JfbWRtSTA?oc=5" target="_blank">Astera, Rocket Lab shares surge after hours on addition to Nasdaq 100</a>&nbsp;&nbsp;<font color="#6f6f6f">Investing.com</font>	https://news.google.com/rss/articles/CBMiwwFBVV95cUxPUTRkbXZKR1ZsV1dla09zbF9SMU5FRnpyZC1zcE1wcUNFZFdHVjVIU09MVXNXT3NvaXV3dm5RRXJsajRBRV95RUF1MUFpZGRRWWVQQXpIeFM1d21iTVQ0YnB1dXF6WkVwWGdyeG9CMHpyQjR1ajc4NGJVZEtWcHQzdHNndkhvWHA2cGd4a0QtZm5SRjJwWE9ZcTVuNVdmNko3ZnZqR0M1Yk1JZWdBc2x6VjFobEpLVVNOU0JqM1JfbWRtSTA?oc=5	0.32	general	2026-06-12 01:18:35	2026-06-12 07:31:03.489581
34	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	RKLB Stock Rallies After Earning Nasdaq 100 Spot – SpaceX Could Be Next Under New Rules - TradingView	<a href="https://news.google.com/rss/articles/CBMi3wFBVV95cUxNZy1sUVlMdHlrcXR3YjF4dVNZRFVoSzVoSWp2Wjl1NUc1Zk9SMkdpQ1FYNTM1MUZxQ0I3TUEtVmFWR3RxWWhOUUpoOVRGT0RYdVp3M2hDbDg5OE9QU29OSUtqa3hXSjgzZ3JhakxyaXpKTjZ4ZTRPSU5pVGVSREl2YUNEajZ1WEpyb1d4NHh6NHBBcjRZOEVQVFYxUUkwS29peXBRdWZnd09zYmhXTHhNZ1djakpZWkNIZXU2ZUpieUgxOW9DNGllUE9RdGgwc0ZGRUpjbGpWMlhHNVF0WVJN?oc=5" target="_blank">RKLB Stock Rallies After Earning Nasdaq 100 Spot – SpaceX Could Be Next Under New Rules</a>&nbsp;&nbsp;<font color="#6f6f6f">TradingView</font>	https://news.google.com/rss/articles/CBMi3wFBVV95cUxNZy1sUVlMdHlrcXR3YjF4dVNZRFVoSzVoSWp2Wjl1NUc1Zk9SMkdpQ1FYNTM1MUZxQ0I3TUEtVmFWR3RxWWhOUUpoOVRGT0RYdVp3M2hDbDg5OE9QU29OSUtqa3hXSjgzZ3JhakxyaXpKTjZ4ZTRPSU5pVGVSREl2YUNEajZ1WEpyb1d4NHh6NHBBcjRZOEVQVFYxUUkwS29peXBRdWZnd09zYmhXTHhNZ1djakpZWkNIZXU2ZUpieUgxOW9DNGllUE9RdGgwc0ZGRUpjbGpWMlhHNVF0WVJN?oc=5	0	general	2026-06-12 05:10:00	2026-06-12 07:31:03.491504
35	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	SpaceX Could Join the Nasdaq-100 Very Soon. Should You Buy the Invesco QQQ Trust Today? - The Motley Fool	<a href="https://news.google.com/rss/articles/CBMilwFBVV95cUxQQjN4b05hOHh2Tlo4OEZtM3hkQzJ1elJ3cXBySFdvMzR0SU9qbkVobWVKaWFweFdyaWhJMndMU2ZtYVhYRk1ZRER4NmQ2UTUxcEEyVmE4OFJCN19UdHg2Q242WFdWdFpkZ0FxVXM1TldCU2x5ZUdmUHMzdDFHVExYVV9mYmQ5aWNsUVJhMFRHUm9JX3U5LXBn?oc=5" target="_blank">SpaceX Could Join the Nasdaq-100 Very Soon. Should You Buy the Invesco QQQ Trust Today?</a>&nbsp;&nbsp;<font color="#6f6f6f">The Motley Fool</font>	https://news.google.com/rss/articles/CBMilwFBVV95cUxQQjN4b05hOHh2Tlo4OEZtM3hkQzJ1elJ3cXBySFdvMzR0SU9qbkVobWVKaWFweFdyaWhJMndMU2ZtYVhYRk1ZRER4NmQ2UTUxcEEyVmE4OFJCN19UdHg2Q242WFdWdFpkZ0FxVXM1TldCU2x5ZUdmUHMzdDFHVExYVV9mYmQ5aWNsUVJhMFRHUm9JX3U5LXBn?oc=5	0	general	2026-06-09 15:00:00	2026-06-12 07:31:03.492797
36	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	How to hedge your portfolio against the Nasdaq-100 using QQQ put spreads - CNBC	<a href="https://news.google.com/rss/articles/CBMirgFBVV95cUxNTUJENWdlaGpJa1RWbkFRVjgwZHJPVDFwVTd0MUVNR1c5eGF0NWNTUl9abGdlTGpXODRTMUhVaWNrdnpUS25HQzllVS1rN2NTQjhhbzlKeU42MGJ3YnI4cHloRzBPcjFMZ2VDZy16N1BjbDlucXJjMjBWQlF5TjA0dUdZeW96bzgzU0ZIZFJURHA0dWpjMTVDYTEzNkJMdEJlRnNLVWxrM2dLVUJBVnc?oc=5" target="_blank">How to hedge your portfolio against the Nasdaq-100 using QQQ put spreads</a>&nbsp;&nbsp;<font color="#6f6f6f">CNBC</font>	https://news.google.com/rss/articles/CBMirgFBVV95cUxNTUJENWdlaGpJa1RWbkFRVjgwZHJPVDFwVTd0MUVNR1c5eGF0NWNTUl9abGdlTGpXODRTMUhVaWNrdnpUS25HQzllVS1rN2NTQjhhbzlKeU42MGJ3YnI4cHloRzBPcjFMZ2VDZy16N1BjbDlucXJjMjBWQlF5TjA0dUdZeW96bzgzU0ZIZFJURHA0dWpjMTVDYTEzNkJMdEJlRnNLVWxrM2dLVUJBVnc?oc=5	0	general	2026-06-09 14:15:13	2026-06-12 07:31:03.495339
37	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	SpaceX Could Join the Nasdaq-100 Very Soon. Should You Buy the Invesco QQQ Trust Today? - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMimAFBVV95cUxQcUNLb0Y5U2J0WUdmdWNiUUNXR3QxVUttcHJKeXZfMy11TUJsVENXUnJkWF9EbG5FNkxDMFB5TmJ2RDY5aDBCVTJSeFljRW1vTExIVGM4elBRVlBZcVk5NGd3VDVMYXQzQy0xZDRJZGZZRmViZXpGdXZGWUtrLTI4STdNQ2swUHhtdi1veFhwMjBnblVlVUxPYw?oc=5" target="_blank">SpaceX Could Join the Nasdaq-100 Very Soon. Should You Buy the Invesco QQQ Trust Today?</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMimAFBVV95cUxQcUNLb0Y5U2J0WUdmdWNiUUNXR3QxVUttcHJKeXZfMy11TUJsVENXUnJkWF9EbG5FNkxDMFB5TmJ2RDY5aDBCVTJSeFljRW1vTExIVGM4elBRVlBZcVk5NGd3VDVMYXQzQy0xZDRJZGZZRmViZXpGdXZGWUtrLTI4STdNQ2swUHhtdi1veFhwMjBnblVlVUxPYw?oc=5	0	general	2026-06-09 14:20:00	2026-06-12 07:31:03.496628
38	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	How SpaceX's inclusion in the S&P and Nasdaq 100 could impact investors - CNBC	<a href="https://news.google.com/rss/articles/CBMisgFBVV95cUxOY1pYVEdzUkRSUTVEMEt0Zjdrd2xZaFl0NDhfRVQtU2JPNFFFaVgxS256c244SkQzcXVSZHhEYkN6bkNuenpabldDSlJFVHNkZ1hVcks4bFc0OVNmUU1IaEFKQmZNTzNfUTVZM1BuZzRGZDA0VHNsOHV3VGp2RTdYcmV4Y0xBUDlEYWw1VmU2ME5Kd05iTTR1enM1czBjbjNNV1FzeFdtT2dpQ3FMcXNlSXJB?oc=5" target="_blank">How SpaceX's inclusion in the S&amp;P and Nasdaq 100 could impact investors</a>&nbsp;&nbsp;<font color="#6f6f6f">CNBC</font>	https://news.google.com/rss/articles/CBMisgFBVV95cUxOY1pYVEdzUkRSUTVEMEt0Zjdrd2xZaFl0NDhfRVQtU2JPNFFFaVgxS256c244SkQzcXVSZHhEYkN6bkNuenpabldDSlJFVHNkZ1hVcks4bFc0OVNmUU1IaEFKQmZNTzNfUTVZM1BuZzRGZDA0VHNsOHV3VGp2RTdYcmV4Y0xBUDlEYWw1VmU2ME5Kd05iTTR1enM1czBjbjNNV1FzeFdtT2dpQ3FMcXNlSXJB?oc=5	0	general	2026-06-10 23:21:00	2026-06-12 07:31:03.497894
39	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	Better ETF Buy Right Now: QQQ vs. SCHG - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMikAFBVV95cUxQM2JiOVlUYmVqMTVaRmpqSS10T3FjU2RQSEVEMjZURm5hMzE2Tl9kN2tOdHdHYVg2bG51clFIRVhpVTV5bkMzTTQ5ZzcwTW5pYTlPNEpCNGdhNERLMXh5dUIyUzN3TDhVR1pCSjNGcmN2elNFcVJKSFFpN0J1NTVzbk5MeWJoT2dwMFI1eWE1QjY?oc=5" target="_blank">Better ETF Buy Right Now: QQQ vs. SCHG</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMikAFBVV95cUxQM2JiOVlUYmVqMTVaRmpqSS10T3FjU2RQSEVEMjZURm5hMzE2Tl9kN2tOdHdHYVg2bG51clFIRVhpVTV5bkMzTTQ5ZzcwTW5pYTlPNEpCNGdhNERLMXh5dUIyUzN3TDhVR1pCSjNGcmN2elNFcVJKSFFpN0J1NTVzbk5MeWJoT2dwMFI1eWE1QjY?oc=5	0	etf	2026-06-09 10:44:00	2026-06-12 07:31:03.500466
40	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	QQQ vs. VGT: The Best Way to Own Big Tech? - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMijAFBVV95cUxOU0l6Y1ZsOTBSdXg2Y28xRGROUno2WGFRODNZbWIwTjluU3AtakFkbjRxZ1lKSDFFUVN6anB2RXJibGpUdzFFbmhmWmFhME9DQWhVOWpzcGVuR2w4TzJhU280T0YxVV8welVqdHB0Q2RkNXByc0dPMEl2bU9ReXhSTHNRelRJNUtsRThiYg?oc=5" target="_blank">QQQ vs. VGT: The Best Way to Own Big Tech?</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMijAFBVV95cUxOU0l6Y1ZsOTBSdXg2Y28xRGROUno2WGFRODNZbWIwTjluU3AtakFkbjRxZ1lKSDFFUVN6anB2RXJibGpUdzFFbmhmWmFhME9DQWhVOWpzcGVuR2w4TzJhU280T0YxVV8welVqdHB0Q2RkNXByc0dPMEl2bU9ReXhSTHNRelRJNUtsRThiYg?oc=5	0	general	2026-06-10 18:20:24	2026-06-12 07:31:03.502563
41	6	""QQQ" OR "Nasdaq 100" OR "Invesco QQQ"" - Google News	QQQ vs. QQQM: Same Index, So Which One Should You Actually Buy? - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMikAFBVV95cUxQMmhCV1Z1N0RDclZNc2xRendVZHk3V2RKak9JV3l1NWxoUzJUWTNxZXVXLUZkT2JtVUdDRWY0TmpMOF9vR0szOEhzcG9QZFZNWUFWeXFGWG9FN3F2VGFYMjBEYm5xN0VXS3RCaU5EVnRrMXJuU1U4XzN3X3ZITmJ5RWJEaldoUnVYemRBQzhGNEY?oc=5" target="_blank">QQQ vs. QQQM: Same Index, So Which One Should You Actually Buy?</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMikAFBVV95cUxQMmhCV1Z1N0RDclZNc2xRendVZHk3V2RKak9JV3l1NWxoUzJUWTNxZXVXLUZkT2JtVUdDRWY0TmpMOF9vR0szOEhzcG9QZFZNWUFWeXFGWG9FN3F2VGFYMjBEYm5xN0VXS3RCaU5EVnRrMXJuU1U4XzN3X3ZITmJ5RWJEaldoUnVYemRBQzhGNEY?oc=5	0	general	2026-06-10 18:28:26	2026-06-12 07:31:04.042035
42	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	VOO vs. VTI: Should You Own the S&P 500 or the Entire Market? - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMiiAFBVV95cUxNLVhZb3VQRnpKZ3BiSy0tLWU2cXBaR1VlWi1fZkdnMGRfM2Z0cXVMNURiWkhYMHNna0MwQXJJYTlRc241T1Bob0pWV3RKcV9yeU5ydDFUeEJZMlI0OVNVNnRTUGdHS3ZjaFZGWWRrWnBTZmRZU0dHUHk5QVFIRVl2bFI1T2RPbFNX?oc=5" target="_blank">VOO vs. VTI: Should You Own the S&amp;P 500 or the Entire Market?</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMiiAFBVV95cUxNLVhZb3VQRnpKZ3BiSy0tLWU2cXBaR1VlWi1fZkdnMGRfM2Z0cXVMNURiWkhYMHNna0MwQXJJYTlRc241T1Bob0pWV3RKcV9yeU5ydDFUeEJZMlI0OVNVNnRTUGdHS3ZjaFZGWWRrWnBTZmRZU0dHUHk5QVFIRVl2bFI1T2RPbFNX?oc=5	0	general	2026-06-10 18:52:24	2026-06-12 07:31:04.043996
43	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	VTI Is Cheaper Than Its Own History. Is The Market Missing Something? - Trefis	<a href="https://news.google.com/rss/articles/CBMi0wFBVV95cUxNS25xZFlwVzJDUFhBbUMwRVBjUWczOU8zVEpwUHRiSDkxcy1GX3Z4Rkk3UG5pcnFHQkVVSXA2bk53dzV5SVJaZFUyXzhFcUN5ZmNBbHNSQzBPbWZTc3pfWlZxVGJ3clFfODh6UFJmOHJRdDRZeENvelNnS0FRTmZfSEtGU3RZRXBSZ204eGRDaTY1SVpZZzFqbmVpNzdoSDhwWkJPZ0ZtdFhEYmNnWnRzSHNxa2RxWERmYWdhVmRad1pqcVpaT09tRmJUMVR2b0VXTmJF?oc=5" target="_blank">VTI Is Cheaper Than Its Own History. Is The Market Missing Something?</a>&nbsp;&nbsp;<font color="#6f6f6f">Trefis</font>	https://news.google.com/rss/articles/CBMi0wFBVV95cUxNS25xZFlwVzJDUFhBbUMwRVBjUWczOU8zVEpwUHRiSDkxcy1GX3Z4Rkk3UG5pcnFHQkVVSXA2bk53dzV5SVJaZFUyXzhFcUN5ZmNBbHNSQzBPbWZTc3pfWlZxVGJ3clFfODh6UFJmOHJRdDRZeENvelNnS0FRTmZfSEtGU3RZRXBSZ204eGRDaTY1SVpZZzFqbmVpNzdoSDhwWkJPZ0ZtdFhEYmNnWnRzSHNxa2RxWERmYWdhVmRad1pqcVpaT09tRmJUMVR2b0VXTmJF?oc=5	0	general	2026-06-12 06:07:22	2026-06-12 07:31:04.045405
44	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	VTI is up 0.4% today, on INTC stock price movement - Quiver Quantitative	<a href="https://news.google.com/rss/articles/CBMikAFBVV95cUxONUl6cXZpQXBLc2RKVzA3YS12YmdMdHhSZnpTUzBieWx4RTJySzg5WUxMcEFzbnRtSUxPY2VZU28xcHFoWVU2bnFYRWJRTzNxSEJpVENZQVg5M3VWQkNaMkRneVZwUlA5VXdrNDY5dHBrLUdrbG16a3JwbEZiS1dRZzBFd0dvTklVZmF3SlpMMmM?oc=5" target="_blank">VTI is up 0.4% today, on INTC stock price movement</a>&nbsp;&nbsp;<font color="#6f6f6f">Quiver Quantitative</font>	https://news.google.com/rss/articles/CBMikAFBVV95cUxONUl6cXZpQXBLc2RKVzA3YS12YmdMdHhSZnpTUzBieWx4RTJySzg5WUxMcEFzbnRtSUxPY2VZU28xcHFoWVU2bnFYRWJRTzNxSEJpVENZQVg5M3VWQkNaMkRneVZwUlA5VXdrNDY5dHBrLUdrbG16a3JwbEZiS1dRZzBFd0dvTklVZmF3SlpMMmM?oc=5	0	general	2026-06-11 16:15:00	2026-06-12 07:31:04.046736
45	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	VTI vs. VOO: Which Vanguard ETF Will Buy More SpaceX Stock After Its IPO? - AOL.com	<a href="https://news.google.com/rss/articles/CBMidkFVX3lxTFA3UkNwa3RFRkoybGx4V0RyUThyV0FIVGpLajN4MUEyS0t4dlJPRC1oNW5PNjVzVWYyNDkwV1c5OWs1TUkyM0lseHN3T0pnNWpwSXBrZ1Rya3l0TU1MbEpZcG5iNFZKYS1sc1VZMHlfWkRtMUxyMlE?oc=5" target="_blank">VTI vs. VOO: Which Vanguard ETF Will Buy More SpaceX Stock After Its IPO?</a>&nbsp;&nbsp;<font color="#6f6f6f">AOL.com</font>	https://news.google.com/rss/articles/CBMidkFVX3lxTFA3UkNwa3RFRkoybGx4V0RyUThyV0FIVGpLajN4MUEyS0t4dlJPRC1oNW5PNjVzVWYyNDkwV1c5OWs1TUkyM0lseHN3T0pnNWpwSXBrZ1Rya3l0TU1MbEpZcG5iNFZKYS1sc1VZMHlfWkRtMUxyMlE?oc=5	0	etf	2026-06-12 05:00:31	2026-06-12 07:31:04.048692
46	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	VOO vs. VTI: Should You Own the S&P 500 or the Entire Market? - 24/7 Wall St.	<a href="https://news.google.com/rss/articles/CBMiowFBVV95cUxQTlBlY0JjSnVISGVQVUVia1drYWw0R0lfLXNpbHdEU3FGWHR3S1ZnejJCMWRQRHNEU29EVURJeUNiVHRRaDZmS19LWkliVmhoeHdWeUhPLWlmNTlTck9hZGF5X2N0eGpneDlwNUlweFA5UFJPMVR2YVdqRklLcmttU0NaV1JUYV90UWdzeHRfa2hsRHlERGNYQm9UemtrNmVnR0lJ?oc=5" target="_blank">VOO vs. VTI: Should You Own the S&amp;P 500 or the Entire Market?</a>&nbsp;&nbsp;<font color="#6f6f6f">24/7 Wall St.</font>	https://news.google.com/rss/articles/CBMiowFBVV95cUxQTlBlY0JjSnVISGVQVUVia1drYWw0R0lfLXNpbHdEU3FGWHR3S1ZnejJCMWRQRHNEU29EVURJeUNiVHRRaDZmS19LWkliVmhoeHdWeUhPLWlmNTlTck9hZGF5X2N0eGpneDlwNUlweFA5UFJPMVR2YVdqRklLcmttU0NaV1JUYV90UWdzeHRfa2hsRHlERGNYQm9UemtrNmVnR0lJ?oc=5	0	general	2026-06-10 18:52:24	2026-06-12 07:31:04.0506
47	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	Vanguard Total Stock Market ETF (Ondo Tokenized) Analytics - CryptoRank	<a href="https://news.google.com/rss/articles/CBMijAFBVV95cUxOQVdhTVRnQTl3cGhUalg5bThZNVhQZW5hMnlrQ3llQUhKQm85NTgzTUhoN0I3Q2N1RFhCRlJMbkZEUTd6aGtDX1ZzX21PeVpHOUxpVmdPeXBObW5ibTQ1bmRDc0kzeE15R29IbDJDanMtLXFrWUJia0t4RzY0MTFtNVVXb3QxVmRkbkZlYg?oc=5" target="_blank">Vanguard Total Stock Market ETF (Ondo Tokenized) Analytics</a>&nbsp;&nbsp;<font color="#6f6f6f">CryptoRank</font>	https://news.google.com/rss/articles/CBMijAFBVV95cUxOQVdhTVRnQTl3cGhUalg5bThZNVhQZW5hMnlrQ3llQUhKQm85NTgzTUhoN0I3Q2N1RFhCRlJMbkZEUTd6aGtDX1ZzX21PeVpHOUxpVmdPeXBObW5ibTQ1bmRDc0kzeE15R29IbDJDanMtLXFrWUJia0t4RzY0MTFtNVVXb3QxVmRkbkZlYg?oc=5	0	etf	2026-06-09 15:45:56	2026-06-12 07:31:04.052599
48	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	Is the Vanguard Total Stock Market ETF the Best Buy for Long-Term Investors? - The Globe and Mail	<a href="https://news.google.com/rss/articles/CBMi8gFBVV95cUxNTVJjTnZ3MVpXX2ZVZ2x5NVNYU0FWOFJSRnRlaGNwVU1Temc2UDlGakpvTlZ2cTFoSlByVjNQWEVEVzNjSHJpZ0YwT3EtSExKM3pZTllubkpzYXo1WG5admxVbGdUZXBTME9FbE1MdlViU095SmszaHhaeUZLdHlUanJfNTBreHZjOXhHRFpCd3BGdUpXTm1GQlE1TVE1S3Blem4zQjEyZ2ZNYU5hWDdLUFRtRGw2VHhVTXNKN0xZenJ6c2hZT2ozX19xUTFZOFdpSUdCNUkwMDVPRVZrWFhueXJhdEdEc01PY1BtRDRaN0w3UQ?oc=5" target="_blank">Is the Vanguard Total Stock Market ETF the Best Buy for Long-Term Investors?</a>&nbsp;&nbsp;<font color="#6f6f6f">The Globe and Mail</font>	https://news.google.com/rss/articles/CBMi8gFBVV95cUxNTVJjTnZ3MVpXX2ZVZ2x5NVNYU0FWOFJSRnRlaGNwVU1Temc2UDlGakpvTlZ2cTFoSlByVjNQWEVEVzNjSHJpZ0YwT3EtSExKM3pZTllubkpzYXo1WG5admxVbGdUZXBTME9FbE1MdlViU095SmszaHhaeUZLdHlUanJfNTBreHZjOXhHRFpCd3BGdUpXTm1GQlE1TVE1S3Blem4zQjEyZ2ZNYU5hWDdLUFRtRGw2VHhVTXNKN0xZenJ6c2hZT2ozX19xUTFZOFdpSUdCNUkwMDVPRVZrWFhueXJhdEdEc01PY1BtRDRaN0w3UQ?oc=5	0	etf	2026-06-10 11:40:00	2026-06-12 07:31:04.05393
49	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	VTI ETF Falls 0.2% - Moomoo	<a href="https://news.google.com/rss/articles/CBMia0FVX3lxTE9mWkhpRUVWUlRuc1ZGMUFGbkpHcmJ4NWxqX0U0Vk1IZDlZekJpZUJzdGRveVFUSlZsZHpYbWtyMFNFcFVKZ2luc0pLdWx6bG9TTWZTcTJOMHFfcWQ1UnVuQTV1bXFteGJvZW5N?oc=5" target="_blank">VTI ETF Falls 0.2%</a>&nbsp;&nbsp;<font color="#6f6f6f">Moomoo</font>	https://news.google.com/rss/articles/CBMia0FVX3lxTE9mWkhpRUVWUlRuc1ZGMUFGbkpHcmJ4NWxqX0U0Vk1IZDlZekJpZUJzdGRveVFUSlZsZHpYbWtyMFNFcFVKZ2luc0pLdWx6bG9TTWZTcTJOMHFfcWQ1UnVuQTV1bXFteGJvZW5N?oc=5	0	etf	2026-06-09 20:40:13	2026-06-12 07:31:04.055792
50	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	VTI 260618 375.00C (VTI260618C375000) Stock Options Chain | Quotes & News - Moomoo	<a href="https://news.google.com/rss/articles/CBMi2gJBVV95cUxPUjVpTlZWWlpMRGljbzZ2Q180TmU2cjA1ZndPWGZfclZOelI0eHlDMHRzODBuNXZjVmV3NTBja256a0I2cS1hejFsYjVhS3hyVVUzZW44a0VzVWNaQjNYREZvTTU3Qlo5Smw4dVNmSWhDNGIwVTZFa0ZkdFhXTHZUZnVJbEVWMzQ5eDJBakFzOGgwSkYybjhpNVB3ZDV1Z1FEalZSRmdmVnh0MTRzTXZqX21FUjlkZFNiRVk3YjM1SzBCYVFvb3psVW9VZ1FNWnVHNGdxVm1uZVpyQ2pydkVUSFUzaDdRLV95SjFYRnY4S2Y4MEMtVlFuUE9yRmh4WjlwdjRzTHo5dy1scUpuNEpGLUU1akt2MkZQWVlDcTRvZjI0X0hLejU2VW14cThiazdXVUhNZ3N2ak9KdUduZ3RGVUlBRXdTUmQ2NFlWM2tCYmF3SnpaSmlyZG9B?oc=5" target="_blank">VTI 260618 375.00C (VTI260618C375000) Stock Options Chain | Quotes & News</a>&nbsp;&nbsp;<font color="#6f6f6f">Moomoo</font>	https://news.google.com/rss/articles/CBMi2gJBVV95cUxPUjVpTlZWWlpMRGljbzZ2Q180TmU2cjA1ZndPWGZfclZOelI0eHlDMHRzODBuNXZjVmV3NTBja256a0I2cS1hejFsYjVhS3hyVVUzZW44a0VzVWNaQjNYREZvTTU3Qlo5Smw4dVNmSWhDNGIwVTZFa0ZkdFhXTHZUZnVJbEVWMzQ5eDJBakFzOGgwSkYybjhpNVB3ZDV1Z1FEalZSRmdmVnh0MTRzTXZqX21FUjlkZFNiRVk3YjM1SzBCYVFvb3psVW9VZ1FNWnVHNGdxVm1uZVpyQ2pydkVUSFUzaDdRLV95SjFYRnY4S2Y4MEMtVlFuUE9yRmh4WjlwdjRzTHo5dy1scUpuNEpGLUU1akt2MkZQWVlDcTRvZjI0X0hLejU2VW14cThiazdXVUhNZ3N2ak9KdUduZ3RGVUlBRXdTUmQ2NFlWM2tCYmF3SnpaSmlyZG9B?oc=5	0	general	2026-06-10 19:06:05	2026-06-12 07:31:04.057667
51	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	Is the Vanguard Total Stock Market ETF the Best Buy for Long-Term Investors? - AOL.com	<a href="https://news.google.com/rss/articles/CBMigAFBVV95cUxOTVpDUHg0WUpQdUNqSzljNFZfZGpYZnEtMHNiRHFmdDdxcXdsdmdraUJKdU91RnZPdEdHd2JUWTdFbGdwcFBpd0Ryd2R5OV9ybFJkcGp6YXgxMVVkclZBeDlRMnp5ejVITTdRNXM4MGtXNnhlalA5M2t0WGV3aGVyTA?oc=5" target="_blank">Is the Vanguard Total Stock Market ETF the Best Buy for Long-Term Investors?</a>&nbsp;&nbsp;<font color="#6f6f6f">AOL.com</font>	https://news.google.com/rss/articles/CBMigAFBVV95cUxOTVpDUHg0WUpQdUNqSzljNFZfZGpYZnEtMHNiRHFmdDdxcXdsdmdraUJKdU91RnZPdEdHd2JUWTdFbGdwcFBpd0Ryd2R5OV9ybFJkcGp6YXgxMVVkclZBeDlRMnp5ejVITTdRNXM4MGtXNnhlalA5M2t0WGV3aGVyTA?oc=5	0	etf	2026-06-10 23:11:23	2026-06-12 07:31:04.06157
52	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	AAPL Stock Quote Price and Forecast - CNN	<a href="https://news.google.com/rss/articles/CBMiUEFVX3lxTE00U3JoRzhkckt5aVFxb1NVNnBndWhrcDM5N0NqUzZGUk8xQk04OF9jVWRULXh2RmlJaGpTS1FJWEREaUlNUnhfSHk2cm53NllX?oc=5" target="_blank">AAPL Stock Quote Price and Forecast</a>&nbsp;&nbsp;<font color="#6f6f6f">CNN</font>	https://news.google.com/rss/articles/CBMiUEFVX3lxTE00U3JoRzhkckt5aVFxb1NVNnBndWhrcDM5N0NqUzZGUk8xQk04OF9jVWRULXh2RmlJaGpTS1FJWEREaUlNUnhfSHk2cm53NllX?oc=5	0	general	2026-06-11 05:29:14	2026-06-12 07:31:04.607387
53	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Does Apple Stock Have More Upside? - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMimAFBVV95cUxPWVpNb0R6Mk9ucy1lbTJUaThOeUYtMTJWSGRfSXZ2eFpURDZ2X0lGbzdiQXB0X0VlZF8zQXFEZTF3dGZicFF6bGhsMEotaEVYbjlGRlJWSllGb0FsUW1DamFYek1HYWMwdEFmY3J1elhPUlRmLU82UGRhR2ZycTBtTjd5OTdXMmhTQWI5RWF2ZENsQVBXakNscg?oc=5" target="_blank">Does Apple Stock Have More Upside?</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMimAFBVV95cUxPWVpNb0R6Mk9ucy1lbTJUaThOeUYtMTJWSGRfSXZ2eFpURDZ2X0lGbzdiQXB0X0VlZF8zQXFEZTF3dGZicFF6bGhsMEotaEVYbjlGRlJWSllGb0FsUW1DamFYek1HYWMwdEFmY3J1elhPUlRmLU82UGRhR2ZycTBtTjd5OTdXMmhTQWI5RWF2ZENsQVBXakNscg?oc=5	0	general	2026-06-11 22:50:53	2026-06-12 07:31:04.60877
54	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Apple (AAPL) Live Share Price, Invest From India - INDmoney	<a href="https://news.google.com/rss/articles/CBMibkFVX3lxTE5KUzhNWU5ZRWhrdG9xQmlZd20wU2pjWi1OSlpPQ0VUOXRyT0JRTEJkWG90Z0hvR1JfY3FZTlpYaUROSks1R25BTXFEY3AyRUNZZG81WjlTQkN6SlZrdVpnbnRRZFk2Qm9BbHR0bFN3?oc=5" target="_blank">Apple (AAPL) Live Share Price, Invest From India</a>&nbsp;&nbsp;<font color="#6f6f6f">INDmoney</font>	https://news.google.com/rss/articles/CBMibkFVX3lxTE5KUzhNWU5ZRWhrdG9xQmlZd20wU2pjWi1OSlpPQ0VUOXRyT0JRTEJkWG90Z0hvR1JfY3FZTlpYaUROSks1R25BTXFEY3AyRUNZZG81WjlTQkN6SlZrdVpnbnRRZFk2Qm9BbHR0bFN3?oc=5	0	general	2026-06-12 03:15:59	2026-06-12 07:31:04.610073
55	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	AAPL Stock Slides Following WWDC, But Analysts Broadly Raise Targets - MacRumors	<a href="https://news.google.com/rss/articles/CBMiekFVX3lxTE9HLTBvVGJtVkdsQUtvWGstMk9ld1Z4cE81dlNLa0d2U3UyY19hQUY0cmpwR3RrMFFGVTg1SC1UVjFhRVVfckQ4bkVRUmkteVBTVTBYOVphbGFabHdIQUJWNTBuLUR5MUFZY3VWQ1FXSnN2NFp4MVhGM3NB?oc=5" target="_blank">AAPL Stock Slides Following WWDC, But Analysts Broadly Raise Targets</a>&nbsp;&nbsp;<font color="#6f6f6f">MacRumors</font>	https://news.google.com/rss/articles/CBMiekFVX3lxTE9HLTBvVGJtVkdsQUtvWGstMk9ld1Z4cE81dlNLa0d2U3UyY19hQUY0cmpwR3RrMFFGVTg1SC1UVjFhRVVfckQ4bkVRUmkteVBTVTBYOVphbGFabHdIQUJWNTBuLUR5MUFZY3VWQ1FXSnN2NFp4MVhGM3NB?oc=5	0	general	2026-06-11 15:51:16	2026-06-12 07:31:04.611309
56	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Why Apple Stock Is Sinking Today - The Motley Fool	<a href="https://news.google.com/rss/articles/CBMigAFBVV95cUxPSVk1X0ZRZXhkN3VkZGlranFLWVhOQTJ0ZW10NFZlcFNNZmJMLVJIaTFnbGxYS2ZLNkoyQ3Z2cmYwNk9XZkpDVTFQVjZ3RzloLUxrbDNYUDJ4M1dXZEpJOV84a1h0bFJ3c2pkbGlULWUweV9LTVppNlFUTVFXVUVNNQ?oc=5" target="_blank">Why Apple Stock Is Sinking Today</a>&nbsp;&nbsp;<font color="#6f6f6f">The Motley Fool</font>	https://news.google.com/rss/articles/CBMigAFBVV95cUxPSVk1X0ZRZXhkN3VkZGlranFLWVhOQTJ0ZW10NFZlcFNNZmJMLVJIaTFnbGxYS2ZLNkoyQ3Z2cmYwNk9XZkpDVTFQVjZ3RzloLUxrbDNYUDJ4M1dXZEpJOV84a1h0bFJ3c2pkbGlULWUweV9LTVppNlFUTVFXVUVNNQ?oc=5	0	general	2026-06-09 17:58:00	2026-06-12 07:31:04.612677
57	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Why is Apple stock sliding today? - Investing.com	<a href="https://news.google.com/rss/articles/CBMimgFBVV95cUxQa2tVVEdpa2FBWVhBM0RjQ1UyaDU0bkwzZGF6VmUyNTlnbkFfektNSEhLUXZSdTQ4Vzh6VjV5ZXpnOERUSlNsZDlwVmUwMkZpX1A1UlVDMWFoWFpvS21nRVJQeV8tcU52am1hbmUyTVlReHFhek9iSTdTZ19XeEEtLVM3bHkzLUJtTzZ3WnYzTnM3empFWDJyXzNn?oc=5" target="_blank">Why is Apple stock sliding today?</a>&nbsp;&nbsp;<font color="#6f6f6f">Investing.com</font>	https://news.google.com/rss/articles/CBMimgFBVV95cUxQa2tVVEdpa2FBWVhBM0RjQ1UyaDU0bkwzZGF6VmUyNTlnbkFfektNSEhLUXZSdTQ4Vzh6VjV5ZXpnOERUSlNsZDlwVmUwMkZpX1A1UlVDMWFoWFpvS21nRVJQeV8tcU52am1hbmUyTVlReHFhek9iSTdTZ19XeEEtLVM3bHkzLUJtTzZ3WnYzTnM3empFWDJyXzNn?oc=5	0	general	2026-06-09 14:42:05	2026-06-12 07:31:04.613947
58	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Here's Why Apple (AAPL) Gained But Lagged the Market Today - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMilwFBVV95cUxPUkl2NFZ3emV6ajRwVnBURFhmcVlCNDFuLU1IVWNGeHR0ZndKUS1FNlR5NDFtcmdXQWpRaE44NGNrN2U3OHBfWjNXWmRfS054T0Q1WUhVU2p3X0llOWxnWHBsUTd0SkpvR3ZQdlVkNURCSnNBX2xTbm5Wa3RjTDIzVE51YjNjWl80aGRQYjRzUjFfNWVNUmtn?oc=5" target="_blank">Here's Why Apple (AAPL) Gained But Lagged the Market Today</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMilwFBVV95cUxPUkl2NFZ3emV6ajRwVnBURFhmcVlCNDFuLU1IVWNGeHR0ZndKUS1FNlR5NDFtcmdXQWpRaE44NGNrN2U3OHBfWjNXWmRfS054T0Q1WUhVU2p3X0llOWxnWHBsUTd0SkpvR3ZQdlVkNURCSnNBX2xTbm5Wa3RjTDIzVE51YjNjWl80aGRQYjRzUjFfNWVNUmtn?oc=5	0	general	2026-06-11 21:45:02	2026-06-12 07:31:04.617083
59	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	The Tariff Threat to Apple Stock Vanished. Its Replacement Is a Bigger Worry. - Trefis	<a href="https://news.google.com/rss/articles/CBMi3wFBVV95cUxQM3VaMGdlVHdIOTFVdmpxalo3UGxpMEVKUzkxYlpSVUNjNk5HWUUwQllZNXBwV19GQW1MWHRaOTZLWkV2c0JvQlgyQVJJYmFRWjNXM0VnakxZVVY5N3dsZGQwOU1FdVFMSWc2TzNiRGItckI0ZjlkM1B4TzhiMWtFZ1ExRjNKZ0d2UzY2YlBDWjJqVG10aW04UkNndVRVUXFoVU9TZ0JEaklza1ZkQm0zRmdVdjNPWW5BYXFRVUZMblZUNnlENll4bGtzRzlDc0dsbE1UQ3RMR3VBQThBMXdn?oc=5" target="_blank">The Tariff Threat to Apple Stock Vanished. Its Replacement Is a Bigger Worry.</a>&nbsp;&nbsp;<font color="#6f6f6f">Trefis</font>	https://news.google.com/rss/articles/CBMi3wFBVV95cUxQM3VaMGdlVHdIOTFVdmpxalo3UGxpMEVKUzkxYlpSVUNjNk5HWUUwQllZNXBwV19GQW1MWHRaOTZLWkV2c0JvQlgyQVJJYmFRWjNXM0VnakxZVVY5N3dsZGQwOU1FdVFMSWc2TzNiRGItckI0ZjlkM1B4TzhiMWtFZ1ExRjNKZ0d2UzY2YlBDWjJqVG10aW04UkNndVRVUXFoVU9TZ0JEaklza1ZkQm0zRmdVdjNPWW5BYXFRVUZMblZUNnlENll4bGtzRzlDc0dsbE1UQ3RMR3VBQThBMXdn?oc=5	0	general	2026-06-12 07:07:30	2026-06-12 07:31:04.618319
60	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Apple's AI News Underwhelms. Siri AI Release Concerns Persist. - Investor's Business Daily	<a href="https://news.google.com/rss/articles/CBMinAFBVV95cUxPWVVYQklOdzh3dm0zS0pJZU9saFI4OVd6d2JEanZxMm8wSnFTeVNZUm56YV93MDdaNjgtRnY1SUFNSnlXUU1KWWp1SW1KeVpCMTk0YTdHUnozYXZJU21sX1B4VDRpcWdqNFRBLThKMDFBb3RURDh5dEsyaHd4cHJ0bElTNHBaOXRuSTd0anM5Y09SQTlIeWFTVHltTFo?oc=5" target="_blank">Apple's AI News Underwhelms. Siri AI Release Concerns Persist.</a>&nbsp;&nbsp;<font color="#6f6f6f">Investor's Business Daily</font>	https://news.google.com/rss/articles/CBMinAFBVV95cUxPWVVYQklOdzh3dm0zS0pJZU9saFI4OVd6d2JEanZxMm8wSnFTeVNZUm56YV93MDdaNjgtRnY1SUFNSnlXUU1KWWp1SW1KeVpCMTk0YTdHUnozYXZJU21sX1B4VDRpcWdqNFRBLThKMDFBb3RURDh5dEsyaHd4cHJ0bElTNHBaOXRuSTd0anM5Y09SQTlIeWFTVHltTFo?oc=5	0	general	2026-06-09 20:04:00	2026-06-12 07:31:04.61955
61	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Apple Inc. (AAPL) Is A Top Stock In Ken Griffin’s Portfolio - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMikwFBVV95cUxON3N3cmh4eF94TWwzRlFPZmZDaXFJSkZFSVlNUExWTTNFOVBaRlNlUlRVSk5pV3VqTjcxYlZqU2Q2THo5OGs0eE1fMElMN0NodHdQQ2tMSUV4TmwtdW12NDFBNzlud3lad0Z0UnFmem45SFExNm9udTJmeUNqMk4xcl9GcE9lNkpZeG90NUZ1RXQ2a2s?oc=5" target="_blank">Apple Inc. (AAPL) Is A Top Stock In Ken Griffin’s Portfolio</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMikwFBVV95cUxON3N3cmh4eF94TWwzRlFPZmZDaXFJSkZFSVlNUExWTTNFOVBaRlNlUlRVSk5pV3VqTjcxYlZqU2Q2THo5OGs0eE1fMElMN0NodHdQQ2tMSUV4TmwtdW12NDFBNzlud3lad0Z0UnFmem45SFExNm9udTJmeUNqMk4xcl9GcE9lNkpZeG90NUZ1RXQ2a2s?oc=5	0	general	2026-06-11 17:30:42	2026-06-12 07:31:04.620797
62	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Why Apple Stock Is Sinking Today - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMimgFBVV95cUxONzkwc3FDWndCa045TmtLQXN1SThQODREWVhPRlp0LVNtSUpBajc3RFdlZmZZMjkyV28tM0RuRW9BQlpaMXZuNHpvUElhbXJUX0NkLXg0ZHFENzFnUUhqbWpiNnNoZlZiNXM2UllNVjRfTkhYN2VJNUxteTFualhvU2dvcmIyM3NGY2RIRWF5U28tUk5veTFCeldn?oc=5" target="_blank">Why Apple Stock Is Sinking Today</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMimgFBVV95cUxONzkwc3FDWndCa045TmtLQXN1SThQODREWVhPRlp0LVNtSUpBajc3RFdlZmZZMjkyV28tM0RuRW9BQlpaMXZuNHpvUElhbXJUX0NkLXg0ZHFENzFnUUhqbWpiNnNoZlZiNXM2UllNVjRfTkhYN2VJNUxteTFualhvU2dvcmIyM3NGY2RIRWF5U28tUk5veTFCeldn?oc=5	0	etf	2026-06-09 17:18:43	2026-06-12 07:31:04.621979
63	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Apple (AAPL) Declined Defies Strong Fundamentals - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMinwFBVV95cUxNMFY1Z09sd0FoQlZGdjdzTUZEeUY1Z29HUDY1NktnbU1pckZuU1pLMnlDRlNNWnBTWVpHb3pKcHN1b0NIMUNkOGFqYk5FZ3VfMTh5ck1DX21WQjU4dngwdllTdVgycGpKdlNIWE5HcktoUDJjRkVHREk5dWJZODVTNDY2RzkycnRtWmZsTENKclM2OGN0QTBvZUxLbTJfUU0?oc=5" target="_blank">Apple (AAPL) Declined Defies Strong Fundamentals</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMinwFBVV95cUxNMFY1Z09sd0FoQlZGdjdzTUZEeUY1Z29HUDY1NktnbU1pckZuU1pLMnlDRlNNWnBTWVpHb3pKcHN1b0NIMUNkOGFqYk5FZ3VfMTh5ck1DX21WQjU4dngwdllTdVgycGpKdlNIWE5HcktoUDJjRkVHREk5dWJZODVTNDY2RzkycnRtWmZsTENKclM2OGN0QTBvZUxLbTJfUU0?oc=5	0.21333333333333337	general	2026-06-10 13:08:04	2026-06-12 07:31:04.62443
64	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Why Apple (AAPL) Shares Are Sliding Today - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMimgFBVV95cUxObjlIZ3RBWG1HWnJhQnBZTjkzb2l3Ml9tVmhwZFlwejkydzhMeHp3SUR3eTE2dmpKRDBZZExoOVBFWmF6M3NaUW5RS1pnRmF0dmI0ckgteDFOMVhGTVBObHQ5STQ1T1BDa0l4OFlxVHR0b1Fyc0dTMGhCaFdzWjRFUWxhRURhQmlQeEJwU3R0RHFkREdLejl5WFF3?oc=5" target="_blank">Why Apple (AAPL) Shares Are Sliding Today</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMimgFBVV95cUxObjlIZ3RBWG1HWnJhQnBZTjkzb2l3Ml9tVmhwZFlwejkydzhMeHp3SUR3eTE2dmpKRDBZZExoOVBFWmF6M3NaUW5RS1pnRmF0dmI0ckgteDFOMVhGTVBObHQ5STQ1T1BDa0l4OFlxVHR0b1Fyc0dTMGhCaFdzWjRFUWxhRURhQmlQeEJwU3R0RHFkREdLejl5WFF3?oc=5	0	general	2026-06-10 02:22:00	2026-06-12 07:31:04.625673
65	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Barclays reiterates Apple stock Underweight rating after developer event - Investing.com	<a href="https://news.google.com/rss/articles/CBMizAFBVV95cUxOOVFXQ0FpVDhKWHBwWFpJQzlTOW5UdVVjSHRXUHZxdUVRU0g4cWtmb0ItZmlMZFh1N1ZOXzNtQzVPRlU5V1pYSzRCTWp4ZFdCSTEwSlFkWFF4bDNBRGtMQWdnNGpTaTU5Mm5CRkpCVWlJQmU1R2RLZ1FQdTlhWGJwc1dCRWhCSGVTVUlKQkdqU2ZmUnIweTZudmx5YjAyYnRTcUUzQUpKUUxESlVBcUVLSm03ck5pcUlUWnMtVXZfYThCSUQycjlXWWJLQlk?oc=5" target="_blank">Barclays reiterates Apple stock Underweight rating after developer event</a>&nbsp;&nbsp;<font color="#6f6f6f">Investing.com</font>	https://news.google.com/rss/articles/CBMizAFBVV95cUxOOVFXQ0FpVDhKWHBwWFpJQzlTOW5UdVVjSHRXUHZxdUVRU0g4cWtmb0ItZmlMZFh1N1ZOXzNtQzVPRlU5V1pYSzRCTWp4ZFdCSTEwSlFkWFF4bDNBRGtMQWdnNGpTaTU5Mm5CRkpCVWlJQmU1R2RLZ1FQdTlhWGJwc1dCRWhCSGVTVUlKQkdqU2ZmUnIweTZudmx5YjAyYnRTcUUzQUpKUUxESlVBcUVLSm03ck5pcUlUWnMtVXZfYThCSUQycjlXWWJLQlk?oc=5	0	general	2026-06-09 09:54:43	2026-06-12 07:31:04.626963
66	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Apple Inc. (AAPL) is Attracting Investor Attention: Here is What You Should Know - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMioAFBVV95cUxQNXJOYXQxaTlfSW0yVS1pT1I4VTBtM2lvRndBSmJCaHBMd2hJUHJDZWc3QzNRVmFxdEYyMzZSdnhTMjJjY093cERhTWppeHc2QXQ2ODA2eEdBU3c1cVd4VDFEY1A4Wnk3X3VHZFhzTnpnVlMxSDNDcVhyQlNVZ056NnQybGR1QjlCNXBYeFROaXVTNTc3bllFMVJ6dkRkbTdr?oc=5" target="_blank">Apple Inc. (AAPL) is Attracting Investor Attention: Here is What You Should Know</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMioAFBVV95cUxQNXJOYXQxaTlfSW0yVS1pT1I4VTBtM2lvRndBSmJCaHBMd2hJUHJDZWc3QzNRVmFxdEYyMzZSdnhTMjJjY093cERhTWppeHc2QXQ2ODA2eEdBU3c1cVd4VDFEY1A4Wnk3X3VHZFhzTnpnVlMxSDNDcVhyQlNVZ056NnQybGR1QjlCNXBYeFROaXVTNTc3bllFMVJ6dkRkbTdr?oc=5	0	general	2026-06-09 13:00:02	2026-06-12 07:31:05.090227
67	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Why Microsoft Stock Slipped Today - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMinwFBVV95cUxObjMwczFpemVlT0I5ejNLMzQzVXlwUGZ1WUQ2THhCQnoyTWFXVkNqRjIyMUVGQnh3T3ZxWktaeXhEdG9oZEZLTE1rSDJSZnQ0NDNUMTJFbTNvZHdzYVFHcnEzdU51SVVpR0xqZVc1cURkWE9pc3NLcm1ua25HbmlEeFZ0NmkwU3RqX0Fpdm5JTmRUS2tOdFhPSTR2Und3aU0?oc=5" target="_blank">Why Microsoft Stock Slipped Today</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMinwFBVV95cUxObjMwczFpemVlT0I5ejNLMzQzVXlwUGZ1WUQ2THhCQnoyTWFXVkNqRjIyMUVGQnh3T3ZxWktaeXhEdG9oZEZLTE1rSDJSZnQ0NDNUMTJFbTNvZHdzYVFHcnEzdU51SVVpR0xqZVc1cURkWE9pc3NLcm1ua25HbmlEeFZ0NmkwU3RqX0Fpdm5JTmRUS2tOdFhPSTR2Und3aU0?oc=5	0	general	2026-06-11 23:07:11	2026-06-12 07:31:05.092151
68	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Reassessing Microsoft (MSFT) Valuation After Recent Share Price Weakness - simplywall.st	<a href="https://news.google.com/rss/articles/CBMixwFBVV95cUxQcnd0TExIR2FVLU05a2l2UnNOaFZDLUN3dGlMWWhNcGJ3clJQV2dxRkx2RnFnX0FSWTg5Wk93R25TVVRadDVVVUc3eTZiQWJfbEJTbVIxTVF4MkwyZFY1N2lSR2VjMTN4a3FnU1ROaW1kX3ZmaGNSaEdNNUVJa1ZMeVNmVEpPbTRfWDZ5N2daX0U3OUVOZDVwY0ZqRGdLa0FMUExsQXU3N1VQUmw1ZVI1UFdoOGZTVEdFNGtUWHdJcC1FR09wVVBV0gHMAUFVX3lxTE82TTFobngtNXdyOFdQUWx2VjBodHVVS0pmdVRoQ2NfcFJYWWhUV1ZhOGlTa0ZJQWZRUVNXb2I5eENLY1kxZlV5X05DUnJvbkxGcVdTc29raGVBdml6RGxqOVJIMVliZVU3WjhOTTVVekE1RkRBWlAta1dIVzRsM1B3ZVh4T2pCQ3RwdWE1a01FNGExNUdOZEl2LUFHSFlmRXc2MDJ1Sjl6MFFRbnJZdDVmMXZCbzVYT0J0LWZVREQzRVY0WTVIelZTMWhrUA?oc=5" target="_blank">Reassessing Microsoft (MSFT) Valuation After Recent Share Price Weakness</a>&nbsp;&nbsp;<font color="#6f6f6f">simplywall.st</font>	https://news.google.com/rss/articles/CBMixwFBVV95cUxQcnd0TExIR2FVLU05a2l2UnNOaFZDLUN3dGlMWWhNcGJ3clJQV2dxRkx2RnFnX0FSWTg5Wk93R25TVVRadDVVVUc3eTZiQWJfbEJTbVIxTVF4MkwyZFY1N2lSR2VjMTN4a3FnU1ROaW1kX3ZmaGNSaEdNNUVJa1ZMeVNmVEpPbTRfWDZ5N2daX0U3OUVOZDVwY0ZqRGdLa0FMUExsQXU3N1VQUmw1ZVI1UFdoOGZTVEdFNGtUWHdJcC1FR09wVVBV0gHMAUFVX3lxTE82TTFobngtNXdyOFdQUWx2VjBodHVVS0pmdVRoQ2NfcFJYWWhUV1ZhOGlTa0ZJQWZRUVNXb2I5eENLY1kxZlV5X05DUnJvbkxGcVdTc29raGVBdml6RGxqOVJIMVliZVU3WjhOTTVVekE1RkRBWlAta1dIVzRsM1B3ZVh4T2pCQ3RwdWE1a01FNGExNUdOZEl2LUFHSFlmRXc2MDJ1Sjl6MFFRbnJZdDVmMXZCbzVYT0J0LWZVREQzRVY0WTVIelZTMWhrUA?oc=5	0	general	2026-06-11 14:34:19	2026-06-12 07:31:05.093588
69	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Microsoft Just Gave Investors 3 Dates They Can't Afford to Ignore - MarketBeat	<a href="https://news.google.com/rss/articles/CBMingFBVV95cUxPSUlSRmVuTlNfTHNOQlZ5dnVYd0RDaFE0OW5PdmhFdEJQR2o5X1lIMXZiU1RNZ0JTNGFHRGFHYXVWSmhoRjU2WjhQa1gwZTI3TTVhbTBOUzQ2emRyLWM2OUgxWDhsVjBudlprNWVMUFJhR0d0NUhEa05iOVZBYnpQcldvZkNsU1huZEwtTFdnUmJVVkNIR0dsbU83UzlVUQ?oc=5" target="_blank">Microsoft Just Gave Investors 3 Dates They Can't Afford to Ignore</a>&nbsp;&nbsp;<font color="#6f6f6f">MarketBeat</font>	https://news.google.com/rss/articles/CBMingFBVV95cUxPSUlSRmVuTlNfTHNOQlZ5dnVYd0RDaFE0OW5PdmhFdEJQR2o5X1lIMXZiU1RNZ0JTNGFHRGFHYXVWSmhoRjU2WjhQa1gwZTI3TTVhbTBOUzQ2emRyLWM2OUgxWDhsVjBudlprNWVMUFJhR0d0NUhEa05iOVZBYnpQcldvZkNsU1huZEwtTFdnUmJVVkNIR0dsbU83UzlVUQ?oc=5	0	general	2026-06-12 00:39:45	2026-06-12 07:31:05.095014
70	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Microsoft Stock Is Trailing the Market in 2026. Here's Why It's a Screaming Buy Right Now. - The Motley Fool	<a href="https://news.google.com/rss/articles/CBMimAFBVV95cUxPdHI1X3lzc0h0YVlEY1ZaNGJ0MTlzTHpaU3h0VUtSSlp6SGZKZUt2UVktb0J4OXJueEtUVlhFV0dqc2piZVJKMDhLOTUyWFhxeTNzN0NOb21WRW1tSmE5NFZ6V29oZEdKSEtkbWlUNlZjaXBQazNGM2twcWdSdGY3RlZ2c040MlliLWNGSU1xNU1sOEg2Tk1TYw?oc=5" target="_blank">Microsoft Stock Is Trailing the Market in 2026. Here's Why It's a Screaming Buy Right Now.</a>&nbsp;&nbsp;<font color="#6f6f6f">The Motley Fool</font>	https://news.google.com/rss/articles/CBMimAFBVV95cUxPdHI1X3lzc0h0YVlEY1ZaNGJ0MTlzTHpaU3h0VUtSSlp6SGZKZUt2UVktb0J4OXJueEtUVlhFV0dqc2piZVJKMDhLOTUyWFhxeTNzN0NOb21WRW1tSmE5NFZ6V29oZEdKSEtkbWlUNlZjaXBQazNGM2twcWdSdGY3RlZ2c040MlliLWNGSU1xNU1sOEg2Tk1TYw?oc=5	0	general	2026-06-11 16:20:00	2026-06-12 07:31:05.096536
71	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Microsoft Stock (MSFT) Opinions on Recent Earnings and AI Developments - Quiver Quantitative	<a href="https://news.google.com/rss/articles/CBMiqwFBVV95cUxOclhvSDUtblN4TUd3TGhMdExHaWI1Q1ZKamRlU01tTTF4NElDQzdFaXZYeXNncGlqUjhhYjgtMzloVmEtQW1McnRQQlNkYjlGMHJKdVlZNlhnOUhVR1RjdHRoYnQweEV0NUIxN2VjT1dzalN5dVkzallkS3RjSkwzSUJ0LVRWZ3FHd3gxeGJxZXRoZm9rbUFnMFZ3cEJ4eXAxejRiNnhCU3NuU2c?oc=5" target="_blank">Microsoft Stock (MSFT) Opinions on Recent Earnings and AI Developments</a>&nbsp;&nbsp;<font color="#6f6f6f">Quiver Quantitative</font>	https://news.google.com/rss/articles/CBMiqwFBVV95cUxOclhvSDUtblN4TUd3TGhMdExHaWI1Q1ZKamRlU01tTTF4NElDQzdFaXZYeXNncGlqUjhhYjgtMzloVmEtQW1McnRQQlNkYjlGMHJKdVlZNlhnOUhVR1RjdHRoYnQweEV0NUIxN2VjT1dzalN5dVkzallkS3RjSkwzSUJ0LVRWZ3FHd3gxeGJxZXRoZm9rbUFnMFZ3cEJ4eXAxejRiNnhCU3NuU2c?oc=5	0	earnings	2026-06-11 14:04:00	2026-06-12 07:31:05.097871
72	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	The Overlooked Tell: Microsoft Stock's Loudest Signal Is The One It Stopped Saying - Trefis	<a href="https://news.google.com/rss/articles/CBMi5gFBVV95cUxOaEN2c2JPNURXMVNnWTh4OVhvWGJ2QTZnRnAwRHlvWDRyX2dTbWl0S2FoQm1ZTEtFalZVZi00bmxqblgtMFhWV3hTRENSZlZHZzRaelQ2WkVKZjFaWDI1aW90NUNuX3pieWJCNlI2TkZkNGdXSkI5Q2tuWWk2ZFVRcGRabXRjaHI0YlBZTWswM0ZGTTVtTkJhaGo4VDRtUmpoYVc5WWJrbnAyTDJqOE05dEFGcDNKaV9GdWNBR0JOMnlFczJRUzQtbHppXzFYUjhKSVNGNm9OUWV5ekZqY01qUTQtbDlTQQ?oc=5" target="_blank">The Overlooked Tell: Microsoft Stock's Loudest Signal Is The One It Stopped Saying</a>&nbsp;&nbsp;<font color="#6f6f6f">Trefis</font>	https://news.google.com/rss/articles/CBMi5gFBVV95cUxOaEN2c2JPNURXMVNnWTh4OVhvWGJ2QTZnRnAwRHlvWDRyX2dTbWl0S2FoQm1ZTEtFalZVZi00bmxqblgtMFhWV3hTRENSZlZHZzRaelQ2WkVKZjFaWDI1aW90NUNuX3pieWJCNlI2TkZkNGdXSkI5Q2tuWWk2ZFVRcGRabXRjaHI0YlBZTWswM0ZGTTVtTkJhaGo4VDRtUmpoYVc5WWJrbnAyTDJqOE05dEFGcDNKaV9GdWNBR0JOMnlFczJRUzQtbHppXzFYUjhKSVNGNm9OUWV5ekZqY01qUTQtbDlTQQ?oc=5	0	etf	2026-06-12 07:04:20	2026-06-12 07:31:05.099288
73	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	What's Going On With Microsoft Stock Thursday? - Microsoft (NASDAQ:MSFT) - Benzinga	<a href="https://news.google.com/rss/articles/CBMivgFBVV95cUxNNHNWMlBnR2w5ZV9IbjlKTExQclp4WmxzTmxUUEN5V2VQTmtwMmxiZFhpS3h5OHluNkQ5WUd2OHFkZDBuazFVMzhrQ3pheHZPdUhKWV9sczVLSVlxTTRONXRtbkI4ek5aaV9lUFp5R01OcWVQLWhkTlB5OE5XbE1jSWpoeWF4MHZOZFJuQ01vWTVobnFpSXBucTNvTThCN3RieE9SZUNYcjFNNEt4OHNSNnNiTTRmUHJKUjJ3cFRB?oc=5" target="_blank">What's Going On With Microsoft Stock Thursday? - Microsoft (NASDAQ:MSFT)</a>&nbsp;&nbsp;<font color="#6f6f6f">Benzinga</font>	https://news.google.com/rss/articles/CBMivgFBVV95cUxNNHNWMlBnR2w5ZV9IbjlKTExQclp4WmxzTmxUUEN5V2VQTmtwMmxiZFhpS3h5OHluNkQ5WUd2OHFkZDBuazFVMzhrQ3pheHZPdUhKWV9sczVLSVlxTTRONXRtbkI4ek5aaV9lUFp5R01OcWVQLWhkTlB5OE5XbE1jSWpoeWF4MHZOZFJuQ01vWTVobnFpSXBucTNvTThCN3RieE9SZUNYcjFNNEt4OHNSNnNiTTRmUHJKUjJ3cFRB?oc=5	0	general	2026-06-11 16:37:06	2026-06-12 07:31:05.100683
74	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Microsoft Stock Trails Rivals in 2026. How to Play MSFT Stock Here. - Barchart.com	<a href="https://news.google.com/rss/articles/CBMirgFBVV95cUxOZkJzU2NlRGJmVFRyWjF2djkyWEhLZEtobk9iRGZFNzB2WmZZclhURGVSYWw2M3J1R3F0U3Zxck54OUpNNTlRYU5maWZLbUQwVkJ6QmxmQW9USjNGU1I1dTZWSklMQjZzX0tuYmh4TzdfbmM1Ti1TS0FoQl9jM3VOZTZUYlNibTRlNUI5T0pFX0o3X2N6YWpkQXBxVTcxZ0RYNHlRWE5sRXYtMWVtNFE?oc=5" target="_blank">Microsoft Stock Trails Rivals in 2026. How to Play MSFT Stock Here.</a>&nbsp;&nbsp;<font color="#6f6f6f">Barchart.com</font>	https://news.google.com/rss/articles/CBMirgFBVV95cUxOZkJzU2NlRGJmVFRyWjF2djkyWEhLZEtobk9iRGZFNzB2WmZZclhURGVSYWw2M3J1R3F0U3Zxck54OUpNNTlRYU5maWZLbUQwVkJ6QmxmQW9USjNGU1I1dTZWSklMQjZzX0tuYmh4TzdfbmM1Ti1TS0FoQl9jM3VOZTZUYlNibTRlNUI5T0pFX0o3X2N6YWpkQXBxVTcxZ0RYNHlRWE5sRXYtMWVtNFE?oc=5	0	general	2026-06-11 23:30:02	2026-06-12 07:31:05.102107
75	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Microsoft Stock Is Trailing the Market in 2026. Here's Why It's a Screaming Buy Right Now. - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMiowFBVV95cUxNRW85V3dIQWlEbjBtS0dLQS1wNlBoSzdLcVJLckpNbE1hbS1ITjVPSm50VnVwTkFrWjBzTEFkdnJuU1NDaWFWZmEwb3M4Rnl4UnpoOHJoVkxFVUZVVklNeTBLMUExVXRFRTJjYVpHd2xHZjBMRzRhamhTd1hJVDZfUjB5OUxpUlFENVZGd2NwT0ZiUWE1N3M4cm1BUzd2N0wtYXlj?oc=5" target="_blank">Microsoft Stock Is Trailing the Market in 2026. Here's Why It's a Screaming Buy Right Now.</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMiowFBVV95cUxNRW85V3dIQWlEbjBtS0dLQS1wNlBoSzdLcVJLckpNbE1hbS1ITjVPSm50VnVwTkFrWjBzTEFkdnJuU1NDaWFWZmEwb3M4Rnl4UnpoOHJoVkxFVUZVVklNeTBLMUExVXRFRTJjYVpHd2xHZjBMRzRhamhTd1hJVDZfUjB5OUxpUlFENVZGd2NwT0ZiUWE1N3M4cm1BUzd2N0wtYXlj?oc=5	0	general	2026-06-11 15:40:00	2026-06-12 07:31:05.103553
76	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Microsoft Stock Price Prediction: A New Record High on the Horizon? - 24/7 Wall St.	<a href="https://news.google.com/rss/articles/CBMirgFBVV95cUxOTVk1VWlnSEdRS3Y5Y1ZTWWtWWGRGTDI5cVBFV2JHM1JKb0xJb2tPNHFsRkIxd2JIRmhSTXZldHhubGQ1XzZtTXp1c3pEWXgzUXBUcUg0Z0ZjVk9FbFBicWY2elNiTjhaRWpFd1ZCQ0ZHNmZwbXVPSURPMU5VdWFCS3ZBWWVtalI0dWxNdGxWaTc1cHFYRE1RalZjUXg2SXp1SnM0Qjc2Qm5oWjBlV3c?oc=5" target="_blank">Microsoft Stock Price Prediction: A New Record High on the Horizon?</a>&nbsp;&nbsp;<font color="#6f6f6f">24/7 Wall St.</font>	https://news.google.com/rss/articles/CBMirgFBVV95cUxOTVk1VWlnSEdRS3Y5Y1ZTWWtWWGRGTDI5cVBFV2JHM1JKb0xJb2tPNHFsRkIxd2JIRmhSTXZldHhubGQ1XzZtTXp1c3pEWXgzUXBUcUg0Z0ZjVk9FbFBicWY2elNiTjhaRWpFd1ZCQ0ZHNmZwbXVPSURPMU5VdWFCS3ZBWWVtalI0dWxNdGxWaTc1cHFYRE1RalZjUXg2SXp1SnM0Qjc2Qm5oWjBlV3c?oc=5	0.26666666666666666	general	2026-06-10 16:36:37	2026-06-12 07:31:05.104946
77	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Microsoft Stock Pulls Back to Support – Smart Entry? - Trefis	<a href="https://news.google.com/rss/articles/CBMirwFBVV95cUxNVmUzYnFISVY5NGQwZHhaMVlOYkVXdTdJSHVwRGVtMHNfSHdpaFBHTURKem5lZWNqMUJmdFZWYTltZUVaX2dIZTNmdDBuSDQyR1UwRWhHcWR2ZUVkbG1VTlR0WGNrSGh1ajE2WFFMLUJkejJnbks2Y3RwelJUR2RFMzFBYmU5TkdoaXEzU0hFOHFYVEFYdmJXZlJxTGRLbXFkRlRKV0NPVnBxZGJlQzVV?oc=5" target="_blank">Microsoft Stock Pulls Back to Support – Smart Entry?</a>&nbsp;&nbsp;<font color="#6f6f6f">Trefis</font>	https://news.google.com/rss/articles/CBMirwFBVV95cUxNVmUzYnFISVY5NGQwZHhaMVlOYkVXdTdJSHVwRGVtMHNfSHdpaFBHTURKem5lZWNqMUJmdFZWYTltZUVaX2dIZTNmdDBuSDQyR1UwRWhHcWR2ZUVkbG1VTlR0WGNrSGh1ajE2WFFMLUJkejJnbks2Y3RwelJUR2RFMzFBYmU5TkdoaXEzU0hFOHFYVEFYdmJXZlJxTGRLbXFkRlRKV0NPVnBxZGJlQzVV?oc=5	0	general	2026-06-11 08:31:25	2026-06-12 07:31:05.10647
78	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Why Microsoft Stock Is Sinking Today - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMinwFBVV95cUxNUmVtaXdqd19ZMUg0YzM2MVdWMzNoQ21RdlhlX0htM0xSSENNQ0l2Q0VhZWFVNWdTZ3hhWVg3V3RBQk40dUlWMjFLb2V2STd1RHFKLVZYcUJUb3lCZHFrTVoyMXJRbkNsRWpQbHZBSkFWM1NEOEs0UFV4SVJzaVloa3g4a25OUXJGLVVPM1NKcHlGajZEazJGM1hsQVNpRkk?oc=5" target="_blank">Why Microsoft Stock Is Sinking Today</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMinwFBVV95cUxNUmVtaXdqd19ZMUg0YzM2MVdWMzNoQ21RdlhlX0htM0xSSENNQ0l2Q0VhZWFVNWdTZ3hhWVg3V3RBQk40dUlWMjFLb2V2STd1RHFKLVZYcUJUb3lCZHFrTVoyMXJRbkNsRWpQbHZBSkFWM1NEOEs0UFV4SVJzaVloa3g4a25OUXJGLVVPM1NKcHlGajZEazJGM1hsQVNpRkk?oc=5	0	general	2026-06-09 18:53:24	2026-06-12 07:31:05.107932
79	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Is Microsoft Stock Too Cheap To Ignore? - Trefis	<a href="https://news.google.com/rss/articles/CBMioAFBVV95cUxNOFR4OXFUS1hCWE94QmRPbkg4bkk3Uk5mQVRyUXdzX1ExTlZHTEd4YU93VG1PVENVZm4zR3FQSFpRdXhTdXptc2tIeXBRQ1BGR1hjbGV4TnpJb0xwLURBcU9sOEJOTUhmT3R0U1FQQ1ZzZmhyeFljXzA5S0x0TVI5d1pnWmJKbGhWNUt6ZzR1NHJ1SFZ3SldNRy1QRHRTT1BI?oc=5" target="_blank">Is Microsoft Stock Too Cheap To Ignore?</a>&nbsp;&nbsp;<font color="#6f6f6f">Trefis</font>	https://news.google.com/rss/articles/CBMioAFBVV95cUxNOFR4OXFUS1hCWE94QmRPbkg4bkk3Uk5mQVRyUXdzX1ExTlZHTEd4YU93VG1PVENVZm4zR3FQSFpRdXhTdXptc2tIeXBRQ1BGR1hjbGV4TnpJb0xwLURBcU9sOEJOTUhmT3R0U1FQQ1ZzZmhyeFljXzA5S0x0TVI5d1pnWmJKbGhWNUt6ZzR1NHJ1SFZ3SldNRy1QRHRTT1BI?oc=5	0	general	2026-06-10 15:05:09	2026-06-12 07:31:05.10956
80	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Is Microsoft (MSFT) One of the Best AI Stocks to Buy in June? - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMilgFBVV95cUxPeGdsb3Q0RmlRZldLVksyeElSeUppcWt0SGgwVnJnMVc0Y1BKbm5BeVNHNDVyWjlCZS1RR3B0ajd3RnpoYUFrcXgtYUdQMG50cDk5RTFkS0RvSEY0ZEM5VU94MWlfTUQ0NC1rT3lDQTUtZGY1T2YwVG4yUkFNSWFCQV92dmF1cTNXUklUemN3TFI1bExUa0E?oc=5" target="_blank">Is Microsoft (MSFT) One of the Best AI Stocks to Buy in June?</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMilgFBVV95cUxPeGdsb3Q0RmlRZldLVksyeElSeUppcWt0SGgwVnJnMVc0Y1BKbm5BeVNHNDVyWjlCZS1RR3B0ajd3RnpoYUFrcXgtYUdQMG50cDk5RTFkS0RvSEY0ZEM5VU94MWlfTUQ0NC1rT3lDQTUtZGY1T2YwVG4yUkFNSWFCQV92dmF1cTNXUklUemN3TFI1bExUa0E?oc=5	0	general	2026-06-09 13:39:11	2026-06-12 07:31:05.110951
81	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Microsoft Corporation (MSFT) Is A Top AI Stock In Ken Griffin’s Portfolio - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMinwFBVV95cUxNNzJWQlVIWXRRMHNONFZabGxGLXhNTFVYOXFkZGM3VVFnX2lNa1N6R2UzSkM3VFkxRkpTZGx2ejNLamU4bEFRNXFQcjlvcmhGOW81Mk8yUnpXRGFkU3pFYnExbVNHUHdSNnZvNjFkalYwRVVsUkFyWEE0YWI2WktyOV9IcGRpdWxIMWVNTXUyX1VrdWpjM0RaQWFYVV84VTg?oc=5" target="_blank">Microsoft Corporation (MSFT) Is A Top AI Stock In Ken Griffin’s Portfolio</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMinwFBVV95cUxNNzJWQlVIWXRRMHNONFZabGxGLXhNTFVYOXFkZGM3VVFnX2lNa1N6R2UzSkM3VFkxRkpTZGx2ejNLamU4bEFRNXFQcjlvcmhGOW81Mk8yUnpXRGFkU3pFYnExbVNHUHdSNnZvNjFkalYwRVVsUkFyWEE0YWI2WktyOV9IcGRpdWxIMWVNTXUyX1VrdWpjM0RaQWFYVV84VTg?oc=5	0	general	2026-06-11 17:31:05	2026-06-12 07:31:05.112399
82	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Here’s why Microsoft Corporation (MSFT) is one of the Best Forever Stock to Buy - Yahoo! Finance Canada	<a href="https://news.google.com/rss/articles/CBMiiwFBVV95cUxPZF91MERoUHA1M0JiUVVNbExmUUxOYmh1aWcxVEFuN0dRamxCVEN0aE83UzRTMDJXblBfbzNzUUZhbFgyTV93OUtadG1BWjV0LTgtTEdjUjRETjlDT2E0MkFhQXBNVVVMOTFpMUkyOXNnYnp6RjFwdkViQTd3eHVHZHc5ald3WlV4eDBj?oc=5" target="_blank">Here’s why Microsoft Corporation (MSFT) is one of the Best Forever Stock to Buy</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo! Finance Canada</font>	https://news.google.com/rss/articles/CBMiiwFBVV95cUxPZF91MERoUHA1M0JiUVVNbExmUUxOYmh1aWcxVEFuN0dRamxCVEN0aE83UzRTMDJXblBfbzNzUUZhbFgyTV93OUtadG1BWjV0LTgtTEdjUjRETjlDT2E0MkFhQXBNVVVMOTFpMUkyOXNnYnp6RjFwdkViQTd3eHVHZHc5ald3WlV4eDBj?oc=5	0	general	2026-06-12 03:25:00	2026-06-12 07:31:05.113816
83	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Here’s Guinness Global Equity Income Fund’s Views on Microsoft Corporation (MSFT) - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMioAFBVV95cUxQRjR1dUQzdEVQdjNDLXNkOVdpa2F1d2lEazZJUU5oUWVmaERTQWp6Z2VCblF6UF9Tak8xb1U5aHIyWXJGeVRYYTlVd1NtMEp2dGRfZ1E0M25SNUZneVdGbHNzZlBYZmxoTTdrVDlwaWRyME9lVlhUVXcyc1NHN1Nhb2t5UHlSaVZqelBsWDJfRjl6X1lWY2tmSXV4YWVDZWdC?oc=5" target="_blank">Here’s Guinness Global Equity Income Fund’s Views on Microsoft Corporation (MSFT)</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMioAFBVV95cUxQRjR1dUQzdEVQdjNDLXNkOVdpa2F1d2lEazZJUU5oUWVmaERTQWp6Z2VCblF6UF9Tak8xb1U5aHIyWXJGeVRYYTlVd1NtMEp2dGRfZ1E0M25SNUZneVdGbHNzZlBYZmxoTTdrVDlwaWRyME9lVlhUVXcyc1NHN1Nhb2t5UHlSaVZqelBsWDJfRjl6X1lWY2tmSXV4YWVDZWdC?oc=5	0	general	2026-06-11 15:36:59	2026-06-12 07:31:05.115228
84	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Is Microsoft Stock Too Cheap To Ignore? - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMingFBVV95cUxQZUFQajA0NzFUTjRzUWhmTWlvWFl1eUtoQVpOX3lXRC1MdGtIcTJoMVR5VjJIaHU1Umh1bjNjbEJPVGxFSlJVbnVaRVpMaFZqVXpnMmhwVGt3VDVlMHZrN1hKWmNnbEtwSTU3RmZuQkFJN2VZbl82YTZkb1dGRVVKdjRPRFFCTlY1ekxMX01mNEdobXlRbU0yOXRLX2Q1QQ?oc=5" target="_blank">Is Microsoft Stock Too Cheap To Ignore?</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMingFBVV95cUxQZUFQajA0NzFUTjRzUWhmTWlvWFl1eUtoQVpOX3lXRC1MdGtIcTJoMVR5VjJIaHU1Umh1bjNjbEJPVGxFSlJVbnVaRVpMaFZqVXpnMmhwVGt3VDVlMHZrN1hKWmNnbEtwSTU3RmZuQkFJN2VZbl82YTZkb1dGRVVKdjRPRFFCTlY1ekxMX01mNEdobXlRbU0yOXRLX2Q1QQ?oc=5	0	general	2026-06-10 15:05:54	2026-06-12 07:31:05.116644
85	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	Microsoft Corp (NASDAQ:MSFT) Presents a Classic GARP Opportunity with Affordable Growth - ChartMill	<a href="https://news.google.com/rss/articles/CBMi0gFBVV95cUxPclI3aUNFOXlnVlhHTEFYV3k3SkJ1NDdmZm14Sm1KZm5ITDhwaWoyWWNaOEYyRWdycVRIa09RWFhmT1RSZUF0NlYyWWxoNnN6al9hMkZQNGdRQ0hqWkdYYWJpMEE4UGJXc2JXWmhzNW9mcXFJQnRTOGMtUVNHYVNvNVByZjlKMVliMzI3bUZKME1Ud0tRVjdOaWtwbjR3YXIyUXp5WldWTkFUaDU4TE5NLVFjdS1zNWFRM2ZaeXkwRi0yTFZHdWVEWUFOdjdueFlLZUE?oc=5" target="_blank">Microsoft Corp (NASDAQ:MSFT) Presents a Classic GARP Opportunity with Affordable Growth</a>&nbsp;&nbsp;<font color="#6f6f6f">ChartMill</font>	https://news.google.com/rss/articles/CBMi0gFBVV95cUxPclI3aUNFOXlnVlhHTEFYV3k3SkJ1NDdmZm14Sm1KZm5ITDhwaWoyWWNaOEYyRWdycVRIa09RWFhmT1RSZUF0NlYyWWxoNnN6al9hMkZQNGdRQ0hqWkdYYWJpMEE4UGJXc2JXWmhzNW9mcXFJQnRTOGMtUVNHYVNvNVByZjlKMVliMzI3bUZKME1Ud0tRVjdOaWtwbjR3YXIyUXp5WldWTkFUaDU4TE5NLVFjdS1zNWFRM2ZaeXkwRi0yTFZHdWVEWUFOdjdueFlLZUE?oc=5	0.26666666666666666	general	2026-06-09 10:40:29	2026-06-12 07:31:05.118011
86	10	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	Prominent Tech Investor: 'When We Were Buying Nvidia in 2023, We Were Paying 4 Times Earnings' - 24/7 Wall St.	<a href="https://news.google.com/rss/articles/CBMizwFBVV95cUxPZ2p3VHl6NFhlZ1dZYXZnQ1k5TGVvNmpPckpqdS1qR0hVa29EbE90UlNWTkRrYXpNUE9VMGZPN2tQX0hBcWM1bUVpenhjSEx1a3Fib0dMTUxUdlR1aTVSbjRPU1RLaXRHcksyMUZ1cEJHR3pIT0NPdzVaOUZZUkkteEVZUUZZX2dmY3pJTmpJX3Y4aEtPMS15TV9JbUJNUk9FbDlvRGhQYjBsaFI3N2pjOC0yTUFaVFQ1a3FBOWhSOERsd3pabUtvSzZvUW02VTg?oc=5" target="_blank">Prominent Tech Investor: 'When We Were Buying Nvidia in 2023, We Were Paying 4 Times Earnings'</a>&nbsp;&nbsp;<font color="#6f6f6f">24/7 Wall St.</font>	https://news.google.com/rss/articles/CBMizwFBVV95cUxPZ2p3VHl6NFhlZ1dZYXZnQ1k5TGVvNmpPckpqdS1qR0hVa29EbE90UlNWTkRrYXpNUE9VMGZPN2tQX0hBcWM1bUVpenhjSEx1a3Fib0dMTUxUdlR1aTVSbjRPU1RLaXRHcksyMUZ1cEJHR3pIT0NPdzVaOUZZUkkteEVZUUZZX2dmY3pJTmpJX3Y4aEtPMS15TV9JbUJNUk9FbDlvRGhQYjBsaFI3N2pjOC0yTUFaVFQ1a3FBOWhSOERsd3pabUtvSzZvUW02VTg?oc=5	0	earnings	2026-06-09 18:54:30	2026-06-12 07:31:05.641069
87	10	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	Nvidia (NVDA) Stock: Can Robotics Spark a New Rally? - Barron's	<a href="https://news.google.com/rss/articles/CBMicEFVX3lxTE4zcjNSOVFEWENrenoxTUE0a3VEaF9zSFdaZnNwYXNZSU9Pa0FyMnpoVHpSdnNhVHR3SnlpV2RTblBhMHhOS2J4dkI2eWpTWlROckQ1Q2swUW5odEhKYjBKTFNRajlxUWU0dzRoQkVld2U?oc=5" target="_blank">Nvidia (NVDA) Stock: Can Robotics Spark a New Rally?</a>&nbsp;&nbsp;<font color="#6f6f6f">Barron's</font>	https://news.google.com/rss/articles/CBMicEFVX3lxTE4zcjNSOVFEWENrenoxTUE0a3VEaF9zSFdaZnNwYXNZSU9Pa0FyMnpoVHpSdnNhVHR3SnlpV2RTblBhMHhOS2J4dkI2eWpTWlROckQ1Q2swUW5odEhKYjBKTFNRajlxUWU0dzRoQkVld2U?oc=5	0	general	2026-06-11 14:36:00	2026-06-12 07:31:05.648594
88	10	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	NVIDIA Corp. (NVDA) Is A Top AI Stock In Ken Griffin’s Portfolio - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMikgFBVV95cUxQV01BRzUyZWtsY1BYQ1Iza1lZNVczSnJCb0huVmNZODQ0YjY4VjFiTUVwa3BLcmNWdDZvUjd4OWpTVEg0MTZDaEhOajZkSl9kXzRBbFFuSUtqVEJya3Rpdjk5c2NVclotUFdiZ3RsVTMyUDdNMko4VzVOUjhqaDh3aDlqaGJwaEtqMWZTa1Fkakp0QQ?oc=5" target="_blank">NVIDIA Corp. (NVDA) Is A Top AI Stock In Ken Griffin’s Portfolio</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMikgFBVV95cUxQV01BRzUyZWtsY1BYQ1Iza1lZNVczSnJCb0huVmNZODQ0YjY4VjFiTUVwa3BLcmNWdDZvUjd4OWpTVEg0MTZDaEhOajZkSl9kXzRBbFFuSUtqVEJya3Rpdjk5c2NVclotUFdiZ3RsVTMyUDdNMko4VzVOUjhqaDh3aDlqaGJwaEtqMWZTa1Fkakp0QQ?oc=5	0	general	2026-06-11 17:30:12	2026-06-12 07:31:05.64999
89	10	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	NVIDIA’s Outlook Gains Momentum: Stock Price to Follow - MarketBeat	<a href="https://news.google.com/rss/articles/CBMilAFBVV95cUxOUURXYmtFaGFSUTNOdGRwTmpSLXpONnVPbkJSckdRcUhJRWtxdTdwei1CUUZya3dFNVY5ZUd0dUNYcGpnaFhUeGdva2VlMkZRdW1Xdy0wem5VTTZMOWV2TU80R3N1MC05Y3hnbTlTb1lWcXAwQlRLZ0FVQW9EekNSRU0xeWFiQU1fT0lmellQU2ZBTjlK?oc=5" target="_blank">NVIDIA’s Outlook Gains Momentum: Stock Price to Follow</a>&nbsp;&nbsp;<font color="#6f6f6f">MarketBeat</font>	https://news.google.com/rss/articles/CBMilAFBVV95cUxOUURXYmtFaGFSUTNOdGRwTmpSLXpONnVPbkJSckdRcUhJRWtxdTdwei1CUUZya3dFNVY5ZUd0dUNYcGpnaFhUeGdva2VlMkZRdW1Xdy0wem5VTTZMOWV2TU80R3N1MC05Y3hnbTlTb1lWcXAwQlRLZ0FVQW9EekNSRU0xeWFiQU1fT0lmellQU2ZBTjlK?oc=5	0	general	2026-06-11 23:37:30	2026-06-12 07:31:05.651459
90	10	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	Is NVIDIA Stock’s New CPU Story Big Enough to Cover Its China Silence? - Trefis	<a href="https://news.google.com/rss/articles/CBMiyAFBVV95cUxOWGtjaWZRcUxvTVljY0FMVTIxVEFFSGlsR3o3RkZMTnBJWjJxeWZlbVFTMTJ4eFU5UVFnRkZVancxTXRBU05zRjlwSWpiMGcyYXI1aGt5RG1LLWdBMUFXeWNNY3E5U2tINE55RnQ0M2VkMVpyNFZQYTZIU1VyQk5NU0hDb0VpTjkxQkVLMTVjUlVMemJMbUNSTmQzTDJzVFZ4cmVlMGludV90c0hGRkJjaUxaa3RWVEIzamdEbXhhMXplZDY0Zl9SNg?oc=5" target="_blank">Is NVIDIA Stock’s New CPU Story Big Enough to Cover Its China Silence?</a>&nbsp;&nbsp;<font color="#6f6f6f">Trefis</font>	https://news.google.com/rss/articles/CBMiyAFBVV95cUxOWGtjaWZRcUxvTVljY0FMVTIxVEFFSGlsR3o3RkZMTnBJWjJxeWZlbVFTMTJ4eFU5UVFnRkZVancxTXRBU05zRjlwSWpiMGcyYXI1aGt5RG1LLWdBMUFXeWNNY3E5U2tINE55RnQ0M2VkMVpyNFZQYTZIU1VyQk5NU0hDb0VpTjkxQkVLMTVjUlVMemJMbUNSTmQzTDJzVFZ4cmVlMGludV90c0hGRkJjaUxaa3RWVEIzamdEbXhhMXplZDY0Zl9SNg?oc=5	0	general	2026-06-11 13:53:17	2026-06-12 07:31:05.652796
91	10	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	Prediction: Nvidia Set to Hit $250 on This Date - 24/7 Wall St.	<a href="https://news.google.com/rss/articles/CBMikwFBVV95cUxQSU10eHl4NUZKRy1GbmJWQVRxQ2FNaEtGazQyZnd4dzQ1T1JfY3FsUDJ1V0dCeFd5VnlOX3IxQk96cThEZklfZUJFRFY4ZWd1MWFJTmUzTTI5REg2ZlhqOW5rakFIVjVLRmZlWFRfTDdoNUl2d094S0t2ZmMyclRqR04wWThMODg5LW0tWUlYUlpfZXM?oc=5" target="_blank">Prediction: Nvidia Set to Hit $250 on This Date</a>&nbsp;&nbsp;<font color="#6f6f6f">24/7 Wall St.</font>	https://news.google.com/rss/articles/CBMikwFBVV95cUxQSU10eHl4NUZKRy1GbmJWQVRxQ2FNaEtGazQyZnd4dzQ1T1JfY3FsUDJ1V0dCeFd5VnlOX3IxQk96cThEZklfZUJFRFY4ZWd1MWFJTmUzTTI5REg2ZlhqOW5rakFIVjVLRmZlWFRfTDdoNUl2d094S0t2ZmMyclRqR04wWThMODg5LW0tWUlYUlpfZXM?oc=5	0	general	2026-06-11 16:41:39	2026-06-12 07:31:05.654194
92	10	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	NVDA's quiet 0.57 P/C is the tell - Moomoo	<a href="https://news.google.com/rss/articles/CBMikAFBVV95cUxOb1dTMnV2R2VxNUIzdEFIWmpiVWYzSWlmUm4xSU5iTlptOHZxVHR3TXlHVVg2R2RyNWstdmlwVEQ0b0xkUnJxUy1yWXIzS1gwWEt1ZFVFbEhGUXNCWi1CUmRBUXRQRVk1SDZIeXctV283ZHR2Q2hHb0xSa2tEQjExRWxzaXdad3gwN2ltSjMtSXM?oc=5" target="_blank">NVDA's quiet 0.57 P/C is the tell</a>&nbsp;&nbsp;<font color="#6f6f6f">Moomoo</font>	https://news.google.com/rss/articles/CBMikAFBVV95cUxOb1dTMnV2R2VxNUIzdEFIWmpiVWYzSWlmUm4xSU5iTlptOHZxVHR3TXlHVVg2R2RyNWstdmlwVEQ0b0xkUnJxUy1yWXIzS1gwWEt1ZFVFbEhGUXNCWi1CUmRBUXRQRVk1SDZIeXctV283ZHR2Q2hHb0xSa2tEQjExRWxzaXdad3gwN2ltSjMtSXM?oc=5	0	general	2026-06-12 06:55:04	2026-06-12 07:31:05.655513
93	10	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	SpaceX Just Announced Fantastic News to Nvidia Stock Investors - The Motley Fool	<a href="https://news.google.com/rss/articles/CBMimAFBVV95cUxOcWRTNnl5enFSMVZia1hQZVM0UUdqN0Nfa2RCV2lYcVMxdldjYjBPU1llWVkySzhBZFdLUmh6YW1DSXphR3kzeDc5ZnFVOFFOck9Va2dUbTd2QkpUV25IUmExN0U5WjNidC1KVmNEVnUtVi1aNThwWmwyZ0paNHVoWEZSTzZxS0RjeHlueEh1SVV5ZUVlTnRTUQ?oc=5" target="_blank">SpaceX Just Announced Fantastic News to Nvidia Stock Investors</a>&nbsp;&nbsp;<font color="#6f6f6f">The Motley Fool</font>	https://news.google.com/rss/articles/CBMimAFBVV95cUxOcWRTNnl5enFSMVZia1hQZVM0UUdqN0Nfa2RCV2lYcVMxdldjYjBPU1llWVkySzhBZFdLUmh6YW1DSXphR3kzeDc5ZnFVOFFOck9Va2dUbTd2QkpUV25IUmExN0U5WjNidC1KVmNEVnUtVi1aNThwWmwyZ0paNHVoWEZSTzZxS0RjeHlueEh1SVV5ZUVlTnRTUQ?oc=5	0	general	2026-06-10 21:25:00	2026-06-12 07:31:05.656883
94	10	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	NVIDIA Corporation (NVDA): A Forever Stock to Buy amid Growing Business Ties in Korea - Yahoo Finance UK	<a href="https://news.google.com/rss/articles/CBMijwFBVV95cUxORzEtUEJ2ZnFybjRheHRCQzRnSl8xVm9Vc011QWtfWnMyWGZwVFBVbE90TGpTOUFtRkhiUGdzLVNmTWZwVW00OWtMNHZscFRTMEtjSUpmTV85ZjhVc09SalUzWlRCUkptQjAxRlFTdTl1LVNPMVR3aFBFYUpUcTNsa081SkRRZTkxUWJsN19HMA?oc=5" target="_blank">NVIDIA Corporation (NVDA): A Forever Stock to Buy amid Growing Business Ties in Korea</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance UK</font>	https://news.google.com/rss/articles/CBMijwFBVV95cUxORzEtUEJ2ZnFybjRheHRCQzRnSl8xVm9Vc011QWtfWnMyWGZwVFBVbE90TGpTOUFtRkhiUGdzLVNmTWZwVW00OWtMNHZscFRTMEtjSUpmTV85ZjhVc09SalUzWlRCUkptQjAxRlFTdTl1LVNPMVR3aFBFYUpUcTNsa081SkRRZTkxUWJsN19HMA?oc=5	0	general	2026-06-12 03:25:00	2026-06-12 07:31:05.658252
95	10	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	NVDA: Calls Lean, P/C Crashing Into 0.57 - Moomoo	<a href="https://news.google.com/rss/articles/CBMilwFBVV95cUxPd2VuN2Jjc043alEycjBpdEEwYkwwWDl1c2pFUGNjVnJRQUM4S3FmOTVxaTI1cmhKNFpQRHN4Mm83aUZDWS1KYXVKSloxdUhWZlh3bkZESTA5VEkxcG1Jd0xlSjZocjZzcW9IbmxLWjNTdmdILS0telVIVXgtd3ltV19sMmd2VDY5ZnFlUXN0eWs2QjM1UjRz?oc=5" target="_blank">NVDA: Calls Lean, P/C Crashing Into 0.57</a>&nbsp;&nbsp;<font color="#6f6f6f">Moomoo</font>	https://news.google.com/rss/articles/CBMilwFBVV95cUxPd2VuN2Jjc043alEycjBpdEEwYkwwWDl1c2pFUGNjVnJRQUM4S3FmOTVxaTI1cmhKNFpQRHN4Mm83aUZDWS1KYXVKSloxdUhWZlh3bkZESTA5VEkxcG1Jd0xlSjZocjZzcW9IbmxLWjNTdmdILS0telVIVXgtd3ltV19sMmd2VDY5ZnFlUXN0eWs2QjM1UjRz?oc=5	0	general	2026-06-12 05:46:56	2026-06-12 07:31:05.659567
96	5	""NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"" - Google News	Nvidia Stock Trades Cheaper Than the S&P 500, and Looks Even More Like a Value Play - Barron's	<a href="https://news.google.com/rss/articles/CBMigAFBVV95cUxOZ0sxQXFITktEdFBTMFdPbjlrSnBQQm80UGJzRC0zTEJneHUyUXllNkd2aTZPWWx0ZU8wSk1EelFjOWE0ZDRkX3habFdmNk5welRzXzF0Tjd0dGtiUXB2emhLc0ZSUW02d0tiNVJUTEd5RkJyQndjVnpGc0xwNk44SA?oc=5" target="_blank">Nvidia Stock Trades Cheaper Than the S&amp;P 500, and Looks Even More Like a Value Play</a>&nbsp;&nbsp;<font color="#6f6f6f">Barron's</font>	https://news.google.com/rss/articles/CBMigAFBVV95cUxOZ0sxQXFITktEdFBTMFdPbjlrSnBQQm80UGJzRC0zTEJneHUyUXllNkd2aTZPWWx0ZU8wSk1EelFjOWE0ZDRkX3habFdmNk5welRzXzF0Tjd0dGtiUXB2emhLc0ZSUW02d0tiNVJUTEd5RkJyQndjVnpGc0xwNk44SA?oc=5	0	general	2026-06-10 20:32:00	2026-06-12 07:31:05.660823
97	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Does Apple Stock Have More Upside? - Trefis	<a href="https://news.google.com/rss/articles/CBMimgFBVV95cUxPaEpLczNNa2FlN21FOXlBc18wTDItTVdsWGZnSngyUkc1NHVveWRCVUVscExXREpYZEZidEpOaTdSdURyQ3FOeWVsdVM2NURITFV5dXduSENXWHNILWxBd0hXeTlyUnZCa25CREZPTmliZTJpSlpEVVgwV2ZHQlFLWEdIN2pDZk1QVkJRUW54WHdlRlFIbnRLWTZn?oc=5" target="_blank">Does Apple Stock Have More Upside?</a>&nbsp;&nbsp;<font color="#6f6f6f">Trefis</font>	https://news.google.com/rss/articles/CBMimgFBVV95cUxPaEpLczNNa2FlN21FOXlBc18wTDItTVdsWGZnSngyUkc1NHVveWRCVUVscExXREpYZEZidEpOaTdSdURyQ3FOeWVsdVM2NURITFV5dXduSENXWHNILWxBd0hXeTlyUnZCa25CREZPTmliZTJpSlpEVVgwV2ZHQlFLWEdIN2pDZk1QVkJRUW54WHdlRlFIbnRLWTZn?oc=5	0	general	2026-06-11 22:50:21	2026-06-12 07:33:22.979109
98	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Morgan Stanley revamps Apple stock target after key event - thestreet.com	<a href="https://news.google.com/rss/articles/CBMiiwFBVV95cUxPdDUyTGRNV1YxNWI0Nzk5WUYtbnpNbkdhU3ZZUEQ2MkxPaWlNNHlQdzhNM25XNF84TUhaM2J0dGVvMEotMmwya3NfSy1tRE9kSVVlVEdPUC1HQWsxclhqSUliTmotV3lVRExMTGVDM1ZQVUxBZ1NWMWtZLWVZUjFjNHZKc3BQMkNnVXd3?oc=5" target="_blank">Morgan Stanley revamps Apple stock target after key event</a>&nbsp;&nbsp;<font color="#6f6f6f">thestreet.com</font>	https://news.google.com/rss/articles/CBMiiwFBVV95cUxPdDUyTGRNV1YxNWI0Nzk5WUYtbnpNbkdhU3ZZUEQ2MkxPaWlNNHlQdzhNM25XNF84TUhaM2J0dGVvMEotMmwya3NfSy1tRE9kSVVlVEdPUC1HQWsxclhqSUliTmotV3lVRExMTGVDM1ZQVUxBZ1NWMWtZLWVZUjFjNHZKc3BQMkNnVXd3?oc=5	0	general	2026-06-10 19:07:00	2026-06-12 07:33:22.983804
99	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Pay Less, Gain More: DELL Tops Apple Stock - Trefis	<a href="https://news.google.com/rss/articles/CBMipgFBVV95cUxOX1BGd01Eck9jOUhkN2Q0UVdGNXNOYXlpU2drTlhvRkpTMUxfaENhMHV2cmpkZ080eVZWQnJrb2xvcWJKUnZTNXBXNzVMcUtWMDFsTFVLVXNTMkNLM2w4Ui1nVHlwZzlzbVBTSk95cUxmRWhzQ2c0Sjl0NjhvY0xyMFYtVEx5cWJTMWg4bVBmNmdVRUhkUGpRbnFjZG4yQWRyMnkweklB?oc=5" target="_blank">Pay Less, Gain More: DELL Tops Apple Stock</a>&nbsp;&nbsp;<font color="#6f6f6f">Trefis</font>	https://news.google.com/rss/articles/CBMipgFBVV95cUxOX1BGd01Eck9jOUhkN2Q0UVdGNXNOYXlpU2drTlhvRkpTMUxfaENhMHV2cmpkZ080eVZWQnJrb2xvcWJKUnZTNXBXNzVMcUtWMDFsTFVLVXNTMkNLM2w4Ui1nVHlwZzlzbVBTSk95cUxmRWhzQ2c0Sjl0NjhvY0xyMFYtVEx5cWJTMWg4bVBmNmdVRUhkUGpRbnFjZG4yQWRyMnkweklB?oc=5	0.21333333333333337	general	2026-06-10 10:29:46	2026-06-12 07:33:22.988518
100	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Apple Stock Capital Return Hits $508 Bil - Trefis	<a href="https://news.google.com/rss/articles/CBMiogFBVV95cUxQUElOWm5OSV8wdlE2RnlDZTdIdEtWQ1RkcGkzdGxwdi1UYU9RbDh1VjlFaXB6QzQ3UDV0N21CLUYxTTYtUTk3cUt4RlMxSkF6OE1hR2g3b2c5bzMxT0V5MUh3QWxuQ1BhY2RIalRIajBiUnBITTl0S3g0QVNzV21PVXZ6WnJobTdLYWhrRmNjZ1MwY1FnZEJ1blhZLUhha3VvY1E?oc=5" target="_blank">Apple Stock Capital Return Hits $508 Bil</a>&nbsp;&nbsp;<font color="#6f6f6f">Trefis</font>	https://news.google.com/rss/articles/CBMiogFBVV95cUxQUElOWm5OSV8wdlE2RnlDZTdIdEtWQ1RkcGkzdGxwdi1UYU9RbDh1VjlFaXB6QzQ3UDV0N21CLUYxTTYtUTk3cUt4RlMxSkF6OE1hR2g3b2c5bzMxT0V5MUh3QWxuQ1BhY2RIalRIajBiUnBITTl0S3g0QVNzV21PVXZ6WnJobTdLYWhrRmNjZ1MwY1FnZEJ1blhZLUhha3VvY1E?oc=5	0	general	2026-06-09 08:45:32	2026-06-12 07:33:23.398469
101	8	""AAPL" OR "Apple stock" OR "Apple earnings"" - Google News	Apple Set to Launch Its First Touchscreen MacBook (AAPL) - GuruFocus	<a href="https://news.google.com/rss/articles/CBMimAFBVV95cUxONkI1UU42QlpneGRYRnNRSGpHZXI1MHItMWVrb2tXcmRoVThWRVZNbXhneXFyZDMxWmFqbEUtcHlqTlhocFVUZnBzeVo3aDdQTjVRSUVFSTlUMV9iWlRMOGZYa2MxZzBYTjhDcTJDWUo5b0tnY19TLWpNNzA2LXJtX0FPMFFvZHpxNmpNb215M25tMG5hM3phcQ?oc=5" target="_blank">Apple Set to Launch Its First Touchscreen MacBook (AAPL)</a>&nbsp;&nbsp;<font color="#6f6f6f">GuruFocus</font>	https://news.google.com/rss/articles/CBMimAFBVV95cUxONkI1UU42QlpneGRYRnNRSGpHZXI1MHItMWVrb2tXcmRoVThWRVZNbXhneXFyZDMxWmFqbEUtcHlqTlhocFVUZnBzeVo3aDdQTjVRSUVFSTlUMV9iWlRMOGZYa2MxZzBYTjhDcTJDWUo5b0tnY19TLWpNNzA2LXJtX0FPMFFvZHpxNmpNb215M25tMG5hM3phcQ?oc=5	0.21333333333333337	general	2026-06-12 05:12:06	2026-06-12 07:38:29.331806
102	9	""MSFT" OR "Microsoft stock" OR "Microsoft earnings"" - Google N	AI Monetization Timelines Weighed on Microsoft Corporation (MSFT) in Q1 - Yahoo Finance	<a href="https://news.google.com/rss/articles/CBMirAFBVV95cUxNUGZUenlHOGVqOFhaaXVNNzdxaUgyeXU0SVZHSU8zVFVVY2syN2p5TmR5a0ZwR2ZLai1lakFYczlrSkduMlFTbjVXR01BZEttVjRBVGxvdENkZ05qNlZrNEVELVl0WjZFd1lKYjdVdm9RQUxjajM5NFRtc21ZREpQU1RBYzQ2Z1haRl9XVlpyVTdvTkJmeHoxb0w3Mmthdm1Bay1rQ2lrYjhHUklx?oc=5" target="_blank">AI Monetization Timelines Weighed on Microsoft Corporation (MSFT) in Q1</a>&nbsp;&nbsp;<font color="#6f6f6f">Yahoo Finance</font>	https://news.google.com/rss/articles/CBMirAFBVV95cUxNUGZUenlHOGVqOFhaaXVNNzdxaUgyeXU0SVZHSU8zVFVVY2syN2p5TmR5a0ZwR2ZLai1lakFYczlrSkduMlFTbjVXR01BZEttVjRBVGxvdENkZ05qNlZrNEVELVl0WjZFd1lKYjdVdm9RQUxjajM5NFRtc21ZREpQU1RBYzQ2Z1haRl9XVlpyVTdvTkJmeHoxb0w3Mmthdm1Bay1rQ2lrYjhHUklx?oc=5	0	general	2026-06-10 13:20:03	2026-06-12 07:38:29.821386
103	5	""SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"" - Google News	‘Spy turtles’ and ‘spy fish’ being used to monitor Chinese waters, Beijing claims - The Guardian	<a href="https://news.google.com/rss/articles/CBMimgFBVV95cUxOc3UxTDFzeVhLamVXcUx2amxISVR3cEhUMW9sd0hwa2NlbUFhRW1wbWJvWW5iN1dlWnk2ZWVWTFd0OG41ZFNJY2JKS1M3bHpNZ05VNnRiNmZkUF9qUXBoeUlCQTVWZlNBWXJLcWttV01XMkNselViZFl1SG9GUGt1NlZQbFlTLVVIT05XTzVBS1Jlekh5OGI5UFJn?oc=5" target="_blank">‘Spy turtles’ and ‘spy fish’ being used to monitor Chinese waters, Beijing claims</a>&nbsp;&nbsp;<font color="#6f6f6f">The Guardian</font>	https://news.google.com/rss/articles/CBMimgFBVV95cUxOc3UxTDFzeVhLamVXcUx2amxISVR3cEhUMW9sd0hwa2NlbUFhRW1wbWJvWW5iN1dlWnk2ZWVWTFd0OG41ZFNJY2JKS1M3bHpNZ05VNnRiNmZkUF9qUXBoeUlCQTVWZlNBWXJLcWttV01XMkNselViZFl1SG9GUGt1NlZQbFlTLVVIT05XTzVBS1Jlekh5OGI5UFJn?oc=5	0	general	2026-06-12 07:28:00	2026-06-12 07:43:33.724992
104	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	Is the Vanguard Total Stock Market ETF the Best Buy for Long-Term Investors? - The Globe and Mail	<a href="https://news.google.com/rss/articles/CBMi8gFBVV95cUxPMGV0Q0xBZjRSdEVfbVNaOHYxQ1JQbnZxUUt4NWZaNFJDYV9fQTdqY1BpNjQxY2ZDYzhqWGxnY3JmUmhwU3RZc2d6bEZrSjZoQzlkN3FoRHdUdEpVRWJTanVfVUpBZTNQckdyZVdJcC1oTlBUQ2R4YlI3RndEMDRLbkE3YjdDZkNOSkR3YlJtcjltd1UtVTdGeHFSTTNBaE80WF90UXdsTFp5NzEyMWVXenNPdmZ3aEllSDRCSFdFeXpBZ3AwZXRCWURHVWdqTEVGSGZQSVBzLXlTZDZwZWRuRFI0ajVvcVRyT2dPb2xjUEV0UQ?oc=5" target="_blank">Is the Vanguard Total Stock Market ETF the Best Buy for Long-Term Investors?</a>&nbsp;&nbsp;<font color="#6f6f6f">The Globe and Mail</font>	https://news.google.com/rss/articles/CBMi8gFBVV95cUxPMGV0Q0xBZjRSdEVfbVNaOHYxQ1JQbnZxUUt4NWZaNFJDYV9fQTdqY1BpNjQxY2ZDYzhqWGxnY3JmUmhwU3RZc2d6bEZrSjZoQzlkN3FoRHdUdEpVRWJTanVfVUpBZTNQckdyZVdJcC1oTlBUQ2R4YlI3RndEMDRLbkE3YjdDZkNOSkR3YlJtcjltd1UtVTdGeHFSTTNBaE80WF90UXdsTFp5NzEyMWVXenNPdmZ3aEllSDRCSFdFeXpBZ3AwZXRCWURHVWdqTEVGSGZQSVBzLXlTZDZwZWRuRFI0ajVvcVRyT2dPb2xjUEV0UQ?oc=5	0	etf	2026-06-10 11:40:41	2026-06-12 07:43:34.270115
105	7	""VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market""	Is the Vanguard Total Stock Market ETF the Best Buy for Long-Term Investors? - The Motley Fool	<a href="https://news.google.com/rss/articles/CBMilAFBVV95cUxQLVhJeEg5MTJ5bFFOQmNiZHVPdzJ3M0JnZThZaVJKcjdWQko3YzRTVFpKNExGU21sbER4a0pObXFHNkFmaEdlSldSX2pJQUlYcERYbnhjMHNrYlYyaEQxUmJHUmhxcTZVMUtEMTdjaWs2b2ptVl8wT1JJVkhaaVMxWkNIaVRZVS1tUmxDZVhBWjVPb1F4?oc=5" target="_blank">Is the Vanguard Total Stock Market ETF the Best Buy for Long-Term Investors?</a>&nbsp;&nbsp;<font color="#6f6f6f">The Motley Fool</font>	https://news.google.com/rss/articles/CBMilAFBVV95cUxQLVhJeEg5MTJ5bFFOQmNiZHVPdzJ3M0JnZThZaVJKcjdWQko3YzRTVFpKNExGU21sbER4a0pObXFHNkFmaEdlSldSX2pJQUlYcERYbnhjMHNrYlYyaEQxUmJHUmhxcTZVMUtEMTdjaWs2b2ptVl8wT1JJVkhaaVMxWkNIaVRZVS1tUmxDZVhBWjVPb1F4?oc=5	0	etf	2026-06-10 12:20:00	2026-06-12 07:43:34.272825
\.


--
-- Data for Name: positions; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.positions (id, asset_id, status, quantity, entry_price, stop_loss, take_profit, opened_at, closed_at, exit_price, pnl_eur) FROM stdin;
\.


--
-- Data for Name: provider_health_samples; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.provider_health_samples (id, provider, asset_kind, status, attempted_assets, successful_assets, failed_assets, stale_assets, cache_used, message, created_at) FROM stdin;
1	binance	crypto	ok	4	4	0	0	f	Preferred: binance. Actual: binance. Preferred provider satisfied the request. CRYPTO quotes fetched from binance. Binance returned crypto spot quotes.	2026-06-12 07:31:05.862422
2	alpaca	etf	ok	3	3	0	0	f	Preferred: alpaca. Actual: alpaca. Preferred provider satisfied the request. ETF quotes fetched from alpaca. Alpaca returned ETF/stock market snapshots.	2026-06-12 07:31:05.862425
3	alpaca	stock	ok	3	3	0	0	f	Preferred: alpaca. Actual: alpaca. Preferred provider satisfied the request. STOCK quotes fetched from alpaca. Alpaca returned ETF/stock market snapshots.	2026-06-12 07:31:05.862427
4	binance	crypto	ok	4	4	0	0	f	Preferred: binance. Actual: binance. Preferred provider satisfied the request. CRYPTO quotes fetched from binance. Binance returned crypto spot quotes.	2026-06-12 07:33:24.080924
5	alpaca	etf	ok	3	3	0	0	f	Preferred: alpaca. Actual: alpaca. Preferred provider satisfied the request. ETF quotes fetched from alpaca. Alpaca returned ETF/stock market snapshots.	2026-06-12 07:33:24.080931
6	alpaca	stock	ok	3	3	0	0	f	Preferred: alpaca. Actual: alpaca. Preferred provider satisfied the request. STOCK quotes fetched from alpaca. Alpaca returned ETF/stock market snapshots.	2026-06-12 07:33:24.080934
7	binance	crypto	ok	4	4	0	0	f	Preferred: binance. Actual: binance. Preferred provider satisfied the request. CRYPTO quotes fetched from binance. Binance returned crypto spot quotes.	2026-06-12 07:38:29.975222
8	alpaca	etf	ok	3	3	0	0	f	Preferred: alpaca. Actual: alpaca. Preferred provider satisfied the request. ETF quotes fetched from alpaca. Alpaca returned ETF/stock market snapshots.	2026-06-12 07:38:29.975225
9	alpaca	stock	ok	3	3	0	0	f	Preferred: alpaca. Actual: alpaca. Preferred provider satisfied the request. STOCK quotes fetched from alpaca. Alpaca returned ETF/stock market snapshots.	2026-06-12 07:38:29.975227
10	binance	crypto	ok	4	4	0	0	f	Preferred: binance. Actual: binance. Preferred provider satisfied the request. CRYPTO quotes fetched from binance. Binance returned crypto spot quotes.	2026-06-12 07:43:36.041868
11	alpaca	etf	ok	3	3	0	0	f	Preferred: alpaca. Actual: alpaca. Preferred provider satisfied the request. ETF quotes fetched from alpaca. Alpaca returned ETF/stock market snapshots.	2026-06-12 07:43:36.041871
12	alpaca	stock	ok	3	3	0	0	f	Preferred: alpaca. Actual: alpaca. Preferred provider satisfied the request. STOCK quotes fetched from alpaca. Alpaca returned ETF/stock market snapshots.	2026-06-12 07:43:36.041873
\.


--
-- Data for Name: reconciliation_snapshots; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.reconciliation_snapshots (id, status, mode, execution_target, provider, ledger_open_positions, ledger_closed_positions, ledger_open_notional_eur, ledger_realized_pnl_eur, pending_intents, failed_intents, broker_connected, broker_account_id, broker_buying_power, message, created_at) FROM stdin;
1	ok	paper	internal	alpaca	0	0	0	0	0	0	t	PA39N7F87RJH	400000	Internal paper ledger is the only active execution path.	2026-06-12 07:31:06.818471
2	ok	paper	internal	alpaca	0	0	0	0	0	0	t	PA39N7F87RJH	400000	Internal paper ledger is the only active execution path.	2026-06-12 07:33:25.04903
3	ok	paper	internal	alpaca	0	0	0	0	0	0	t	PA39N7F87RJH	400000	Internal paper ledger is the only active execution path.	2026-06-12 07:38:30.92244
4	ok	paper	internal	alpaca	0	0	0	0	0	0	t	PA39N7F87RJH	400000	Internal paper ledger is the only active execution path.	2026-06-12 07:43:36.988583
\.


--
-- Data for Name: signal_outcome_snapshots; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.signal_outcome_snapshots (id, signal_id, horizon_hours, signal_price, observed_price, market_move_pct, decision_edge_pct, pnl_pct, outcome_label, outcome_status, created_at, updated_at) FROM stdin;
1	1	1	54473.6	\N	\N	\N	\N		pending	2026-06-12 07:31:05.868382	2026-06-12 07:31:05.868385
2	1	4	54473.6	\N	\N	\N	\N		pending	2026-06-12 07:31:05.868387	2026-06-12 07:31:05.868388
3	1	24	54473.6	\N	\N	\N	\N		pending	2026-06-12 07:31:05.868389	2026-06-12 07:31:05.86839
4	2	1	1433.84	\N	\N	\N	\N		pending	2026-06-12 07:31:05.872443	2026-06-12 07:31:05.872446
5	2	4	1433.84	\N	\N	\N	\N		pending	2026-06-12 07:31:05.872448	2026-06-12 07:31:05.87245
6	2	24	1433.84	\N	\N	\N	\N		pending	2026-06-12 07:31:05.872451	2026-06-12 07:31:05.872452
7	3	1	57.31	\N	\N	\N	\N		pending	2026-06-12 07:31:05.875538	2026-06-12 07:31:05.875541
8	3	4	57.31	\N	\N	\N	\N		pending	2026-06-12 07:31:05.875543	2026-06-12 07:31:05.875544
9	3	24	57.31	\N	\N	\N	\N		pending	2026-06-12 07:31:05.875546	2026-06-12 07:31:05.875547
10	4	1	6.737	\N	\N	\N	\N		pending	2026-06-12 07:31:05.878415	2026-06-12 07:31:05.878418
11	4	4	6.737	\N	\N	\N	\N		pending	2026-06-12 07:31:05.87842	2026-06-12 07:31:05.878421
12	4	24	6.737	\N	\N	\N	\N		pending	2026-06-12 07:31:05.878422	2026-06-12 07:31:05.878423
13	5	1	738.15	\N	\N	\N	\N		pending	2026-06-12 07:31:05.881241	2026-06-12 07:31:05.881244
14	5	4	738.15	\N	\N	\N	\N		pending	2026-06-12 07:31:05.881246	2026-06-12 07:31:05.881247
15	5	24	738.15	\N	\N	\N	\N		pending	2026-06-12 07:31:05.881249	2026-06-12 07:31:05.88125
16	6	1	715.46	\N	\N	\N	\N		pending	2026-06-12 07:31:05.884321	2026-06-12 07:31:05.884324
17	6	4	715.46	\N	\N	\N	\N		pending	2026-06-12 07:31:05.884326	2026-06-12 07:31:05.884328
18	6	24	715.46	\N	\N	\N	\N		pending	2026-06-12 07:31:05.884329	2026-06-12 07:31:05.884331
19	7	1	364.5	\N	\N	\N	\N		pending	2026-06-12 07:31:05.887401	2026-06-12 07:31:05.887404
20	7	4	364.5	\N	\N	\N	\N		pending	2026-06-12 07:31:05.887407	2026-06-12 07:31:05.887409
21	7	24	364.5	\N	\N	\N	\N		pending	2026-06-12 07:31:05.887411	2026-06-12 07:31:05.887413
22	8	1	295.56	\N	\N	\N	\N		pending	2026-06-12 07:31:05.890014	2026-06-12 07:31:05.890017
23	8	4	295.56	\N	\N	\N	\N		pending	2026-06-12 07:31:05.890019	2026-06-12 07:31:05.89002
24	8	24	295.56	\N	\N	\N	\N		pending	2026-06-12 07:31:05.890021	2026-06-12 07:31:05.890023
25	9	1	391.47	\N	\N	\N	\N		pending	2026-06-12 07:31:05.892459	2026-06-12 07:31:05.892462
26	9	4	391.47	\N	\N	\N	\N		pending	2026-06-12 07:31:05.892464	2026-06-12 07:31:05.892465
27	9	24	391.47	\N	\N	\N	\N		pending	2026-06-12 07:31:05.892467	2026-06-12 07:31:05.892468
28	10	1	204.86	\N	\N	\N	\N		pending	2026-06-12 07:31:05.894907	2026-06-12 07:31:05.894909
29	10	4	204.86	\N	\N	\N	\N		pending	2026-06-12 07:31:05.894911	2026-06-12 07:31:05.894913
30	10	24	204.86	\N	\N	\N	\N		pending	2026-06-12 07:31:05.894914	2026-06-12 07:31:05.894915
31	11	1	54443.8	\N	\N	\N	\N		pending	2026-06-12 07:33:24.086561	2026-06-12 07:33:24.086564
32	11	4	54443.8	\N	\N	\N	\N		pending	2026-06-12 07:33:24.086566	2026-06-12 07:33:24.086568
33	11	24	54443.8	\N	\N	\N	\N		pending	2026-06-12 07:33:24.086569	2026-06-12 07:33:24.08657
34	12	1	1433.03	\N	\N	\N	\N		pending	2026-06-12 07:33:24.089982	2026-06-12 07:33:24.089985
35	12	4	1433.03	\N	\N	\N	\N		pending	2026-06-12 07:33:24.089988	2026-06-12 07:33:24.089989
36	12	24	1433.03	\N	\N	\N	\N		pending	2026-06-12 07:33:24.089991	2026-06-12 07:33:24.089992
37	13	1	57.25	\N	\N	\N	\N		pending	2026-06-12 07:33:24.092818	2026-06-12 07:33:24.092821
38	13	4	57.25	\N	\N	\N	\N		pending	2026-06-12 07:33:24.092823	2026-06-12 07:33:24.092824
39	13	24	57.25	\N	\N	\N	\N		pending	2026-06-12 07:33:24.092826	2026-06-12 07:33:24.092827
40	14	1	6.742	\N	\N	\N	\N		pending	2026-06-12 07:33:24.095598	2026-06-12 07:33:24.095602
41	14	4	6.742	\N	\N	\N	\N		pending	2026-06-12 07:33:24.095604	2026-06-12 07:33:24.095605
42	14	24	6.742	\N	\N	\N	\N		pending	2026-06-12 07:33:24.095606	2026-06-12 07:33:24.095607
43	15	1	738.15	\N	\N	\N	\N		pending	2026-06-12 07:33:24.099312	2026-06-12 07:33:24.099315
44	15	4	738.15	\N	\N	\N	\N		pending	2026-06-12 07:33:24.099317	2026-06-12 07:33:24.099318
45	15	24	738.15	\N	\N	\N	\N		pending	2026-06-12 07:33:24.099319	2026-06-12 07:33:24.099321
46	16	1	715.46	\N	\N	\N	\N		pending	2026-06-12 07:33:24.102845	2026-06-12 07:33:24.102848
47	16	4	715.46	\N	\N	\N	\N		pending	2026-06-12 07:33:24.10285	2026-06-12 07:33:24.102851
48	16	24	715.46	\N	\N	\N	\N		pending	2026-06-12 07:33:24.102853	2026-06-12 07:33:24.102854
49	17	1	364.5	\N	\N	\N	\N		pending	2026-06-12 07:33:24.106275	2026-06-12 07:33:24.106278
50	17	4	364.5	\N	\N	\N	\N		pending	2026-06-12 07:33:24.10628	2026-06-12 07:33:24.106281
51	17	24	364.5	\N	\N	\N	\N		pending	2026-06-12 07:33:24.106283	2026-06-12 07:33:24.106284
52	18	1	295.56	\N	\N	\N	\N		pending	2026-06-12 07:33:24.109032	2026-06-12 07:33:24.109035
53	18	4	295.56	\N	\N	\N	\N		pending	2026-06-12 07:33:24.109066	2026-06-12 07:33:24.109069
54	18	24	295.56	\N	\N	\N	\N		pending	2026-06-12 07:33:24.109071	2026-06-12 07:33:24.109072
55	19	1	391.47	\N	\N	\N	\N		pending	2026-06-12 07:33:24.11187	2026-06-12 07:33:24.111873
56	19	4	391.47	\N	\N	\N	\N		pending	2026-06-12 07:33:24.111875	2026-06-12 07:33:24.111876
57	19	24	391.47	\N	\N	\N	\N		pending	2026-06-12 07:33:24.111878	2026-06-12 07:33:24.111879
58	20	1	204.86	\N	\N	\N	\N		pending	2026-06-12 07:33:24.11478	2026-06-12 07:33:24.114783
59	20	4	204.86	\N	\N	\N	\N		pending	2026-06-12 07:33:24.114785	2026-06-12 07:33:24.114787
60	20	24	204.86	\N	\N	\N	\N		pending	2026-06-12 07:33:24.114788	2026-06-12 07:33:24.114789
61	21	1	54430.48	\N	\N	\N	\N		pending	2026-06-12 07:38:29.977909	2026-06-12 07:38:29.977912
62	21	4	54430.48	\N	\N	\N	\N		pending	2026-06-12 07:38:29.977914	2026-06-12 07:38:29.977915
63	21	24	54430.48	\N	\N	\N	\N		pending	2026-06-12 07:38:29.977917	2026-06-12 07:38:29.977918
64	22	1	1434.88	\N	\N	\N	\N		pending	2026-06-12 07:38:29.980389	2026-06-12 07:38:29.980392
65	22	4	1434.88	\N	\N	\N	\N		pending	2026-06-12 07:38:29.980394	2026-06-12 07:38:29.980395
66	22	24	1434.88	\N	\N	\N	\N		pending	2026-06-12 07:38:29.980397	2026-06-12 07:38:29.980398
67	23	1	57.26	\N	\N	\N	\N		pending	2026-06-12 07:38:29.982548	2026-06-12 07:38:29.982551
68	23	4	57.26	\N	\N	\N	\N		pending	2026-06-12 07:38:29.982553	2026-06-12 07:38:29.982554
69	23	24	57.26	\N	\N	\N	\N		pending	2026-06-12 07:38:29.982556	2026-06-12 07:38:29.982557
70	24	1	6.739	\N	\N	\N	\N		pending	2026-06-12 07:38:29.984653	2026-06-12 07:38:29.984656
71	24	4	6.739	\N	\N	\N	\N		pending	2026-06-12 07:38:29.984658	2026-06-12 07:38:29.984659
72	24	24	6.739	\N	\N	\N	\N		pending	2026-06-12 07:38:29.984661	2026-06-12 07:38:29.984662
73	25	1	738.15	\N	\N	\N	\N		pending	2026-06-12 07:38:29.986738	2026-06-12 07:38:29.986741
74	25	4	738.15	\N	\N	\N	\N		pending	2026-06-12 07:38:29.986743	2026-06-12 07:38:29.986744
75	25	24	738.15	\N	\N	\N	\N		pending	2026-06-12 07:38:29.986746	2026-06-12 07:38:29.986747
76	26	1	715.46	\N	\N	\N	\N		pending	2026-06-12 07:38:29.98882	2026-06-12 07:38:29.988823
77	26	4	715.46	\N	\N	\N	\N		pending	2026-06-12 07:38:29.988825	2026-06-12 07:38:29.988826
78	26	24	715.46	\N	\N	\N	\N		pending	2026-06-12 07:38:29.988828	2026-06-12 07:38:29.988829
79	27	1	364.5	\N	\N	\N	\N		pending	2026-06-12 07:38:29.991084	2026-06-12 07:38:29.991087
80	27	4	364.5	\N	\N	\N	\N		pending	2026-06-12 07:38:29.991089	2026-06-12 07:38:29.99109
81	27	24	364.5	\N	\N	\N	\N		pending	2026-06-12 07:38:29.991092	2026-06-12 07:38:29.991093
82	28	1	295.56	\N	\N	\N	\N		pending	2026-06-12 07:38:29.993246	2026-06-12 07:38:29.993249
83	28	4	295.56	\N	\N	\N	\N		pending	2026-06-12 07:38:29.993251	2026-06-12 07:38:29.993252
84	28	24	295.56	\N	\N	\N	\N		pending	2026-06-12 07:38:29.993254	2026-06-12 07:38:29.993255
85	29	1	391.47	\N	\N	\N	\N		pending	2026-06-12 07:38:29.995641	2026-06-12 07:38:29.995644
86	29	4	391.47	\N	\N	\N	\N		pending	2026-06-12 07:38:29.995646	2026-06-12 07:38:29.995647
87	29	24	391.47	\N	\N	\N	\N		pending	2026-06-12 07:38:29.995648	2026-06-12 07:38:29.99565
88	30	1	204.86	\N	\N	\N	\N		pending	2026-06-12 07:38:29.997703	2026-06-12 07:38:29.997706
89	30	4	204.86	\N	\N	\N	\N		pending	2026-06-12 07:38:29.997708	2026-06-12 07:38:29.99771
90	30	24	204.86	\N	\N	\N	\N		pending	2026-06-12 07:38:29.997711	2026-06-12 07:38:29.997712
91	31	1	54495.95	\N	\N	\N	\N		pending	2026-06-12 07:43:36.044435	2026-06-12 07:43:36.044439
92	31	4	54495.95	\N	\N	\N	\N		pending	2026-06-12 07:43:36.044441	2026-06-12 07:43:36.044442
93	31	24	54495.95	\N	\N	\N	\N		pending	2026-06-12 07:43:36.044444	2026-06-12 07:43:36.044445
94	32	1	1434.98	\N	\N	\N	\N		pending	2026-06-12 07:43:36.046675	2026-06-12 07:43:36.046679
95	32	4	1434.98	\N	\N	\N	\N		pending	2026-06-12 07:43:36.046681	2026-06-12 07:43:36.046682
96	32	24	1434.98	\N	\N	\N	\N		pending	2026-06-12 07:43:36.046683	2026-06-12 07:43:36.046685
97	33	1	57.28	\N	\N	\N	\N		pending	2026-06-12 07:43:36.048817	2026-06-12 07:43:36.04882
98	33	4	57.28	\N	\N	\N	\N		pending	2026-06-12 07:43:36.048823	2026-06-12 07:43:36.048824
99	33	24	57.28	\N	\N	\N	\N		pending	2026-06-12 07:43:36.048826	2026-06-12 07:43:36.048827
100	34	1	6.745	\N	\N	\N	\N		pending	2026-06-12 07:43:36.050976	2026-06-12 07:43:36.050979
101	34	4	6.745	\N	\N	\N	\N		pending	2026-06-12 07:43:36.050981	2026-06-12 07:43:36.050983
102	34	24	6.745	\N	\N	\N	\N		pending	2026-06-12 07:43:36.050984	2026-06-12 07:43:36.050985
103	35	1	738.15	\N	\N	\N	\N		pending	2026-06-12 07:43:36.05311	2026-06-12 07:43:36.053113
104	35	4	738.15	\N	\N	\N	\N		pending	2026-06-12 07:43:36.053115	2026-06-12 07:43:36.053116
105	35	24	738.15	\N	\N	\N	\N		pending	2026-06-12 07:43:36.053117	2026-06-12 07:43:36.053119
106	36	1	715.46	\N	\N	\N	\N		pending	2026-06-12 07:43:36.055245	2026-06-12 07:43:36.055248
107	36	4	715.46	\N	\N	\N	\N		pending	2026-06-12 07:43:36.055251	2026-06-12 07:43:36.055252
108	36	24	715.46	\N	\N	\N	\N		pending	2026-06-12 07:43:36.055253	2026-06-12 07:43:36.055255
109	37	1	364.5	\N	\N	\N	\N		pending	2026-06-12 07:43:36.057419	2026-06-12 07:43:36.057422
110	37	4	364.5	\N	\N	\N	\N		pending	2026-06-12 07:43:36.057424	2026-06-12 07:43:36.057426
111	37	24	364.5	\N	\N	\N	\N		pending	2026-06-12 07:43:36.057427	2026-06-12 07:43:36.057428
112	38	1	295.56	\N	\N	\N	\N		pending	2026-06-12 07:43:36.059561	2026-06-12 07:43:36.059564
113	38	4	295.56	\N	\N	\N	\N		pending	2026-06-12 07:43:36.059566	2026-06-12 07:43:36.059567
114	38	24	295.56	\N	\N	\N	\N		pending	2026-06-12 07:43:36.059569	2026-06-12 07:43:36.05957
115	39	1	391.47	\N	\N	\N	\N		pending	2026-06-12 07:43:36.061689	2026-06-12 07:43:36.061692
116	39	4	391.47	\N	\N	\N	\N		pending	2026-06-12 07:43:36.061694	2026-06-12 07:43:36.061696
117	39	24	391.47	\N	\N	\N	\N		pending	2026-06-12 07:43:36.061697	2026-06-12 07:43:36.061698
118	40	1	204.86	\N	\N	\N	\N		pending	2026-06-12 07:43:36.063836	2026-06-12 07:43:36.063838
119	40	4	204.86	\N	\N	\N	\N		pending	2026-06-12 07:43:36.06384	2026-06-12 07:43:36.063842
120	40	24	204.86	\N	\N	\N	\N		pending	2026-06-12 07:43:36.063843	2026-06-12 07:43:36.063844
\.


--
-- Data for Name: signals; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.signals (id, asset_id, action, score, sentiment_score, momentum_score, rationale, created_at) FROM stdin;
1	1	HOLD	0.5819	0.0056	0.0316	Setup crypto_watch: no clean edge yet. Score 0.58, sentiment 0.01, momentum 0.03, news 6. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:31:05.732837
2	2	HOLD	0.6603	0.5367	0.0063	Setup crypto_watch: no clean edge yet. Score 0.66, sentiment 0.54, momentum 0.01, news 2. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:31:05.732842
3	3	HOLD	0.5061	0	0.1776	Setup crypto_watch: no clean edge yet. Score 0.51, sentiment 0.00, momentum 0.18, news 1. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:31:05.732843
4	4	HOLD	0.4281	0	0.0178	Setup crypto_watch: no clean edge yet. Score 0.43, sentiment 0.00, momentum 0.02, news 0. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:31:05.732845
5	5	HOLD	0.6144	0.0365	0.1732	Setup etf_leader: no clean edge yet. Score 0.61, sentiment 0.04, momentum 0.17, news 19. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:31:05.732846
6	6	BUY	0.6779	0.192	0.3137	Setup etf_leader: ETF lane passed. Score 0.68, sentiment 0.19, momentum 0.31, news 5. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:31:05.732847
7	7	HOLD	0.6071	0	0.1836	Setup etf_leader: no clean edge yet. Score 0.61, sentiment 0.00, momentum 0.18, news 3. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:31:05.732849
8	8	HOLD	0.5995	0	0.14	Setup stock_watch: no clean edge yet. Score 0.60, sentiment 0.00, momentum 0.14, news 6. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:31:05.73285
9	9	HOLD	0.5488	0	-0.1495	Setup stock_watch: no clean edge yet. Score 0.55, sentiment 0.00, momentum -0.15, news 13. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:31:05.732851
10	10	HOLD	0.6139	0	0.222	Setup stock_watch: no clean edge yet. Score 0.61, sentiment 0.00, momentum 0.22, news 8. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:31:05.732852
11	1	HOLD	0.5812	0.0056	0.0277	Setup crypto_watch: no clean edge yet. Score 0.58, sentiment 0.01, momentum 0.03, news 6. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:33:23.951159
12	2	HOLD	0.6605	0.5367	0.0078	Setup crypto_watch: no clean edge yet. Score 0.66, sentiment 0.54, momentum 0.01, news 2. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:33:23.951163
13	3	HOLD	0.5048	0	0.1705	Setup crypto_watch: no clean edge yet. Score 0.50, sentiment 0.00, momentum 0.17, news 1. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:33:23.951165
14	4	HOLD	0.4294	0	0.0253	Setup crypto_watch: no clean edge yet. Score 0.43, sentiment 0.00, momentum 0.03, news 0. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:33:23.951166
15	5	HOLD	0.6144	0.0365	0.1732	Setup etf_leader: no clean edge yet. Score 0.61, sentiment 0.04, momentum 0.17, news 19. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:33:23.951167
16	6	BUY	0.6779	0.192	0.3137	Setup etf_leader: ETF lane passed. Score 0.68, sentiment 0.19, momentum 0.31, news 5. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:33:23.951169
17	7	HOLD	0.6071	0	0.1836	Setup etf_leader: no clean edge yet. Score 0.61, sentiment 0.00, momentum 0.18, news 3. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:33:23.95117
18	8	HOLD	0.5995	0	0.14	Setup stock_watch: no clean edge yet. Score 0.60, sentiment 0.00, momentum 0.14, news 7. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:33:23.951171
19	9	HOLD	0.5488	0	-0.1495	Setup stock_watch: no clean edge yet. Score 0.55, sentiment 0.00, momentum -0.15, news 13. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:33:23.951173
20	10	HOLD	0.6139	0	0.222	Setup stock_watch: no clean edge yet. Score 0.61, sentiment 0.00, momentum 0.22, news 8. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:33:23.951174
21	1	HOLD	0.583	0.0056	0.0376	Setup crypto_watch: no clean edge yet. Score 0.58, sentiment 0.01, momentum 0.04, news 6. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:38:29.886809
22	2	HOLD	0.6646	0.5367	0.0312	Setup crypto_watch: no clean edge yet. Score 0.66, sentiment 0.54, momentum 0.03, news 2. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:38:29.886814
23	3	HOLD	0.5099	0	0.1995	Setup crypto_watch: no clean edge yet. Score 0.51, sentiment 0.00, momentum 0.20, news 1. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:38:29.886816
24	4	HOLD	0.4323	0	0.0417	Setup crypto_watch: no clean edge yet. Score 0.43, sentiment 0.00, momentum 0.04, news 0. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:38:29.886817
25	5	HOLD	0.6144	0.0365	0.1732	Setup etf_leader: no clean edge yet. Score 0.61, sentiment 0.04, momentum 0.17, news 19. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:38:29.886818
26	6	BUY	0.6779	0.192	0.3137	Setup etf_leader: ETF lane passed. Score 0.68, sentiment 0.19, momentum 0.31, news 5. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:38:29.88682
27	7	HOLD	0.6071	0	0.1836	Setup etf_leader: no clean edge yet. Score 0.61, sentiment 0.00, momentum 0.18, news 3. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:38:29.886821
28	8	HOLD	0.6062	0.0267	0.14	Setup stock_watch: no clean edge yet. Score 0.61, sentiment 0.03, momentum 0.14, news 8. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:38:29.886822
29	9	HOLD	0.5488	0	-0.1495	Setup stock_watch: no clean edge yet. Score 0.55, sentiment 0.00, momentum -0.15, news 13. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:38:29.886823
30	10	HOLD	0.6139	0	0.222	Setup stock_watch: no clean edge yet. Score 0.61, sentiment 0.00, momentum 0.22, news 8. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:38:29.886825
31	1	HOLD	0.5846	0.0056	0.0472	Setup crypto_watch: no clean edge yet. Score 0.58, sentiment 0.01, momentum 0.05, news 6. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:43:35.917418
32	2	HOLD	0.6646	0.5367	0.0309	Setup crypto_watch: no clean edge yet. Score 0.66, sentiment 0.54, momentum 0.03, news 2. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:43:35.917422
33	3	HOLD	0.5102	0	0.2012	Setup crypto_watch: no clean edge yet. Score 0.51, sentiment 0.00, momentum 0.20, news 1. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:43:35.917424
34	4	HOLD	0.4307	0	0.0327	Setup crypto_watch: no clean edge yet. Score 0.43, sentiment 0.00, momentum 0.03, news 0. Crypto lane is waiting for cleaner confirmation.	2026-06-12 07:43:35.917425
35	5	HOLD	0.614	0.0347	0.1732	Setup etf_leader: no clean edge yet. Score 0.61, sentiment 0.03, momentum 0.17, news 20. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:43:35.917427
36	6	BUY	0.6779	0.192	0.3137	Setup etf_leader: ETF lane passed. Score 0.68, sentiment 0.19, momentum 0.31, news 5. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:43:35.917428
37	7	HOLD	0.6071	0	0.1836	Setup etf_leader: no clean edge yet. Score 0.61, sentiment 0.00, momentum 0.18, news 3. ETF leader lane wants one clean leader over the pack. Breadth 3 positive / 0 negative, leader momentum 0.31, score spread 0.06.	2026-06-12 07:43:35.917429
38	8	HOLD	0.6062	0.0267	0.14	Setup stock_watch: no clean edge yet. Score 0.61, sentiment 0.03, momentum 0.14, news 8. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:43:35.91743
39	9	HOLD	0.5488	0	-0.1495	Setup stock_watch: no clean edge yet. Score 0.55, sentiment 0.00, momentum -0.15, news 13. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:43:35.917432
40	10	HOLD	0.6139	0	0.222	Setup stock_watch: no clean edge yet. Score 0.61, sentiment 0.00, momentum 0.22, news 8. Stock watch is observation-only until momentum or catalyst quality gets much cleaner.	2026-06-12 07:43:35.917433
\.


--
-- Data for Name: simulation_alerts; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.simulation_alerts (id, simulation_id, level, title, message, created_at) FROM stdin;
\.


--
-- Data for Name: state_events; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.state_events (id, event_key, category, severity, title, message, fingerprint, created_at) FROM stdin;
1	autopilot-state	autopilot	ok	Autopilot is ready	all active universes passed autopilot safety checks	ready|all active universes passed autopilot safety checks	2026-06-12 07:31:05.908205
2	best-opportunity	opportunity	warn	Best opportunity shifted to QQQ	US market session is closed.	blocked|QQQ|etf_leader|US market session is closed.	2026-06-12 07:31:05.910703
3	etf-regime	opportunity	ok	ETF leadership is rebuilding around QQQ	ETF leadership is rebuilding around QQQ. etf_leader is forming, but it is not tradable yet.	rebuilding|QQQ|etf_leader|ETF leadership is rebuilding around QQQ. etf_leader is forming, but it is not tradable yet.	2026-06-12 07:31:05.911985
4	simulation-trigger	simulation	warn	Simulation trigger is waiting	The worker will start the next best approved cross-asset simulation automatically when a fresh BUY appears.	waiting|none	2026-06-12 07:31:05.913298
5	setup-proof-counts	proof	warn	Setup proof board: 0 approved / 0 watch	Current setup evidence totals: 0 approved, 0 watch, 0 disabled.	0|0|0	2026-06-12 07:31:05.914541
6	approval-focus	proof	warn	No entry lane is close enough to promote	The proof engine still lacks any entry setup with enough evidence to become the primary approval candidate.	none	2026-06-12 07:31:05.915952
7	active-proof-runway	proof	ok	QQQ entered first live proof	ETF QQQ etf_leader has 3 pending outcome windows and is now collecting its first real live evidence.	first_live_proof|QQQ|etf_leader|watch|research|0|3|0.000	2026-06-12 07:31:05.919752
8	active-proof-runway	proof	ok	QQQ entered first live proof	ETF QQQ etf_leader has 6 pending outcome windows and is now collecting its first real live evidence.	first_live_proof|QQQ|etf_leader|watch|research|0|6|0.000	2026-06-12 07:33:24.145137
9	active-proof-runway	proof	ok	QQQ entered first live proof	ETF QQQ etf_leader has 9 pending outcome windows and is now collecting its first real live evidence.	first_live_proof|QQQ|etf_leader|watch|research|0|9|0.000	2026-06-12 07:38:30.023142
10	active-proof-runway	proof	ok	QQQ entered first live proof	ETF QQQ etf_leader has 12 pending outcome windows and is now collecting its first real live evidence.	first_live_proof|QQQ|etf_leader|watch|research|0|12|0.000	2026-06-12 07:43:36.093835
\.


--
-- Data for Name: strategy_simulations; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.strategy_simulations (id, asset_id, scenario_key, scenario_label, setup_type, opened_signal_score, status, initial_notional_eur, quantity, entry_price, latest_price, pnl_eur, pnl_pct, stop_price, take_profit_price, trailing_stop_price, alert_flags, opened_reason, started_at, updated_at, closed_at) FROM stdin;
\.


--
-- Data for Name: trades; Type: TABLE DATA; Schema: public; Owner: microtrader
--

COPY public.trades (id, asset_id, mode, execution_target, side, status, notional_eur, quantity, price, reason, executed_at) FROM stdin;
1	5	PAPER	internal	BUY	SKIPPED	0	0	738.15	Skipped because the US market session is closed.	2026-06-12 07:31:05.81839
2	6	PAPER	internal	BUY	SKIPPED	0	0	715.46	Skipped because the US market session is closed.	2026-06-12 07:31:05.823477
3	7	PAPER	internal	BUY	SKIPPED	0	0	364.5	Skipped because the US market session is closed.	2026-06-12 07:31:05.827283
4	8	PAPER	internal	BUY	SKIPPED	0	0	295.56	Skipped because the US market session is closed.	2026-06-12 07:31:05.830948
5	9	PAPER	internal	BUY	SKIPPED	0	0	391.47	Skipped because the US market session is closed.	2026-06-12 07:31:05.834451
6	10	PAPER	internal	BUY	SKIPPED	0	0	204.86	Skipped because the US market session is closed.	2026-06-12 07:31:05.83849
7	5	PAPER	internal	BUY	SKIPPED	0	0	738.15	Skipped because the US market session is closed.	2026-06-12 07:33:24.037131
8	6	PAPER	internal	BUY	SKIPPED	0	0	715.46	Skipped because the US market session is closed.	2026-06-12 07:33:24.042156
9	7	PAPER	internal	BUY	SKIPPED	0	0	364.5	Skipped because the US market session is closed.	2026-06-12 07:33:24.045631
10	8	PAPER	internal	BUY	SKIPPED	0	0	295.56	Skipped because the US market session is closed.	2026-06-12 07:33:24.049129
11	9	PAPER	internal	BUY	SKIPPED	0	0	391.47	Skipped because the US market session is closed.	2026-06-12 07:33:24.052487
12	10	PAPER	internal	BUY	SKIPPED	0	0	204.86	Skipped because the US market session is closed.	2026-06-12 07:33:24.056233
13	5	PAPER	internal	BUY	SKIPPED	0	0	738.15	Skipped because the US market session is closed.	2026-06-12 07:38:29.943966
14	6	PAPER	internal	BUY	SKIPPED	0	0	715.46	Skipped because the US market session is closed.	2026-06-12 07:38:29.947202
15	7	PAPER	internal	BUY	SKIPPED	0	0	364.5	Skipped because the US market session is closed.	2026-06-12 07:38:29.950407
16	8	PAPER	internal	BUY	SKIPPED	0	0	295.56	Skipped because the US market session is closed.	2026-06-12 07:38:29.953659
17	9	PAPER	internal	BUY	SKIPPED	0	0	391.47	Skipped because the US market session is closed.	2026-06-12 07:38:29.956918
18	10	PAPER	internal	BUY	SKIPPED	0	0	204.86	Skipped because the US market session is closed.	2026-06-12 07:38:29.959914
19	5	PAPER	internal	BUY	SKIPPED	0	0	738.15	Skipped because the US market session is closed.	2026-06-12 07:43:36.01253
20	6	PAPER	internal	BUY	SKIPPED	0	0	715.46	Skipped because the US market session is closed.	2026-06-12 07:43:36.015547
21	7	PAPER	internal	BUY	SKIPPED	0	0	364.5	Skipped because the US market session is closed.	2026-06-12 07:43:36.018623
22	8	PAPER	internal	BUY	SKIPPED	0	0	295.56	Skipped because the US market session is closed.	2026-06-12 07:43:36.021629
23	9	PAPER	internal	BUY	SKIPPED	0	0	391.47	Skipped because the US market session is closed.	2026-06-12 07:43:36.024589
24	10	PAPER	internal	BUY	SKIPPED	0	0	204.86	Skipped because the US market session is closed.	2026-06-12 07:43:36.027674
\.


--
-- Name: assets_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.assets_id_seq', 10, true);


--
-- Name: engine_runs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.engine_runs_id_seq', 4, true);


--
-- Name: execution_intents_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.execution_intents_id_seq', 24, true);


--
-- Name: market_ticks_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.market_ticks_id_seq', 40, true);


--
-- Name: news_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.news_items_id_seq', 105, true);


--
-- Name: positions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.positions_id_seq', 1, false);


--
-- Name: provider_health_samples_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.provider_health_samples_id_seq', 12, true);


--
-- Name: reconciliation_snapshots_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.reconciliation_snapshots_id_seq', 4, true);


--
-- Name: signal_outcome_snapshots_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.signal_outcome_snapshots_id_seq', 120, true);


--
-- Name: signals_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.signals_id_seq', 40, true);


--
-- Name: simulation_alerts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.simulation_alerts_id_seq', 1, false);


--
-- Name: state_events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.state_events_id_seq', 10, true);


--
-- Name: strategy_simulations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.strategy_simulations_id_seq', 1, false);


--
-- Name: trades_id_seq; Type: SEQUENCE SET; Schema: public; Owner: microtrader
--

SELECT pg_catalog.setval('public.trades_id_seq', 24, true);


--
-- Name: assets assets_external_id_key; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_external_id_key UNIQUE (external_id);


--
-- Name: assets assets_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_pkey PRIMARY KEY (id);


--
-- Name: engine_runs engine_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.engine_runs
    ADD CONSTRAINT engine_runs_pkey PRIMARY KEY (id);


--
-- Name: execution_intents execution_intents_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.execution_intents
    ADD CONSTRAINT execution_intents_pkey PRIMARY KEY (id);


--
-- Name: market_ticks market_ticks_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.market_ticks
    ADD CONSTRAINT market_ticks_pkey PRIMARY KEY (id);


--
-- Name: news_items news_items_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.news_items
    ADD CONSTRAINT news_items_pkey PRIMARY KEY (id);


--
-- Name: news_items news_items_url_key; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.news_items
    ADD CONSTRAINT news_items_url_key UNIQUE (url);


--
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: provider_health_samples provider_health_samples_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.provider_health_samples
    ADD CONSTRAINT provider_health_samples_pkey PRIMARY KEY (id);


--
-- Name: reconciliation_snapshots reconciliation_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.reconciliation_snapshots
    ADD CONSTRAINT reconciliation_snapshots_pkey PRIMARY KEY (id);


--
-- Name: signal_outcome_snapshots signal_outcome_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.signal_outcome_snapshots
    ADD CONSTRAINT signal_outcome_snapshots_pkey PRIMARY KEY (id);


--
-- Name: signals signals_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_pkey PRIMARY KEY (id);


--
-- Name: simulation_alerts simulation_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.simulation_alerts
    ADD CONSTRAINT simulation_alerts_pkey PRIMARY KEY (id);


--
-- Name: state_events state_events_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.state_events
    ADD CONSTRAINT state_events_pkey PRIMARY KEY (id);


--
-- Name: strategy_simulations strategy_simulations_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.strategy_simulations
    ADD CONSTRAINT strategy_simulations_pkey PRIMARY KEY (id);


--
-- Name: trades trades_pkey; Type: CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_pkey PRIMARY KEY (id);


--
-- Name: ix_assets_symbol; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE UNIQUE INDEX ix_assets_symbol ON public.assets USING btree (symbol);


--
-- Name: ix_engine_runs_completed_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_engine_runs_completed_at ON public.engine_runs USING btree (completed_at);


--
-- Name: ix_engine_runs_started_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_engine_runs_started_at ON public.engine_runs USING btree (started_at);


--
-- Name: ix_engine_runs_status; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_engine_runs_status ON public.engine_runs USING btree (status);


--
-- Name: ix_execution_intents_asset_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_execution_intents_asset_id ON public.execution_intents USING btree (asset_id);


--
-- Name: ix_execution_intents_broker_order_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_execution_intents_broker_order_id ON public.execution_intents USING btree (broker_order_id);


--
-- Name: ix_execution_intents_created_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_execution_intents_created_at ON public.execution_intents USING btree (created_at);


--
-- Name: ix_execution_intents_execution_target; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_execution_intents_execution_target ON public.execution_intents USING btree (execution_target);


--
-- Name: ix_execution_intents_intent_key; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE UNIQUE INDEX ix_execution_intents_intent_key ON public.execution_intents USING btree (intent_key);


--
-- Name: ix_execution_intents_mode; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_execution_intents_mode ON public.execution_intents USING btree (mode);


--
-- Name: ix_execution_intents_position_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_execution_intents_position_id ON public.execution_intents USING btree (position_id);


--
-- Name: ix_execution_intents_signal_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_execution_intents_signal_id ON public.execution_intents USING btree (signal_id);


--
-- Name: ix_execution_intents_source; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_execution_intents_source ON public.execution_intents USING btree (source);


--
-- Name: ix_execution_intents_status; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_execution_intents_status ON public.execution_intents USING btree (status);


--
-- Name: ix_execution_intents_updated_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_execution_intents_updated_at ON public.execution_intents USING btree (updated_at);


--
-- Name: ix_market_ticks_asset_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_market_ticks_asset_id ON public.market_ticks USING btree (asset_id);


--
-- Name: ix_market_ticks_captured_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_market_ticks_captured_at ON public.market_ticks USING btree (captured_at);


--
-- Name: ix_news_items_asset_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_news_items_asset_id ON public.news_items USING btree (asset_id);


--
-- Name: ix_news_items_published_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_news_items_published_at ON public.news_items USING btree (published_at);


--
-- Name: ix_positions_asset_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_positions_asset_id ON public.positions USING btree (asset_id);


--
-- Name: ix_provider_health_samples_asset_kind; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_provider_health_samples_asset_kind ON public.provider_health_samples USING btree (asset_kind);


--
-- Name: ix_provider_health_samples_created_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_provider_health_samples_created_at ON public.provider_health_samples USING btree (created_at);


--
-- Name: ix_provider_health_samples_provider; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_provider_health_samples_provider ON public.provider_health_samples USING btree (provider);


--
-- Name: ix_provider_health_samples_status; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_provider_health_samples_status ON public.provider_health_samples USING btree (status);


--
-- Name: ix_reconciliation_snapshots_created_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_reconciliation_snapshots_created_at ON public.reconciliation_snapshots USING btree (created_at);


--
-- Name: ix_reconciliation_snapshots_execution_target; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_reconciliation_snapshots_execution_target ON public.reconciliation_snapshots USING btree (execution_target);


--
-- Name: ix_reconciliation_snapshots_mode; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_reconciliation_snapshots_mode ON public.reconciliation_snapshots USING btree (mode);


--
-- Name: ix_reconciliation_snapshots_status; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_reconciliation_snapshots_status ON public.reconciliation_snapshots USING btree (status);


--
-- Name: ix_signal_outcome_snapshots_created_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_signal_outcome_snapshots_created_at ON public.signal_outcome_snapshots USING btree (created_at);


--
-- Name: ix_signal_outcome_snapshots_horizon_hours; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_signal_outcome_snapshots_horizon_hours ON public.signal_outcome_snapshots USING btree (horizon_hours);


--
-- Name: ix_signal_outcome_snapshots_outcome_status; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_signal_outcome_snapshots_outcome_status ON public.signal_outcome_snapshots USING btree (outcome_status);


--
-- Name: ix_signal_outcome_snapshots_signal_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_signal_outcome_snapshots_signal_id ON public.signal_outcome_snapshots USING btree (signal_id);


--
-- Name: ix_signal_outcome_snapshots_updated_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_signal_outcome_snapshots_updated_at ON public.signal_outcome_snapshots USING btree (updated_at);


--
-- Name: ix_signals_asset_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_signals_asset_id ON public.signals USING btree (asset_id);


--
-- Name: ix_signals_created_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_signals_created_at ON public.signals USING btree (created_at);


--
-- Name: ix_signals_score; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_signals_score ON public.signals USING btree (score);


--
-- Name: ix_simulation_alerts_created_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_simulation_alerts_created_at ON public.simulation_alerts USING btree (created_at);


--
-- Name: ix_simulation_alerts_simulation_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_simulation_alerts_simulation_id ON public.simulation_alerts USING btree (simulation_id);


--
-- Name: ix_state_events_category; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_state_events_category ON public.state_events USING btree (category);


--
-- Name: ix_state_events_created_at; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_state_events_created_at ON public.state_events USING btree (created_at);


--
-- Name: ix_state_events_event_key; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_state_events_event_key ON public.state_events USING btree (event_key);


--
-- Name: ix_state_events_fingerprint; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_state_events_fingerprint ON public.state_events USING btree (fingerprint);


--
-- Name: ix_state_events_severity; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_state_events_severity ON public.state_events USING btree (severity);


--
-- Name: ix_strategy_simulations_asset_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_strategy_simulations_asset_id ON public.strategy_simulations USING btree (asset_id);


--
-- Name: ix_strategy_simulations_scenario_key; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_strategy_simulations_scenario_key ON public.strategy_simulations USING btree (scenario_key);


--
-- Name: ix_strategy_simulations_setup_type; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_strategy_simulations_setup_type ON public.strategy_simulations USING btree (setup_type);


--
-- Name: ix_trades_asset_id; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_trades_asset_id ON public.trades USING btree (asset_id);


--
-- Name: ix_trades_execution_target; Type: INDEX; Schema: public; Owner: microtrader
--

CREATE INDEX ix_trades_execution_target ON public.trades USING btree (execution_target);


--
-- Name: execution_intents execution_intents_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.execution_intents
    ADD CONSTRAINT execution_intents_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id);


--
-- Name: execution_intents execution_intents_position_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.execution_intents
    ADD CONSTRAINT execution_intents_position_id_fkey FOREIGN KEY (position_id) REFERENCES public.positions(id);


--
-- Name: execution_intents execution_intents_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.execution_intents
    ADD CONSTRAINT execution_intents_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id);


--
-- Name: market_ticks market_ticks_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.market_ticks
    ADD CONSTRAINT market_ticks_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id);


--
-- Name: news_items news_items_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.news_items
    ADD CONSTRAINT news_items_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id);


--
-- Name: positions positions_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id);


--
-- Name: signal_outcome_snapshots signal_outcome_snapshots_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.signal_outcome_snapshots
    ADD CONSTRAINT signal_outcome_snapshots_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id);


--
-- Name: signals signals_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id);


--
-- Name: simulation_alerts simulation_alerts_simulation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.simulation_alerts
    ADD CONSTRAINT simulation_alerts_simulation_id_fkey FOREIGN KEY (simulation_id) REFERENCES public.strategy_simulations(id);


--
-- Name: strategy_simulations strategy_simulations_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.strategy_simulations
    ADD CONSTRAINT strategy_simulations_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id);


--
-- Name: trades trades_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: microtrader
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id);


--
-- PostgreSQL database dump complete
--

\unrestrict IrzCqz3Q91UzExcznoEeuGjqvtKxfhwhh5vGcco6q1jPtkcy4nXRpkBKcUBsUjf

