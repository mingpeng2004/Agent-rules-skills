# AgentOS delegated autonomy v1.2

## AGOS-AUTO-001: goal and file driven work

The user's existing goal, constraints and DoD drive execution. Read the task,
working memory, evidence, checkpoint and decisions from disk on every restart.
Already authorized routine read/edit/test/build work proceeds immediately.
Do not ask preference questions for routine implementation details.

## AGOS-AUTO-002: five-minute preference delegation

For a material ordinary choice, write a complete recommendation, affected scope,
impact, rollback, known operations and verified factual basis using
templates/DECISION.json. Keep it within the existing goal and reversible.
Use bin/AgentOS-Decision.ps1 to persist it. Send the user the recommendation and
state that it will be adopted after five minutes without feedback. Only after
the notice is actually sent, call notify with its message reference. Creating a
file or planning a notice does not start the clock. Never invent notification
or feedback references. A local caller-supplied reference is not authentication.

At 300 seconds, evaluate records delegated_default under the prior delegation.
It never means user_approved, measured success, factual confirmation or E4
acceptance. User rejection, pause or changes supersede the recommendation,
including after adoption; stop future dependent work, assess executed changes
and preserve history. Changed proposals require a new decision ID and notice.

## AGOS-AUTO-003: gates that do not expire

Safety includes data deletion/irreversible changes, credentials, new network
access, dependencies, persistence, remote hosts, real actuators, flashing,
power, BIOS, paid purchases and security controls. Obtain explicit approval
with the required project/device checks. Unknown operation or risk is blocked.
Missing facts are investigated; elapsed time cannot make them known. Host tool
permission gates remain in force. User acceptance is recorded only from actual
acceptance evidence. Prepare, verify and deliver autonomous results without
waiting for ceremonial acceptance; keep any required physical/user acceptance
clearly pending. Do not redefine the user's goal or change locked SSOT by timeout.

## AGOS-AUTO-004: active loop and restart

1. Ingest new user feedback first; persist respond before evaluating deadlines.
2. Run evaluate on pending decisions at each Unit boundary and resume.
3. If a choice is waiting, continue independent ready Units. If nothing is ready,
   revisit deadlines in bounded intervals of at most 60 seconds while the host
   supports an active loop. Never sleep for five minutes in one blocking call.
4. Before dependent action, re-evaluate source/policy hashes and gates. A changed
   basis, clock rollback, missing file or unknown operation blocks adoption.
5. Save next_action, waiting decisions and deadline in the checkpoint. Resume
   from files after interruption; do not start the five-minute clock again.

No local rule installs a timer, resumes a closed conversation or authenticates
user messages. A host without a live loop/scheduler evaluates at its next active
cycle. No service, scheduled task or background persistence is installed here.

## Commands

```powershell
& "$env:AGENTOS_HOME\bin\AgentOS-Decision.ps1" propose -ProjectRoot $project -DecisionId choice_001 -ProposalPath $proposal
# Send the complete actual notice before the following call.
& "$env:AGENTOS_HOME\bin\AgentOS-Decision.ps1" notify -ProjectRoot $project -DecisionId choice_001 -NoticeRef 'actual message reference'
& "$env:AGENTOS_HOME\bin\AgentOS-Decision.ps1" respond -ProjectRoot $project -DecisionId choice_001 -Response pause -ResponseRef 'actual user message reference'
& "$env:AGENTOS_HOME\bin\AgentOS-Decision.ps1" evaluate -ProjectRoot $project
& "$env:AGENTOS_HOME\bin\AgentOS-Decision.ps1" status -ProjectRoot $project
```

Read outcome and proceed; exit code zero only means the inspection ran. Status
is read-only and never grants a choice. The tool selects no shell command and
performs no development/hardware action. Feedback and evaluation are serialized
by a local project lock; busy callers retry on their next loop, not indefinitely.
Snapshots and history are saved atomically. Same-permission agents can bypass
optional tools or alter files; strong enforcement needs a host-owned tool gateway
and authenticated feedback, which this file-based version does not claim.
