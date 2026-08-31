# Dendritron: Notes for Ninereeds

**Date:** 2026-07-25
**Status:** Research note; ideas retained for later evaluation, no architectural change proposed
**Project relevance:** Modular cognition, functional ownership, continual learning, knowledge preservation, repair, LoRA/module lifecycle, orchestration

## Executive summary

Dendritron is an independent research project led by Richard A. Aragon. It combines biologically inspired nonlinear branch processing with a broader software-like discipline for managing learned functions: explicit ownership, restricted write scopes, quarantine before admission, certificates, immutable sharing, copy-on-write, local damage and repair, versioning, and bounded routing.

The project is interesting, but its public evidence does not presently justify treating it as a new foundation for AI or as a demonstrated successor to the perceptron. Its concrete implementations largely combine established ingredients:

- Gaussian/RBF or LVQ-style prototype branches
- nonlinear branch integration
- sparse or conditional experts
- frozen task-specific LoRA adapters
- parameter isolation for continual learning
- registries, hashes, tests, versioning, and copy-on-write

For Ninereeds, the useful contribution is not the current neuron implementation. The valuable part is the operational vocabulary and lifecycle discipline for learned modules. These ideas should be retained and revisited when Ninereeds gains multiple cognitive modules, saved knowledge regions, LoRAs, pruning, rollback, or repair infrastructure.

**Current decision:** Do not shoehorn the Dendritron architecture into BDH/Ninereeds. Preserve its systems principles as candidates for later module governance.

## What Dendritron proposes

Dendritron is best understood as an architectural philosophy rather than one definitive neuron equation. Its central principles include:

1. **Separated nonlinear branches**
   Inputs remain separated across multiple local nonlinear compartments before their outputs are integrated.

2. **Functional ownership**
   Every learned function or region has an explicit owner and defined write boundary.

3. **Quarantine and admission**
   New functions begin isolated. They must pass defined tests or certificates before they may influence the active system.

4. **Protected existing functions**
   Existing functions can be frozen, shared immutably, forked through copy-on-write, disabled, versioned, or repaired locally.

5. **Bounded routing**
   A router selects a limited set of relevant functional regions for each input.

6. **Recursive composition**
   Verified regions can become components of larger functional structures or “tissues.”

The strongest conceptual contribution may be this question:

> What if learned functions were managed like software components, with owners, interfaces, tests, versions, permissions, quarantine, dependency records, and localized repair?

## What currently exists

### 1. Starter-kit branch implementation

The public starter kit includes a small NumPy implementation. Its basic branches behave like Gaussian/RBF prototypes. A simplified branch activation is:

\[
a_b(x)=\exp\left[-\frac{1}{2}\left(\frac{d(x,c_b)}{\sigma_b}\right)^2\right]
\]

Each activation is combined with a branch output vector, and branches can be integrated using sum, maximum, or noisy-OR. Local learning moves selected prototype centres.

This is legitimate and inspectable software, but it is not yet evidence for a fundamental replacement of the perceptron. At this level, the mathematical core resembles established RBF/LVQ methods. In the elementary API, damaging a branch means marking it inactive; repairing it means reactivating it. The surrounding ownership, registration, certification, forking, and lifecycle machinery is more distinctive than the underlying branch mathematics.

### 2. “Dendritron Transformer”

The Transformer demonstration uses a frozen SmolLM2-360M backbone with separate LoRA packs trained for five small functional tasks. A router selects the relevant pack, while a registry can install, verify, remove, or replace adapters.

The archived experiment reports 97% autonomous routing and execution. However, this is a task-isolated functional-memory demonstration, not general lifelong learning. The backbone does not organically absorb arbitrary new knowledge without forgetting; instead, new abilities are stored in separately frozen adapter packs. Forgetting is avoided because training a new pack does not modify earlier packs.

This is useful engineering and directly relevant to possible Ninereeds module management, but it should not be mistaken for a demonstrated new cognitive substrate.

### 3. Native10 vision model

Native10 is described as a from-scratch CIFAR-100 architecture containing:

- a shared patch-based sensory field
- 1,000 fine-class routing scouts
- 20 category-owned colonies
- 45 local experts per colony
- rotating training groups of 15 experts
- all 45 experts reactivated for inference
- approximately 5.23 million parameters

The reported result is 53.51% CIFAR-100 top-1 accuracy after a 240-second A100 training budget. Rotating microcolonies reportedly increased throughput by 55% over the preceding version and improved accuracy by 2.37 percentage points.

This result currently lacks a matched CNN, Mixer, or sparse-MoE baseline under the same parameter and wall-clock budget. At the time of review, the Native10 source, checkpoint, and full result archive were not found in the public starter-kit repository. It should therefore be treated as an internally reported, not yet independently reproducible, result.

