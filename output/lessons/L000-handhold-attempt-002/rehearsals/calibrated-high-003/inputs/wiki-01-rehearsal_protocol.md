# Lesson rehearsal, anonymous review, and repair

During handhold mode, every lesson must complete this loop before it can be considered ready:

1. freeze the exact lesson, learner level, known closure, actor prompts, tools, language policy,
   budgets, scenarios, and wiki bindings in a rehearsal specification, then materialize every
   bound lesson/state/closure/wiki input into the run directory before either actor starts;
2. let Luna teach while a Sol session simulates Ninereeds at that exact level;
3. have Luna close conduct with a hash-bound post-lesson report, then construct an anonymized
   evidence packet containing that report and the frozen interaction log;
4. let a fresh Sol session review the packet without model identities or hidden simulator policy;
5. either record a pass or diagnose and repair the failure in a new linked attempt.

The roleplay Sol and review Sol are different sessions. The reviewer sees only an anonymous
teacher, an anonymous learner simulator, the current learner state and known closure, the lesson,
the hash-chained log, the teacher-language policy, the alarm state, and hash-bound wiki sources.
It must not receive either actor's model identity, provider preference, or the simulator's hidden
behavior profile. The reviewer must include the teaching methodology wiki binding.

Run distinct frozen learner-simulation modes rather than one convenient generic student:
`calibrated_estimate`, `conservative_lower_bound`, `unexpected_bonus`,
`adversarial_pedagogical`, `adversarial_protocol`, and `failure_injection`. Each mode uses a separate run and
preferably a fresh Sol session. The hidden mode and behavior profile are excluded from the
anonymous review packet; the reviewer judges whether the visible behavior remains plausible for
the stated learner stage.

Failure injection covers catastrophic capability collapse, word or phrase perseveration,
concept bleed, prompt-pressure verbatim echoing, prompt copying, token degeneration, abrupt loss
of previously stable items, one-label contamination, alternating competence and collapse, and
persistent silence or `I don't know`. Preserve the raw response before normalization. An exact
prompt echo is not acquisition evidence. The frozen scenario states whether Luna should make one
bounded diagnostic or rescue attempt before alarming. Persistent looping, degeneration, concept
bleed, prompt echo, or a material state discontinuity must freeze or defer the lesson; grinding
onward is a Luna-routine failure. Every novel real-world pathology becomes a new immutable
regression scenario after diagnosis.

Calibrate Luna effort separately for lesson building, conduct, and post-lesson analysis. Freeze
the exact effort in each actor configuration and hold prompts, inputs, scenarios, and review
rubrics fixed during comparison. Use the lowest effort that preserves quality; test a higher effort
only where independent review shows a reproducible gain. The conductor and report analyst may be
separate Luna sessions with different effort settings.

For model-attributable judgment or output failure, retry in a new linked run using the fixed ladder
`medium → high → xhigh → max`, advancing exactly one rung and changing no other variable. Missing
prerequisites, rejected assets, lesson contradictions, infrastructure failures, and operator stops
are blockers rather than effort failures and do not climb the ladder. Failure at `max` records
`terminal_model_capability_failure` and ends that attempt family. `low` is reserved for later
efficiency probes after the role works reliably.

## Conduct contract

Luna and Sol alternate complete turns. Every event names the canonical phase and exercise. Sol
answers from the frozen hidden behavior profile and known closure; it does not optimize for making
the lesson pass. Luna may perform ordinary teaching actions only inside the lesson Point, answer
contracts, phase order, and turn budgets.

Actor separation is enforced at admission, not inferred from labels inside a combined transcript.
Luna produces a teacher-only exchange artifact containing only `tool_call` and `teacher_turn`
events. A separate Sol session receives only the already-emitted bounded block and produces a
student-only artifact containing exactly one `student_turn` per teacher turn. The orchestration
layer pairs these artifacts by phase and exercise ID and appends them in alternating order. Luna
must never predict, fabricate, or serialize a learner turn; Sol must never author a teacher turn.
No response from the assigned peer is a protocol failure, not permission for either actor to play
both roles. During handhold mode the operator brokers these blocks at adaptive decision boundaries;
an autonomous runner must preserve the same independently attributable admission boundary.

Every Luna turn carries a language receipt dividing its wording among known forms, the declared
frontier, licensed instruction phrases, and licensed rescue phrases. Any unlicensed wording is a
protocol failure and freezes the run. A passing run includes an explicit understanding check; a
correct answer alone does not prove that the teacher's wording was understood.

Luna may call only these protocol-level tools when both the rehearsal specification and current
exercise license them:

- `SHOW_ASSET`: show a prepared lesson asset;
- `SHOW_CROP`: show a precomputed literal crop;
- `SHOW_HIGHLIGHT`: show a prepared context-preserving highlight;
- `REPLAY_PRESENTATION`: repeat the frozen presentation within budget;
- `PRESENT_AGAIN`: use the lesson's exact failed-gate dispatch to replay one frozen presentation
  and administer its mapped unmarked cold retest;
- `USE_MARKERS`: apply the frozen bounded marker policy and retest unmarked;
- `ASK_BOUNDED_CLARIFICATION`: ask one licensed clarification question;
- `CHECK_UNDERSTANDING`: test whether wording and focus were understood;
- `TRAIN_MORE`: add one bounded logged example inside the frozen Point and known closure, using
  only already reviewed lesson assets; it may not commission or invent pixels live;
