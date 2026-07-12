;; ============================================================================
;;  LibriSense — planning domain
;; ----------------------------------------------------------------------------
;;  Classical PDDL with action costs (PDDL level: :typing + :action-costs).
;;
;;  Why classical-with-costs and not PDDL 2.1 numeric/durative?
;;  Our planner is Fast Downward (seq-opt-lmcut), an OPTIMAL classical planner.
;;  It does not support durative actions or continuous numeric fluents — those
;;  need a temporal/numeric planner (ENHSP, OPTIC). We therefore discretise the
;;  environment (light: dark vs. bright-enough; CO2: ok vs. high; session:
;;  focusing vs. break-due) in the processing layer and let Fast Downward find
;;  a cost-optimal action sequence. Action costs encode the LibriSense
;;  objectives: comfort (light), air quality (ventilation), break hygiene, and
;;  energy thrift (switching the lamp off when a zone empties).
;;
;;  The decision of *which* goal atoms are active right now lives in the
;;  problem generator: it reads the live world state (library/state) and emits
;;  a ground goal. The planner decides *how* to reach it cost-optimally.
;; ============================================================================
(define (domain librisense)
  (:requirements :typing :action-costs :negative-preconditions)

  (:types zone)

  (:predicates
    (occupied ?z - zone)        ; someone is present (from the motion sensor)
    (lamp_on ?z - zone)         ; reading lamp (Plugwise Circle+ relay) is on
    (dark ?z - zone)            ; illuminance below the comfort threshold
    (co2_elevated ?z - zone)    ; CO2 proxy in the middle band (~800..1100 ppm)
    (co2_high ?z - zone)        ; CO2 proxy in the high band (> ~1100 ppm)
    (ventilating ?z - zone)     ; ventilation currently engaged
    (break_due ?z - zone)       ; focus session has run long enough for a break
    (break_suggested ?z - zone)); a break reminder has been issued

  ;; pulse-vent-cost / full-vent-cost are STATIC per problem instance: the
  ;; problem generator computes them from live outdoor temperature using the
  ;; heat-loss relation Q_loss ~ Qv x (Tin - Tout) from the team's window-
  ;; control planning report (docs/Window_Control_Preliminary_Report.pdf).
  ;; Cold outside -> full (long) ventilation becomes expensive, so the
  ;; cost-optimal plan switches to short pulse ventilation — the report's
  ;; winter recommendation, realised via planning instead of rules.
  (:functions (total-cost) (pulse-vent-cost) (full-vent-cost))

  ;; --- Comfort: light an occupied, dark zone -------------------------------
  ;; Cheap, because comfort for present learners is a priority.
  (:action turn_on_lamp
    :parameters (?z - zone)
    :precondition (and (occupied ?z) (dark ?z) (not (lamp_on ?z)))
    :effect (and (lamp_on ?z)
                 (not (dark ?z))
                 (increase (total-cost) 2)))

  ;; --- Energy: switch the lamp off once a zone empties ---------------------
  ;; Cheapest action — we actively want this to happen for energy thrift.
  (:action turn_off_lamp
    :parameters (?z - zone)
    :precondition (and (not (occupied ?z)) (lamp_on ?z))
    :effect (and (not (lamp_on ?z))
                 (increase (total-cost) 1)))

  ;; --- Air quality: leveled ventilation (window-control report, §7-9) ------
  ;; Three actions give the planner a REAL choice on high CO2:
  ;;   [full_ventilate]                    cost = full-vent-cost
  ;;   [pulse_ventilate_step, pulse_...]   cost = 2 x pulse-vent-cost
  ;; Warm outside -> full is cheaper (one long airing). Cold outside -> the
  ;; heat-loss term makes full expensive and two gentle pulses win.

  ;; Short pulse: clears the middle band entirely.
  (:action pulse_ventilate
    :parameters (?z - zone)
    :precondition (and (occupied ?z) (co2_elevated ?z))
    :effect (and (ventilating ?z)
                 (not (co2_elevated ?z))
                 (increase (total-cost) (pulse-vent-cost))))

  ;; Short pulse on high CO2: knocks it down one band (high -> elevated).
  (:action pulse_ventilate_step
    :parameters (?z - zone)
    :precondition (and (occupied ?z) (co2_high ?z))
    :effect (and (ventilating ?z)
                 (not (co2_high ?z))
                 (co2_elevated ?z)
                 (increase (total-cost) (pulse-vent-cost))))

  ;; Long airing: clears high CO2 in one go, but pays the full heat loss.
  (:action full_ventilate
    :parameters (?z - zone)
    :precondition (and (occupied ?z) (co2_high ?z))
    :effect (and (ventilating ?z)
                 (not (co2_high ?z))
                 (increase (total-cost) (full-vent-cost))))

  ;; --- Break hygiene: nudge a long focus session --------------------------
  (:action suggest_break
    :parameters (?z - zone)
    :precondition (and (occupied ?z) (break_due ?z))
    :effect (and (break_suggested ?z)
                 (not (break_due ?z))
                 (increase (total-cost) 1)))
)
