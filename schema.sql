--
-- PostgreSQL database dump
--

\restrict Y6VPzyCKFYnKSTY53UuIsYTdwShHBc1u2MypwfoiL5hrYoCNyOieOOhby1jPeTF

-- Dumped from database version 16.13 (Ubuntu 16.13-1.pgdg24.04+1)
-- Dumped by pg_dump version 17.9 (Ubuntu 17.9-1.pgdg24.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: advicetype; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.advicetype AS ENUM (
    'daily',
    'weekly',
    'monthly'
);


ALTER TYPE public.advicetype OWNER TO postgres;

--
-- Name: coachtone; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.coachtone AS ENUM (
    'blunt',
    'balanced',
    'push'
);


ALTER TYPE public.coachtone OWNER TO postgres;

--
-- Name: goalcategory; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.goalcategory AS ENUM (
    'health',
    'career',
    'mindset',
    'relationships',
    'finance',
    'purpose'
);


ALTER TYPE public.goalcategory OWNER TO postgres;

--
-- Name: goallogstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.goallogstatus AS ENUM (
    'completed',
    'incomplete',
    'skipped'
);


ALTER TYPE public.goallogstatus OWNER TO postgres;

--
-- Name: memorytype; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.memorytype AS ENUM (
    'journal',
    'advice',
    'pattern',
    'milestone'
);


ALTER TYPE public.memorytype OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_advice; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ai_advice (
    id integer NOT NULL,
    user_id integer NOT NULL,
    advice_text text NOT NULL,
    advice_type public.advicetype NOT NULL,
    given_at timestamp with time zone,
    validate_at timestamp with time zone,
    validated boolean,
    effectiveness_score double precision,
    outcome_notes text
);


ALTER TABLE public.ai_advice OWNER TO postgres;

--
-- Name: ai_advice_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ai_advice_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ai_advice_id_seq OWNER TO postgres;

--
-- Name: ai_advice_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ai_advice_id_seq OWNED BY public.ai_advice.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: daily_goal_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.daily_goal_logs (
    id integer NOT NULL,
    goal_id integer NOT NULL,
    user_id integer NOT NULL,
    log_date date NOT NULL,
    status public.goallogstatus NOT NULL,
    skip_reason text,
    daily_log_id integer,
    created_at timestamp with time zone
);


ALTER TABLE public.daily_goal_logs OWNER TO postgres;

--
-- Name: daily_goal_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.daily_goal_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.daily_goal_logs_id_seq OWNER TO postgres;

--
-- Name: daily_goal_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.daily_goal_logs_id_seq OWNED BY public.daily_goal_logs.id;


--
-- Name: daily_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.daily_logs (
    id integer NOT NULL,
    user_id integer NOT NULL,
    created_at timestamp with time zone,
    log_date date NOT NULL,
    morning_feeling_score integer,
    morning_text text,
    morning_extracted jsonb,
    evening_text text,
    evening_extracted jsonb,
    day_score integer
);


ALTER TABLE public.daily_logs OWNER TO postgres;

--
-- Name: daily_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.daily_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.daily_logs_id_seq OWNER TO postgres;

--
-- Name: daily_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.daily_logs_id_seq OWNED BY public.daily_logs.id;


--
-- Name: dead_letter_tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.dead_letter_tasks (
    id integer NOT NULL,
    user_id integer NOT NULL,
    source character varying(100) NOT NULL,
    error text NOT NULL,
    status character varying(20),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.dead_letter_tasks OWNER TO postgres;

--
-- Name: dead_letter_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.dead_letter_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.dead_letter_tasks_id_seq OWNER TO postgres;

--
-- Name: dead_letter_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.dead_letter_tasks_id_seq OWNED BY public.dead_letter_tasks.id;


--
-- Name: goals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.goals (
    id integer NOT NULL,
    user_id integer NOT NULL,
    title text NOT NULL,
    category public.goalcategory NOT NULL,
    created_date date,
    target_date date,
    is_active boolean
);


ALTER TABLE public.goals OWNER TO postgres;

--
-- Name: goals_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.goals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.goals_id_seq OWNER TO postgres;

--
-- Name: goals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.goals_id_seq OWNED BY public.goals.id;


--
-- Name: memory_embeddings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.memory_embeddings (
    id integer NOT NULL,
    user_id integer NOT NULL,
    content text NOT NULL,
    embedding public.vector(768) NOT NULL,
    memory_type public.memorytype NOT NULL,
    created_at timestamp with time zone
);


ALTER TABLE public.memory_embeddings OWNER TO postgres;

--
-- Name: memory_embeddings_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.memory_embeddings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.memory_embeddings_id_seq OWNER TO postgres;

--
-- Name: memory_embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.memory_embeddings_id_seq OWNED BY public.memory_embeddings.id;


--
-- Name: person_model; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.person_model (
    id integer NOT NULL,
    user_id integer NOT NULL,
    top_excuses jsonb,
    consistency_style character varying,
    peak_performance_days jsonb,
    goal_dna jsonb,
    life_area_scores jsonb,
    dominant_emotions jsonb,
    mood_performance_correlation double precision,
    updated_at timestamp with time zone
);


ALTER TABLE public.person_model OWNER TO postgres;

--
-- Name: person_model_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.person_model_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.person_model_id_seq OWNER TO postgres;

--
-- Name: person_model_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.person_model_id_seq OWNED BY public.person_model.id;


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.refresh_tokens (
    id integer NOT NULL,
    token_hash character varying,
    user_id integer NOT NULL,
    created_at timestamp with time zone,
    expires_at timestamp without time zone
);


ALTER TABLE public.refresh_tokens OWNER TO postgres;

--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.refresh_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.refresh_tokens_id_seq OWNER TO postgres;

--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.refresh_tokens_id_seq OWNED BY public.refresh_tokens.id;


--
-- Name: user_onboarding; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_onboarding (
    id integer NOT NULL,
    user_id integer NOT NULL,
    life_area_focus text,
    past_failures text,
    ideal_day text,
    biggest_excuse text,
    life_scores jsonb,
    created_at timestamp with time zone
);


ALTER TABLE public.user_onboarding OWNER TO postgres;

--
-- Name: user_onboarding_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_onboarding_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_onboarding_id_seq OWNER TO postgres;

--
-- Name: user_onboarding_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_onboarding_id_seq OWNED BY public.user_onboarding.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying NOT NULL,
    name character varying NOT NULL,
    password_hash character varying NOT NULL,
    role character varying,
    token_version integer,
    avatar_url character varying,
    coach_tone public.coachtone,
    onboarding_complete boolean,
    created_at timestamp with time zone
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: ai_advice id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ai_advice ALTER COLUMN id SET DEFAULT nextval('public.ai_advice_id_seq'::regclass);


--
-- Name: daily_goal_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_goal_logs ALTER COLUMN id SET DEFAULT nextval('public.daily_goal_logs_id_seq'::regclass);


--
-- Name: daily_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_logs ALTER COLUMN id SET DEFAULT nextval('public.daily_logs_id_seq'::regclass);


--
-- Name: dead_letter_tasks id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dead_letter_tasks ALTER COLUMN id SET DEFAULT nextval('public.dead_letter_tasks_id_seq'::regclass);


--
-- Name: goals id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goals ALTER COLUMN id SET DEFAULT nextval('public.goals_id_seq'::regclass);


--
-- Name: memory_embeddings id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_embeddings ALTER COLUMN id SET DEFAULT nextval('public.memory_embeddings_id_seq'::regclass);


--
-- Name: person_model id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.person_model ALTER COLUMN id SET DEFAULT nextval('public.person_model_id_seq'::regclass);


--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('public.refresh_tokens_id_seq'::regclass);


--
-- Name: user_onboarding id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_onboarding ALTER COLUMN id SET DEFAULT nextval('public.user_onboarding_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: ai_advice ai_advice_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ai_advice
    ADD CONSTRAINT ai_advice_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: daily_goal_logs daily_goal_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_goal_logs
    ADD CONSTRAINT daily_goal_logs_pkey PRIMARY KEY (id);


--
-- Name: daily_logs daily_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_logs
    ADD CONSTRAINT daily_logs_pkey PRIMARY KEY (id);


--
-- Name: dead_letter_tasks dead_letter_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dead_letter_tasks
    ADD CONSTRAINT dead_letter_tasks_pkey PRIMARY KEY (id, user_id);


--
-- Name: goals goals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goals
    ADD CONSTRAINT goals_pkey PRIMARY KEY (id);


--
-- Name: memory_embeddings memory_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_embeddings
    ADD CONSTRAINT memory_embeddings_pkey PRIMARY KEY (id);


--
-- Name: person_model person_model_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.person_model
    ADD CONSTRAINT person_model_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: daily_goal_logs uq_goal_log_per_day; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_goal_logs
    ADD CONSTRAINT uq_goal_log_per_day UNIQUE (goal_id, log_date);


--
-- Name: daily_logs uq_user_daily_log; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_logs
    ADD CONSTRAINT uq_user_daily_log UNIQUE (user_id, log_date);


--
-- Name: memory_embeddings uq_user_memory; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_embeddings
    ADD CONSTRAINT uq_user_memory UNIQUE (user_id, memory_type, content);


--
-- Name: user_onboarding user_onboarding_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_onboarding
    ADD CONSTRAINT user_onboarding_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_ai_advice_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_ai_advice_user_id ON public.ai_advice USING btree (user_id);


--
-- Name: ix_daily_goal_logs_goal_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_daily_goal_logs_goal_id ON public.daily_goal_logs USING btree (goal_id);


--
-- Name: ix_daily_goal_logs_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_daily_goal_logs_user_id ON public.daily_goal_logs USING btree (user_id);


--
-- Name: ix_daily_logs_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_daily_logs_user_id ON public.daily_logs USING btree (user_id);


--
-- Name: ix_dead_letter_tasks_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_dead_letter_tasks_id ON public.dead_letter_tasks USING btree (id);


--
-- Name: ix_dead_letter_tasks_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_dead_letter_tasks_user_id ON public.dead_letter_tasks USING btree (user_id);


--
-- Name: ix_goals_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_goals_user_id ON public.goals USING btree (user_id);


--
-- Name: ix_memory_embeddings_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_embeddings_created_at ON public.memory_embeddings USING btree (created_at);


--
-- Name: ix_memory_embeddings_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_memory_embeddings_user_id ON public.memory_embeddings USING btree (user_id);


--
-- Name: ix_person_model_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_person_model_user_id ON public.person_model USING btree (user_id);


--
-- Name: ix_refresh_tokens_token_hash; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_refresh_tokens_token_hash ON public.refresh_tokens USING btree (token_hash);


--
-- Name: ix_refresh_tokens_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_refresh_tokens_user_id ON public.refresh_tokens USING btree (user_id);


--
-- Name: ix_user_onboarding_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_user_onboarding_user_id ON public.user_onboarding USING btree (user_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ai_advice ai_advice_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ai_advice
    ADD CONSTRAINT ai_advice_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: daily_goal_logs daily_goal_logs_daily_log_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_goal_logs
    ADD CONSTRAINT daily_goal_logs_daily_log_id_fkey FOREIGN KEY (daily_log_id) REFERENCES public.daily_logs(id) ON DELETE SET NULL;


--
-- Name: daily_goal_logs daily_goal_logs_goal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_goal_logs
    ADD CONSTRAINT daily_goal_logs_goal_id_fkey FOREIGN KEY (goal_id) REFERENCES public.goals(id) ON DELETE CASCADE;


--
-- Name: daily_goal_logs daily_goal_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_goal_logs
    ADD CONSTRAINT daily_goal_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: daily_logs daily_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.daily_logs
    ADD CONSTRAINT daily_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: dead_letter_tasks dead_letter_tasks_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dead_letter_tasks
    ADD CONSTRAINT dead_letter_tasks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: goals goals_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goals
    ADD CONSTRAINT goals_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: memory_embeddings memory_embeddings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.memory_embeddings
    ADD CONSTRAINT memory_embeddings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: person_model person_model_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.person_model
    ADD CONSTRAINT person_model_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_onboarding user_onboarding_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_onboarding
    ADD CONSTRAINT user_onboarding_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict Y6VPzyCKFYnKSTY53UuIsYTdwShHBc1u2MypwfoiL5hrYoCNyOieOOhby1jPeTF