- `TRAIN_LONGER`: extend practice by a bounded, logged ordering of frozen mixed-practice items,
  without immediate identical repeats and with an explicit stop count;
- `REPLAY_LESSON`: replay only the frozen, fully accounted base path when the lesson's release
  predicate is true;
- `FINISH`: close conduct only after the frozen finish predicate is true;
- `ALARM`: freeze the lesson immediately.

Nonverbal picture-book demonstrations and scored selections are logged as `machine_control`
teacher emissions rather than spoken language. Every replay, `SHOW_CORRECT_OPTION`, and scored
machine action consumes one teacher-turn unit and alternates with one simulator observation or
selection, so the transcript and global turn budget account for the same execution.

There is no generic browser, cropper, generator, editor, search tool, or unrestricted dialogue
escape hatch during conduct. A missing crop is a lesson-material defect, not permission to invent
one live. A tool provider's success cannot substitute for the lesson's frozen pixel review.

## Alarm and freeze

Luna presses `ALARM` whenever it cannot preserve the Point, understandable language, scene truth,
answer contract, tool contract, chronology, role boundary, or stopping budget. The operator may
also stop manually. The harness automatically alarms on malformed alternation, an unlicensed
action or tool, an unprepared visual operation, unlicensed teacher language, or a budget breach.

An alarm appends one terminal event and changes the run to `alarm_frozen`. No further teaching
event may be appended. The independent reviewer still analyzes the frozen evidence and assigns
root cause; an alarm is not itself a diagnosis.

## Log and independent review

`events.jsonl` is append-only and hash-chained. State records its event count and chain tip. The
terminal manifest binds the lesson, specification, log, review packet, verdict, and any parent
repair receipt. Verification must fail if any logged bytes, ordering, hashes, or terminal bindings
change.

The fresh Sol reviewer grades these dimensions independently:

- lesson-plan waterproofing;
- Point/Topic separation and fidelity;
- Luna's judgment about which tested things belong and whether the lesson warrants fewer or more
  than the rough sixteen-item guideline;
- structural completeness and the declared square symmetry or justified exception;
- picture-book story compatibility and post-story comprehension;
- Luna's teaching routine;
- the decision to use or not use `TRAIN_MORE` and `TRAIN_LONGER`, plus the validity of any
  additional material or mixed-practice loop;
- calibration of Luna's post-lesson self-assessment against the raw log, including its separation
  of independent, scaffolded, contradictory, and not-demonstrated behavior;
- teacher-language closure and understandability;
- fidelity to Ninereeds' actual developmental stage rather than assumptions about an adult
  second-language learner;
- protocol integrity;
- visual grounding;
- fidelity of the Ninereeds simulation.

Failures identify an event where possible and name one root category: `lesson_plan`,
`visual_material`, `luna_routine`, `sol_simulation`, `harness`, `verifier`, `infrastructure`, or
`unresolved`. A pass requires every dimension, every required phase, complete Luna/Sol turn pairs,
at least one understanding check, no alarm, and no recorded failure.

Luna's report records phase outcomes, capability hypotheses tied to event sequences, remaining
difficulties, uncertainties, intervention effects, self-critique, alarm judgment, proposed closure
changes, and next-lesson implications. During rehearsal every proposed closure change is a
hypothesis only and cannot advance learner state. Later pipeline integration may consume only the
subset independently accepted by the fresh reviewer.

The reviewer records `luna_verified` when the report is calibrated, or
`sol_reconstruction_required` with explicit corrections when teaching evidence is usable but the
report is not. Poor reporting does not retroactively turn successful teaching into failed teaching,
but it prevents Luna's report from becoming canonical and counts against reporting qualification.
No next-lesson commission may start until one canonical outcome report exists.

## Repair without erasure

Never overwrite a failed, alarm-frozen, or passed run. A rerun must use a new directory and bind
the prior terminal manifest. Its repair receipt names the failure codes and root causes, explains
the repair, and proves changed artifact bytes with before/after SHA-256 values. A rerun with no
actual changed bytes is invalid.

Instructor qualification aggregates the mandatory adversarial scenarios. Every required scenario
must have one passing terminal manifest for the exact lesson and Instructor bundle; averages cannot
hide a failed boundary. During handhold mode this suite policy does not waive the rehearsal and
anonymous review of each individual lesson.

## Human-readable proof

Render every compiled lesson to `lesson.pdf` before rehearsal. The PDF is the canonical human
review projection: every exercise page places the exact image, literal crop, or highlight Luna
shows immediately beside the teacher dialogue, expected answer, and invariants. It also shows the
Point and selection rationale, captions, parent/crop coordinates and operation evidence, tool
limits, alarm rule, hashes, and operator checklist. A missing or undeclared visual is displayed as
a blocker, never hidden behind an asset ID. The lesson JSON remains machine authority. The PDF
never repairs, expands, or overrides it; regenerate the PDF whenever the source lesson bytes
change.

The deterministic harness is `scripts/rehearse_lesson.py`. The deterministic projection renderer
is `scripts/render_lesson_pdf.py`. Neither command calls a model provider, conducts training, or
advances learner state.