## Evidence assessment

### Boolean demonstrations

The project reconstructs all 65,536 four-input Boolean functions and recursively calculates long parity expressions. This demonstrates representability and explicit functional composition. It does not show that a new learning rule discovers these functions more efficiently than established approaches, because branches or minterms are installed from the known truth table.

### Optical Digits continual learning

The archived Optical Digits experiment reports:

- 98.11% final accuracy
- 0.65% forgetting in a class-incremental setting

The concrete system is an LVQ-like model with 16 class-local prototypes per digit. New classes receive new parameters, while old prototypes remain untouched. This is a favorable setting for structural isolation and demonstrates that the ownership approach can work, but it is not yet a test of the full proposed architecture.

### Permuted-MNIST

A repository experiment without task ID at inference reported:

- Dendritron tissue: 67.3% average accuracy
- replay: 90.2%
- EWC: 76.6%
- joint training: 95.6%

Forgetting was relatively low, but routing and capacity were weak, and the normal certificate threshold rejected every task. This is important negative evidence: explicit isolation protects old functions, but protection alone does not solve representation capacity, generalization, or routing.

### Overall evidence level

The public starter kit and archived experiments are real and unusually candid about their limitations. The strongest claims surrounding the project—replacement of the perceptron, repaired foundations of AI, or the end of dependence on NVIDIA-style hardware—run far ahead of the demonstrated results.

## Relationship to prior work

Most individual ingredients have established precedents:

- nonlinear dendritic subunits before somatic integration
- RBF networks and learning vector quantization
- mixture-of-experts and conditional computation
- progressive networks and parameter isolation
- masks, adapters, and LoRAs
- dendritic gating in continual-learning systems
- registries, immutable artifacts, dependency hashes, tests, and copy-on-write

Poirazi and Mel’s 2003 work described pyramidal neurons as resembling a two-layer network: nonlinear dendritic subunits followed by integration at the soma. More recent artificial and spiking systems have also used multiple nonlinear dendritic branches and dendritic gating.

The potentially novel contribution is therefore the particular bundle, the vocabulary of functional ownership, and the attempt to turn these principles into one coherent lifecycle for learned functions.

## Claims that should not guide Ninereeds decisions

The following claims should be treated as promotional rather than established:

- A single-layer perceptron’s inability to solve XOR does not mean modern neural networks rest on a mathematically broken foundation. Multilayer networks solve XOR; Minsky and Papert established limits of a particular machine class.
- Backpropagation was not invented merely to conceal or patch the perceptron’s failure.
- The current experiments do not demonstrate a general successor to conventional neurons or deep networks.
- Native10 was implemented with PyTorch, automatic differentiation, tensor operations, and an NVIDIA A100. A different organization of experts does not by itself make matrix-oriented accelerators irrelevant.

The technical documents and repository appear more careful than some public promotional framing. Decisions should be based on runnable code and matched experiments, not the rhetoric.

## Why this is relevant to Ninereeds

Ninereeds already points toward a multi-component cognitive system:

- BDH as continuity, identity, and learned internal structure
- an external language centre, presently considering mBERT or a similar fixed multilingual encoder
- SigLIP2 or another vision pathway
- possible arithmetic, reasoning, or specialized cognitive modules
- saved LoRAs or extracted knowledge regions
- an orchestrator and executor with deliberately limited cognitive horizons
- future pruning, preservation, rollback, and repair mechanisms

Dendritron’s present architecture should not replace or distort these plans. Its governance concepts, however, align closely with earlier Ninereeds ideas:

- modules should have explicit responsibilities
- no component should write indiscriminately into another component’s state
- newly trained structures should not become authoritative merely because training completed
- preserved knowledge should remain addressable and reversible
- removal or failure of one module should have bounded consequences
- modular attachment should become a natural mode of growth rather than a late collection of bolted-on tools

This is especially relevant to the idea that inaccessible or pruned knowledge need not be destroyed. It could be extracted into an indexed artifact, given lineage and validation metadata, and reattached if needed.

## Candidate principles to borrow later

When Ninereeds has a real module registry or knowledge lifecycle, consider recording the following for each module, adapter, extracted knowledge artifact, or protected region:

