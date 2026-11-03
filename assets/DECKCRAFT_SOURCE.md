# DeckCraft adaptations

Drunk Peanuts adapts animation easing and effect sampling from DeckCraft,
https://github.com/storytold/deckcraft, pinned to
`0d45a64db23baa0a4c8f9f7ac14c59c91b40fec9`.

Sources: `crates/anim/src/easing.rs`, `crates/anim/src/effects.rs`, and the
native timing/preset mappings in `crates/model/src/anim.rs` and
`crates/pptx/src/write/timing.rs`.

These adaptations use the MIT license option. `deckcraft-LICENSE-MIT.txt` and
`deckcraft-NOTICE.txt` retain upstream notices. The Python/Qt implementation is
modified for this app. ArtCraft/DeckCraft trademarks, logos, app UI and fonts are
not included. This is component reuse, not a claim of full DeckCraft or PowerPoint
feature parity.
