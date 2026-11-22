--
-- PostgreSQL database dump
--

\restrict kT3H1PILJJUlwrXUzkDipX01fwfD1L74Wzn7BK6UzJHu1a5WE8ZMOruZrYUA5Gz

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: case_persons; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.case_persons (
    case_id integer NOT NULL,
    person_id integer NOT NULL,
    role character varying(30) NOT NULL,
    CONSTRAINT case_persons_role_check CHECK (((role)::text = ANY ((ARRAY['suspect'::character varying, 'witness'::character varying, 'investigator'::character varying, 'other'::character varying])::text[])))
);


ALTER TABLE public.case_persons OWNER TO postgres;

--
-- Name: cases; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cases (
    case_id integer NOT NULL,
    title character varying(150) NOT NULL,
    description text NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT cases_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'investigating'::character varying, 'closed'::character varying])::text[])))
);


ALTER TABLE public.cases OWNER TO postgres;

--
-- Name: cases_case_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.cases ALTER COLUMN case_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.cases_case_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: evidence; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.evidence (
    evidence_id integer NOT NULL,
    case_id integer NOT NULL,
    title character varying(150) NOT NULL,
    description text NOT NULL,
    evidence_type character varying(40) NOT NULL,
    verification_status character varying(20) DEFAULT 'unverified'::character varying NOT NULL,
    recorded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT evidence_verification_status_check CHECK (((verification_status)::text = ANY ((ARRAY['unverified'::character varying, 'verified'::character varying, 'disputed'::character varying])::text[])))
);


ALTER TABLE public.evidence OWNER TO postgres;

--
-- Name: evidence_evidence_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.evidence ALTER COLUMN evidence_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.evidence_evidence_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: evidence_people; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.evidence_people (
    evidence_id integer NOT NULL,
    person_id integer NOT NULL,
    involvement character varying(50) NOT NULL
);


ALTER TABLE public.evidence_people OWNER TO postgres;

--
-- Name: locations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.locations (
    location_id integer NOT NULL,
    location_name character varying(100) NOT NULL
);


ALTER TABLE public.locations OWNER TO postgres;

--
-- Name: locations_location_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.locations ALTER COLUMN location_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.locations_location_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: person_relationships; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.person_relationships (
    relationship_id integer NOT NULL,
    case_id integer NOT NULL,
    person_id integer NOT NULL,
    related_person_id integer NOT NULL,
    relationship_type character varying(50) NOT NULL,
    CONSTRAINT person_relationships_check CHECK ((person_id <> related_person_id))
);


ALTER TABLE public.person_relationships OWNER TO postgres;

--
-- Name: person_relationships_relationship_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.person_relationships ALTER COLUMN relationship_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.person_relationships_relationship_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: persons; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.persons (
    person_id integer NOT NULL,
    full_name character varying(100) NOT NULL,
    occupation character varying(100)
);


ALTER TABLE public.persons OWNER TO postgres;

--
-- Name: persons_person_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.persons ALTER COLUMN person_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.persons_person_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: timeline_events; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.timeline_events (
    event_id integer NOT NULL,
    case_id integer NOT NULL,
    person_id integer NOT NULL,
    location_id integer NOT NULL,
    event_time timestamp without time zone NOT NULL,
    description text NOT NULL,
    source_evidence_id integer,
    is_verified boolean DEFAULT false NOT NULL
);


ALTER TABLE public.timeline_events OWNER TO postgres;

--
-- Name: timeline_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.timeline_events ALTER COLUMN event_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.timeline_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: case_persons case_persons_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_persons
    ADD CONSTRAINT case_persons_pkey PRIMARY KEY (case_id, person_id);


--
-- Name: cases cases_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cases
    ADD CONSTRAINT cases_pkey PRIMARY KEY (case_id);


--
-- Name: evidence_people evidence_people_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evidence_people
    ADD CONSTRAINT evidence_people_pkey PRIMARY KEY (evidence_id, person_id, involvement);