| Field | Purpose |
| --- | --- |
| Functional owner | Identifies the component responsible for the capability |
| Write scope | Defines exactly which state the module may modify |
| Version | Makes behavior and training state traceable |
| Content/dependency hashes | Detects drift and records exact dependencies |
| Parentage | Records the source module, checkpoint, or knowledge region |
| Copy-on-write lineage | Preserves ancestry when a protected function is forked |
| Admission certificate | Defines tests required before activation |
| Regression certificate | Protects existing behavior from damage |
| Routing authority | Defines which router may invoke or suppress the module |
| Activation statistics | Shows whether the module is useful, dormant, or over-selected |
| Health history | Records failures, drift, interventions, and repairs |
| Damage/removal test | Measures what actually breaks when the module is disabled |
| Rollback target | Provides a known safe prior version |
| Retirement state | Distinguishes dormant, quarantined, superseded, and deleted artifacts |

These should remain candidate fields until the system has enough real modules to reveal which metadata is genuinely useful.

## A possible lifecycle for future Ninereeds modules

This is not an implementation plan yet, but a useful template to revisit:

1. **Create in quarantine**
   Train or import a module without allowing it to affect authoritative behavior.

2. **Record provenance**
   Store its parent checkpoint, dataset/curriculum slice, training configuration, hashes, and intended function.

3. **Run capability tests**
   Verify that the module performs its claimed task.

4. **Run protected regressions**
   Test effects on identity, language consistency, existing knowledge, routing, and safety constraints.

5. **Admit with bounded authority**
   Give the module a limited routing scope and explicit rollback target.

6. **Observe real use**
   Record activation frequency, confidence, errors, collisions, latency, and downstream effects.

7. **Repair, fork, or retire locally**
   Prefer bounded intervention over global retraining when the failure is demonstrably localized.

8. **Retain reversible history**
   Keep useful superseded states addressable until there is evidence that permanent deletion is safe.

## What not to implement prematurely

Do not introduce the following merely because Dendritron names them:

- an RBF/LVQ branch layer inside BDH
- complex certificates before Ninereeds has stable behavioral tests
- elaborate ownership metadata for components that do not yet exist
- a router before there are enough modules to justify routing
- copy-on-write infrastructure before actual mutation conflicts appear
- “damage and repair” demonstrations that only toggle modules off and on

The right sequence is to let Ninereeds’ concrete system create the need, then adopt the smallest governance mechanism that addresses a real failure mode.

## Revisit triggers

Reopen this note when any of the following becomes active work:

- designing the Ninereeds module registry
- integrating mBERT or another language centre
- integrating SigLIP2 or a vision projector
- saving, indexing, attaching, or retiring LoRAs
- extracting knowledge before pruning
- implementing model/module rollback
- defining executor or orchestrator capability boundaries
- adding automated regression suites or admission gates
- diagnosing catastrophic forgetting localized to particular regions
- evaluating independent reproduction of Native10 or later Dendritron models

At that point, compare Dendritron’s current repository and evidence with the actual Ninereeds implementation. Borrow individual principles only where they solve an observed problem.

## Questions for a future review

1. Has Native10 become publicly reproducible, with code, checkpoints, logs, and matched baselines?
2. Has Dendritron demonstrated learning advantages beyond structural parameter isolation?
3. Can its router handle task ambiguity without a task ID and outperform replay or conventional continual-learning baselines?
4. Do certificates predict real robustness, or do they merely restate held-out accuracy thresholds?
5. Is local repair genuinely learned, or is it still administrative replacement/reactivation?
6. Does the architecture scale beyond favorable class-local prototype problems?
7. Which ownership fields have proven operationally useful in the project’s own later experiments?
8. Which Ninereeds components now have actual write conflicts, regression risks, or lifecycle needs?

## Project and background links

- Dendritron starter kit: <https://github.com/MMVFIRM/dendritron-starter-kit>
- Repository experiment notes: <https://github.com/MMVFIRM/dendritron-starter-kit/blob/main/docs/EXPERIMENTS.md>
- Comprehensive preprint supplied for review: <https://docs.google.com/document/d/1LSw5AS87dtxxJkwcVGEh7lgH1Ajhqn7K/edit>
- Second supplied technical document: <https://docs.google.com/document/d/1A-8tO1d8wfJzLy_imTU5MURTgZjmYABKMLhwJm0wjzc/edit>
- Poirazi and Mel, 2003, *Pyramidal Neuron as Two-Layer Neural Network*: <https://pubmed.ncbi.nlm.nih.gov/12670427/>
- DendSN preprint: <https://arxiv.org/abs/2412.06355>

## Bottom line

Dendritron is neither nonsense nor, on present evidence, a new foundation for AI. It is an imaginative alpha-stage research program whose architectural claims remain weakly demonstrated, but whose software-like treatment of learned functions is highly compatible with Ninereeds’ long-term direction.

For now:

- preserve the idea
- watch the project
- do not change BDH around it
- revisit its ownership, quarantine, certification, lineage, and rollback concepts when Ninereeds has real modules that require such machinery
