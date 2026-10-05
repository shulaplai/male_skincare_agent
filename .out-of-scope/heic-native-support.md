# Native HEIC / HEIF support

This project does not accept HEIC or HEIF at the API boundary. An unsupported format gets a
readable 415, and that is deliberate. We are **not** adding native HEIC decoding.

## Why this is out of scope

Not because it would be hard — `pillow-heif` exists and would slot in beside the Pillow that
is already a dependency. It is out of scope because **no HEIC ever reaches the backend in the
flow this project actually has**, so the code would be servicing an input that does not occur.

Measured 2026-10-05, reading the magic bytes of every file in the local `photos/` directory:

```
photos/ — 20 files
  JPEG 20    HEIC 0    PNG 0
```

All twenty are JPEG, **including the ones uploaded from the iPhone**. iOS Safari's
`<input type="file" accept="image/*">` transcodes HEIC to JPEG before the upload leaves the
device, so the request that would trigger the 415 has never been made. The last upload before
this measurement was 2026-10-01.

Adding the decoder anyway would cost a new dependency, a new native build requirement in the
Docker image, and a new attacker-facing decode surface — in exchange for handling zero
observed requests. For a single-user local-first app whose photos are skin selfies, the
decode surface is not worth widening for a hypothetical.

## What would change this

If the input path changes so that bytes arrive without a browser doing the transcode, HEIC
becomes real and this file should be deleted. Concretely:

- An iOS Shortcut, or a native wrapper app, POSTing the file directly
- Picking a photo via the Files app rather than through Safari's file input
- Any upload path that opens the file itself instead of handing it to a browser input

In any of those cases: delete this file and open a fresh issue. Per the triage convention,
the closed issue is not reopened — it is a historical record of a decision that was correct
for its input path.

## Prior requests

- [#24](https://github.com/shulaplai/male_skincare_agent/issues/24): "HEIC (iPhone default)
  now returns a readable 415 — support it natively?"