--
-- Name: evidence evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT evidence_pkey PRIMARY KEY (evidence_id);


--
-- Name: locations locations_location_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_location_name_key UNIQUE (location_name);


--
-- Name: locations locations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_pkey PRIMARY KEY (location_id);


--
-- Name: person_relationships person_relationships_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.person_relationships
    ADD CONSTRAINT person_relationships_pkey PRIMARY KEY (relationship_id);


--
-- Name: persons persons_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_pkey PRIMARY KEY (person_id);


--
-- Name: timeline_events timeline_events_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timeline_events
    ADD CONSTRAINT timeline_events_pkey PRIMARY KEY (event_id);


--
-- Name: idx_evidence_case; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_evidence_case ON public.evidence USING btree (case_id);


--
-- Name: idx_evidence_people_person; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_evidence_people_person ON public.evidence_people USING btree (person_id);


--
-- Name: idx_relationship_person; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_relationship_person ON public.person_relationships USING btree (case_id, person_id);


--
-- Name: idx_relationship_related; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_relationship_related ON public.person_relationships USING btree (case_id, related_person_id);


--
-- Name: idx_timeline_person_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_timeline_person_time ON public.timeline_events USING btree (person_id, event_time);


--
-- Name: case_persons case_persons_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_persons
    ADD CONSTRAINT case_persons_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(case_id) ON DELETE CASCADE;


--
-- Name: case_persons case_persons_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_persons
    ADD CONSTRAINT case_persons_person_id_fkey FOREIGN KEY (person_id) REFERENCES public.persons(person_id) ON DELETE CASCADE;


--
-- Name: evidence evidence_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT evidence_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(case_id);


--
-- Name: evidence_people evidence_people_evidence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evidence_people
    ADD CONSTRAINT evidence_people_evidence_id_fkey FOREIGN KEY (evidence_id) REFERENCES public.evidence(evidence_id) ON DELETE CASCADE;


--
-- Name: evidence_people evidence_people_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.evidence_people
    ADD CONSTRAINT evidence_people_person_id_fkey FOREIGN KEY (person_id) REFERENCES public.persons(person_id);


--
-- Name: person_relationships person_relationships_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.person_relationships
    ADD CONSTRAINT person_relationships_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(case_id);


--
-- Name: person_relationships person_relationships_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.person_relationships
    ADD CONSTRAINT person_relationships_person_id_fkey FOREIGN KEY (person_id) REFERENCES public.persons(person_id);


--
-- Name: person_relationships person_relationships_related_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.person_relationships
    ADD CONSTRAINT person_relationships_related_person_id_fkey FOREIGN KEY (related_person_id) REFERENCES public.persons(person_id);


--
-- Name: timeline_events timeline_events_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timeline_events
    ADD CONSTRAINT timeline_events_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(case_id);


--
-- Name: timeline_events timeline_events_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timeline_events
    ADD CONSTRAINT timeline_events_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.locations(location_id);


--
-- Name: timeline_events timeline_events_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timeline_events
    ADD CONSTRAINT timeline_events_person_id_fkey FOREIGN KEY (person_id) REFERENCES public.persons(person_id);


--
-- Name: timeline_events timeline_events_source_evidence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timeline_events
    ADD CONSTRAINT timeline_events_source_evidence_id_fkey FOREIGN KEY (source_evidence_id) REFERENCES public.evidence(evidence_id);


--
-- PostgreSQL database dump complete
--

\unrestrict kT3H1PILJJUlwrXUzkDipX01fwfD1L74Wzn7BK6UzJHu1a5WE8ZMOruZrYUA5Gz


-- CaseGraph person avatar/photo support (additive migration)
ALTER TABLE public.persons ADD COLUMN IF NOT EXISTS gender text;
ALTER TABLE public.persons ADD COLUMN IF NOT EXISTS photo_path text;
