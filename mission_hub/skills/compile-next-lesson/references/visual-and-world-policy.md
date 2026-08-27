# Visual and grounded-world policy

## World-bible boundary

The authoritative workstation library is
`training_data/grounded_stories/assets/canonical/`. Keep recurring character references under
`characters/`, recurring locations under `locations/`, and bind all accepted files through
`reference_manifest.json`. Do not publish these references into the general image bank or Git.
Materialize only lesson-selected, hash-addressed copies into the trainbox cache.

Track only recurring, individually identifiable entities and reusable named locations.
Unnamed shoppers, passengers, workers, visitors, and crowd members remain extras and acquire no
persistent history.

Every recurring entry records its stable identifier and kind, canonical appearance or reference
assets, introduction lesson or story, earliest permitted use, home or location when relevant,
and stable relationships.

Established villagers may know one another by world-bible rule. Births, arrivals, moves,
adoptions, transfers, and first encounters must occur in an ordered introduction story. A later
story may depend on that introduction; it may not precede it.

For minds, distinguish the mind, its name, its symbol, a message, and the device through which
it communicates. A phone or icon may represent Errol or Ninereeds without becoming their body.

## Asset routing

Picture-book continuity assets and general teaching images are separate production tracks.

Use OpenAI ImageGen directly for canonical recurring characters, animals, locations, vehicles,
and objects; continuity-sensitive picture-book compositions; canonical seasonal, lighting,
weather, and state variants; and edits whose acceptance depends on preserving exact identity or
layout. A failed Flux attempt is not required before this route.

Use Flux for generic or one-off lesson imagery outside the canonical picture-book library, broad
noncanonical transformations, and detail-insensitive additions or substitutions where small
identity or layout drift is acceptable.

Neither model is an approval authority. Every output begins as a candidate and returns through
review. Only explicit operator approval and registration in `reference_manifest.json` makes a
reusable asset canonical. Protect evaluation selections and preserve the teaching claim.

## Master scenes and crops

For a complex picture-book page, freeze a scene inventory before generation: characters,
canonical references, objects, exact counts, actions, spatial relations, camera, style, and
forbidden extras. Validate every required fact after rendering.

Use a literal crop only when it resolves an explicit pointing or salience problem: for example,
isolating one object in a multi-object scene. Cropping is optional, not a completeness signal. Do
not crop a relational scene when the relation itself is the teaching object; a greeting, dialogue,
or turn-taking image must preserve the participating characters and their orientation. When a crop
is justified, create it with a deterministic image operation from the approved master, record the
parent asset and crop box, and never ask a generative model to redraw it. Create a second state,
such as an opened refrigerator, by identity-preserving edit of the master and review the entire new
state independently.

Apply relation-operand completeness to every visual claim. The shown image must contain every
entity, landmark, boundary, and amount of surrounding context needed to verify the relation. “The
cup is next to the toaster” requires the cup, the toaster, and legible spacing between them; a crop
showing only the cup cannot teach or test that Point. Pixel review evaluates the actual shown asset,
not facts remembered from its parent master.

Do not accept an image because it is attractive. Reject missing, duplicated, fused, floating,
miscounted, mislocated, mislabeled, or identity-drifting elements.
