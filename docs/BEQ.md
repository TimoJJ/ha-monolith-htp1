## Summary
Adds support for loading [BEQ (Bass EQ)](https://beqcatalogue.readthedocs.io/) correction filters directly from Home Assistant. BEQ filters apply bass correction profiles to the HTP-1's PEQ slots for specific movies and TV shows, compensating for rolled-off low-frequency content in many modern soundtracks.
Implementation matches the HTP-1 web UI (`BassEq.vue`) behavior — same slot range, value formatting, and `changemso` payload structure. Verified working on a real HTP-1 with Dirac ART and 3 subwoofers.
Inspired by the BEQ catalogue support added in [v2.0.0 of the Unfolded Circle integration](https://github.com/mase1981/uc-intg-monoprice-htp1/releases/tag/2.0.0) by [@mase1981](https://github.com/mase1981). Thanks for the original idea and implementation reference — the catalogue search approach and PEQ slot management logic were adapted from that work.
## New features
- **`monoprice_htp1.load_beq_filter` service** — Search the BEQ catalogue and load a filter by:
  - Movie title (case-insensitive substring match)
  - TMDB ID (supports numeric IDs, string IDs, and full themoviedb.org URLs)
  - Optional year and audio codec filters to narrow results when multiple matches exist
- **`monoprice_htp1.clear_beq_filter` service** — Remove the currently loaded BEQ filter
- **BEQ Filter sensor** — Shows the name of the currently active BEQ filter (or "None")
## Usage examples
### Basic service calls
```yaml
# Load by movie title
service: monoprice_htp1.load_beq_filter
target:
  entity_id: media_player.htp_1
data:
  title: "The Matrix"
  codec: "Atmos"
# Load by TMDB ID
service: monoprice_htp1.load_beq_filter
target:
  entity_id: media_player.htp_1
data:
  tmdb_id: "603"
# Clear current filter
service: monoprice_htp1.clear_beq_filter
target:
  entity_id: media_player.htp_1
```
### Auto-load BEQ on movie playback
Media player integrations like **Zidoo** and **Kodi** expose the TMDB ID of the currently playing movie in their entity attributes. You can use this to automatically load the correct BEQ filter whenever a movie starts playing:
```yaml
automation:
  - alias: "Auto-load BEQ filter on movie playback"
    trigger:
      - platform: state
        entity_id: media_player.zidoo
        to: "playing"
    condition:
      - condition: template
        value_template: >
          {{ state_attr('media_player.zidoo', 'media_tmdb_id') not in [None, ''] }}
    action:
      - service: monoprice_htp1.load_beq_filter
        target:
          entity_id: media_player.htp_1
        data:
          tmdb_id: "{{ state_attr('media_player.zidoo', 'media_tmdb_id') }}"
          codec: "Atmos"
  - alias: "Clear BEQ filter when playback stops"
    trigger:
      - platform: state
        entity_id: media_player.zidoo
        from: "playing"
    action:
      - service: monoprice_htp1.clear_beq_filter
        target:
          entity_id: media_player.htp_1
```
A similar automation works with Kodi, where the TMDB ID can be sourced from attributes exposed by the Kodi integration or a custom sensor via Kodi's JSON-RPC API.
## Technical details
- Filters written to PEQ slots on all active sub channels, finding empty slots by `gaindB === 0` (matching web UI logic)
- Uses the `underlying` catalogue field for `beqActive` so the web UI can resolve the display name
- Clear scans all 16 PEQ slots across sub1-sub5 (matching web UI `clearAllExistingBeqFilters`)
- Enables PEQ (`peqsw = true`) after loading (matching web UI `setGlobalPEQOn`)
- Sends integer values for whole numbers (e.g. `10` not `10.0`) matching web UI `convertFloat`/`JSON.stringify` behavior
- All clear + load ops sent in a single `changemso` batch
- `msoupdate` handler now supports `remove` operations (required for clearing BEQ state)
- BEQ catalogue fetched from `beqcatalogue.readthedocs.io` and cached in memory for 1 hour using HA's shared aiohttp session
- Services registered as entity services on the media player platform with full HA developer tools UI support
