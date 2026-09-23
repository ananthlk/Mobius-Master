-- 073 · An outcome is attributable only if the turn ran to completion.
--
-- v_reformulation_arms excluded clock deaths by BLACKLISTING ONE LITERAL
-- STRING, 'exit=v2_budget_exhausted'. Governor's loop has since grown five
-- more ways to run out of promise, and row 771 (exit=reserve_the_write)
-- was being counted as a query that failed to close its gap. A rate built
-- on it is a rate about the caller's clock.
--
-- Naming one instance of a class and letting the class grow is the same
-- mistake as pinning a test to a slug instead of a property. So this keys
-- on the CLASS, whitelists the only family that can carry an outcome, and
-- makes an unrecognised exit VISIBLE rather than silently counted either
-- way.
--
-- Vocabulary from Governor, 2026-09-23, as written on the loop's exit step:
--   done       model_complete_no_gaps
--   clock      v2_budget_exhausted, overrun_into_band, reserve_the_write,
--              out_of_time_write, max_rounds, nothing_worth_buying
--   broken     unusable_rounds, model_empty, model_error, no_state
--              (plus status=failed error=worker_lost, which never reaches
--               the exit step at all)
--
-- NOTE FOR WHOEVER TOUCHES THIS NEXT: the loop also carries a class-level
-- `exit_mode` enum (complete/budget/capability/error) on the same step. If
-- the note ever carries it, key on that and delete the string lists below.

create or replace function research.exit_class(note text)
returns text language sql immutable as $$
  select case
    when note is null                                   then 'no_exit'
    when note like '%exit=model_complete_no_gaps%'      then 'done'
    when note like '%exit=v2_budget_exhausted%'
      or note like '%exit=overrun_into_band%'
      or note like '%exit=reserve_the_write%'
      or note like '%exit=out_of_time_write%'
      or note like '%exit=max_rounds%'
      or note like '%exit=nothing_worth_buying%'        then 'clock'
    when note like '%exit=unusable_rounds%'
      or note like '%exit=model_empty%'
      or note like '%exit=model_error%'
      or note like '%exit=no_state%'
      or note like '%error=worker_lost%'                then 'broken'
    when note like '%exit=%'                            then 'UNKNOWN'
    else 'no_exit'
  end
$$;

-- Every exit the data has ever carried, with its class. An UNKNOWN row here
-- means the loop grew a new exit and this migration has gone stale; that is
-- the signal the old blacklist could never give.
create or replace view research.v_reformulation_exits as
  select research.exit_class(outcome_note) as exit_class,
         -- [a-z0-9_] not [a-z_]: the first version of this captured "v"
         -- from "v2_budget_exhausted" and printed a class-correct row with
         -- a nonsense name. The same failure this migration exists to fix,
         -- one layer down: a pattern that does not cover its vocabulary.
         substring(outcome_note from 'exit=([a-z0-9_]+)') as exit_seen,
         count(*) as rows,
         count(*) filter (where gap_closed is not null) as told
    from research.reformulation
   where outcome_note is not null
     and coalesce(outcome_note,'') not like '%SMOKE ROW%'
     and coalesce(outcome_note,'') not like '%MIS-TRIGGERED%'
   group by 1, 2
   order by 1, 3 desc;

create or replace view research.v_reformulation_arms as
  with scored as (
    select called_because, arm, caller_ref, attribution,
           gap_closed, closed_by_this_query
      from research.reformulation
     where executed is not false
       and outcome_note is not null
       and coalesce(outcome_note,'') not like '%SMOKE ROW%'
       and coalesce(outcome_note,'') not like '%MIS-TRIGGERED%'
       -- EXCLUDE ON AFFIRMATIVE EVIDENCE, not on absence of it. A clock
       -- death, a broken turn or an exit nobody has taught this view about
       -- are all excluded — so a new exit string is never silently counted
       -- — while a note carrying no exit marker at all is kept, because it
       -- asserts nothing about how the turn ended and not every caller
       -- annotates. A pure whitelist on 'done' dropped those too, which
       -- broke a test whose note said exit=normal: a value the loop has
       -- never emitted, invented in a fixture, and correctly flagged
       -- UNKNOWN by this function.
       and research.exit_class(outcome_note) in ('done', 'no_exit')
  )
  select called_because, arm,
         count(*) as rows_scored,
         count(*) filter (where gap_closed is not null) as told,
         count(*) filter (where gap_closed) as settled,
         count(*) filter (where closed_by_this_query) as settled_on_own_evidence,
         count(distinct caller_ref) as distinct_questions,
         count(distinct attribution) as attribution_methods,
         string_agg(distinct attribution, '/') as attributed_by
    from scored
   group by called_because, arm;
