# Open Source Summit Japan + ALS + ELC Asia 2026 CFP Submission

Tokyo, 7-9 Dec 2026 · **CFP closes Mon 24 Aug, 23:59 JST (20:29 IST)**
Notifications 23 Sep · Schedule 28 Sep
Submit at: https://sessionize.com/oss-als-elc-japan-26/

One proposal per track. Track selected: Open AI + Data.

---

## Session Title

**Building and Sharing Open RL Environments with OpenEnv**

*Settled. Names the project and matches the build-then-share arc, without the
unearned "scaling" claim of the earlier variant.*

## Track

**Open AI + Data**: "open models, LLM frameworks, inferencing, ethics."

## Session Format

**Session Presentation** (30-40 min)

## Audience Level

**Intermediate**. Assumes Python and familiarity with LLM APIs. No reinforcement
learning background required; the talk builds the concepts it needs.

---

## Description

Post-training is where model capability is now won, and reinforcement learning is the method. That makes the RL environment a central piece of infrastructure: the sandbox a model acts in, the tools it can call, and the grader that scores it. It has many moving parts, from task sets and tool schemas to session state and a transport to the trainer. Every team wires them together differently, so environments stay locked to the setup they were born in.

OpenEnv is one effort to standardize them. Launched as a partnership between Meta-PyTorch and Hugging Face, with a committee of eleven organizations steering where the specification goes, it gives an environment a single interface, a Docker package, and a hub to publish it on. The same container also runs as an eval harness, since the tools and grader that train a model are the ones that score it.

Drawing on the speaker's work as an OpenEnv contributor, this talk covers what the standard asks of an environment, builds one end to end (a tool, a task set, a reward, a served container), then publishes it so anyone can pull it into their own training run. It closes with the failure modes worth knowing before writing a grader of your own.

## Benefits to the Ecosystem

Small open models are where most teams can realistically work, and sovereign AI efforts increasingly need to post-train their own rather than call someone else's API. Both depend on RL environments, and today almost none are reusable. Each is assembled differently, wired to a single trainer, and thrown away after one run, which leaves the benefit of RL concentrated among the few labs that can afford to rebuild the harness every time.

A shared standard changes that arithmetic. If an environment is a container with one interface and a hub to publish it on, a small team can pull a coding, terminal, or domain-specific environment off the shelf and spend its compute on training instead of plumbing. Because the same container that trains a model also evaluates one, a published environment does double duty: a reproducible benchmark anyone can rerun, not only a training target. That matters most where evaluation is hardest to come by, on a language or a regulatory domain no public benchmark covers, and it is exactly what a sovereign effort can contribute back.

This talk treats the OpenEnv specification as an open question rather than a finished product, so attendees leave able to build an environment, publish it for others to train against, and argue with the spec. OpenEnv is BSD-3-Clause and the environments shown are Apache-2.0, all of it runnable.

---

## Talk Outline (not submitted, your reference)

| # | Beat | Existing slides |
|---|------|-----------------|
| 1 | Post-training is the lever; RL is the method. Verifiable rewards, and why the input became an environment rather than a dataset. | `Paradigm` → `GRPO`, `Unlock`, `Scale` |
| 2 | The moving parts. Tasks, tool schemas, observations, session state, sandbox, reward, termination, transport, and why every team wires them differently. | `Traditional`, `GymAPI`, `Analogy`, `Contrast`, `Anatomy`, `Definition`, `Components` |
| 3 | OpenEnv as the standardization effort: a Meta-PyTorch and Hugging Face partnership, an eleven-org steering committee, BSD-3-Clause, and what the spec commits you to. | `WhyOpenEnv`, `OpenEnv` |
| 4 | Build one: tool → tasks → reward → serve. | `BuildTool` → `BuildServe`, `OpenEnvCLI` |
| 5 | Share it. Docker package, push to the Hub, someone else pulls it into their trainer, then train against it with TRL to prove the loop closes. | `OpenEnvCLI`, `TRL`, `TRLCode`, `ExampleEnvs` |
| 6 | Closing: grader failure modes. Three real reward-hacking cases, the healthy-looking curves, the rules. | `rh/*`, `rh2/*` |
| 7 | How to contribute: publish an environment, comment on the spec. | `NowWhat` |

**Cut:** the six-framework comparison, Repo2RLEnv, most GRPO internals.
**Held back:** the multi-harness / proxy material (`multi-harness-training` deck,
OpenEnv PR #1036). It does not fit a build-and-share arc. Better as its own talk,
or as one slide under beat 5 if you want the upstream-contribution signal on stage.

---

## Speaker

**Name:** Adithya S Kolavi
**Tagline:** Post-Training & RL, Hugging Face
**Company:** Hugging Face
**Email:** adithyaskolavi@huggingface.co
**Country of residence:** India

### Biography (456 / 500 chars)

Adithya S Kolavi works on post-training and reinforcement learning at Hugging Face, where he builds open RL environments and training recipes and contributes to OpenEnv. He was previously at Apple and Microsoft Research, and founded CognitiveLab, an open-source-first research lab that received a six-figure grant from Meta. He wrote the ultimate guide to RL environments, read by over 30,000 people, and has 13k+ stars across his open source repositories.

### Photo

`tutorials/slides/rl-environments-101-amd/src/assets/adithyask.jpeg`. Cropped to a
square, so check the crop.

### Links

- OpenEnv PR #1036 (multi-harness): https://github.com/huggingface/OpenEnv/pull/1036
- Guide: https://huggingface.co/spaces/AdithyaSK/rl-environments-guide
- Code (Apache-2.0): https://github.com/adithya-s-k/RL_Envs_101
- Live deck: https://adithyask-rl-environments-101-slides.static.hf.space
- OpenEnv: https://github.com/huggingface/OpenEnv

---

## Remaining form fields

- **Submitter and speaker?** Yes. No co-speakers, which avoids the panel-composition rules entirely.
- **Presented before?** Yes. Earlier versions at **AMD AI Dev Day India** and a **Hugging Face × Red Hat** event. This version is re-cut for an open-source-infrastructure audience: OpenEnv's spec and governance are foregrounded, and the multi-harness and reward-hacking material is new.
- **Presentation language:** English
- **Speaker Office Hours:** Yes. Answer text under Office Hours Topics below.
- **AI acknowledgement / Code of Conduct / Inclusivity:** tick all three (skim the Inclusive Speaker Orientation once; it is short).
- **Travel funding:** non-binding and does not affect review. If Tokyo is not already covered, tick yes and apply separately at events.linuxfoundation.org/about/travel-fund-request/
- **Demographics:** optional and confidential, so your call.

---

## Office Hours Topics

Designing an RL environment from scratch: how to turn a task somebody already cares about into tasks, tools, state, and a reward, and which of those decisions are expensive to change later. I am happy to work through a specific environment somebody has in mind and say plainly whether RL is even the right tool for it. Debugging rewards is the other half of that: why a run with a healthy-looking reward curve can be teaching the model nothing, how to spot reward hacking by reading trajectories rather than metrics, and how to build a grader you can trust before spending compute on it. This applies equally to eval harnesses, so it is useful to people who are not training anything. Post-training a small model on a realistic budget: what GRPO needs, where TRL and OpenEnv fit together, and what is genuinely achievable on modest hardware versus what needs a cluster. Publishing environments and contributing to OpenEnv, including how the spec is governed and where feedback actually goes.
