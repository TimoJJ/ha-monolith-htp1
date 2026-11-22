# Bass EQ (BEQ) filters

Load [BEQ (Bass EQ)](https://beqcatalogue.readthedocs.io/) correction filters onto the HTP-1 from Home Assistant. A BEQ filter is a set of bass corrections made for a specific movie or TV show, compensating for the rolled-off low frequencies in many modern soundtracks. The integration looks the title up in the BEQ catalogue and writes the filters to the HTP-1's PEQ slots. You can load a filter by hand or automatically when playback starts.

## Requirements

- The HTP-1 is connected, so its media player entity is available.
- Home Assistant can reach `beqcatalogue.readthedocs.io`.
- Free PEQ slots on the subwoofer channels (see [How loading works](#how-loading-works)).

## Services

Both services target the HTP-1 media player entity.

### `monoprice_htp1.load_beq_filter`

Searches the BEQ catalogue and loads the best matching filter. Give either `title` or `tmdb_id`.

| Field | Description |
|---|---|
| `title` | Movie title. Case-insensitive substring match. |
| `tmdb_id` | The Movie Database ID: a number, a string, or a full themoviedb.org URL. If both `tmdb_id` and `title` are given, `tmdb_id` is used and `title` and `year` are ignored. |
| `year` | Release year. Narrows a title search when several entries match. |
| `codec` | Audio codec, for example `Atmos`, `DTS:X` or `TrueHD`. Case-insensitive substring match. Works with both `title` and `tmdb_id`. |
| `edition` | Edition, for example `Extended Cut` or `Director's Cut`. An exact edition first, otherwise editions that contain the text; case is ignored. Works with `title`, `tmdb_id` and `digest`. |

If several catalogue entries match, the one with the most filters is used. To load one specific entry instead, pass its `digest` from `search_beq_filter`:

| Field | Description |
|---|---|
| `digest` | Digest of one catalogue entry (returned by `search_beq_filter`). Loads exactly that entry; `title`, `tmdb_id` and `year` are then ignored. A few titles have several entries with the same filters for another audio type or edition, and those share a digest: give `codec` and `edition` as well to pick the one whose name shows your audio type and edition. Without `edition`, the entry without an edition is preferred. |

### `monoprice_htp1.search_beq_filter`

Searches the BEQ catalogue and returns every matching entry without loading anything, so you (or a dashboard, a remote or an automation) can choose one. Takes the same `title`, `tmdb_id`, `year` and `codec` fields as `load_beq_filter`, plus `limit` (default 20, max 100). A title search returns the exact title matches when there are any (case, accents and punctuation ignored), otherwise every title that contains the text.

It returns a response (call it with `response_variable`, or tick *Return response* in Developer tools):

```yaml
media_player.htp_1:
  count: 3
  matches:
    - digest: 847c19c4a09c4bd9ecd4b21e19e3c4da06721af32dae01d06a59188758e19469
      title: Tenet
      year: "2020"
      author: aron7awol
      edition: null
      audio_types: ["DTS-HD MA 5.1"]
      mv: "-6.5"
      filter_count: 4
      note: null
      warning: null
      label: Tenet (2020) (-6.5 gain) BEQ DTS-HD MA 5.1
      tmdb_id: 577922
    # ... one entry per catalogue version (mobe1969, remixmark, ...)
```

Load the one you picked:

```yaml
service: monoprice_htp1.load_beq_filter
target:
  entity_id: media_player.htp_1
data:
  digest: 847c19c4a09c4bd9ecd4b21e19e3c4da06721af32dae01d06a59188758e19469
```

### `monoprice_htp1.clear_beq_filter`

Removes the currently loaded BEQ filter.

## Sensor

The **BEQ Filter** sensor shows the name of the loaded BEQ filter, or `None` when no filter is loaded.

## Examples

Load by movie title:

```yaml
service: monoprice_htp1.load_beq_filter
target:
  entity_id: media_player.htp_1
data:
  title: "The Matrix"
  codec: "Atmos"
```

Load by TMDB ID:

```yaml
service: monoprice_htp1.load_beq_filter
target:
  entity_id: media_player.htp_1
data:
  tmdb_id: "603"
```

Clear the current filter:

```yaml
service: monoprice_htp1.clear_beq_filter
target:
  entity_id: media_player.htp_1
```

### Load BEQ automatically when a movie starts

Media players such as **Zidoo** and **Kodi** can expose the TMDB ID of the movie that is playing in their entity attributes. This automation loads the matching BEQ filter when playback starts and clears it when playback stops:

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

A similar automation works with Kodi. The TMDB ID can come from attributes exposed by the Kodi integration or from a custom sensor that reads it through Kodi's JSON-RPC API.

## How loading works

- The filters are written to the PEQ slots of the subwoofer channels. If the PEQ location is **pre**, only the first subwoofer channel (shown as LFE) is used. If it is **post**, every subwoofer channel that is present is used.
- Any BEQ filter that was loaded earlier is cleared first.
- Slots that hold your own filters are skipped. A slot counts as free when its gain is 0 and its filter type is not all-pass, low-pass or high-pass.
- The PEQ has 16 slots. If the catalogue entry has more filters than there are free slots, the extra filters are skipped and a warning is written to the Home Assistant log.
- The PEQ is switched on after the filter is loaded.
- Clearing and loading are sent to the HTP-1 as one change.
- The filter name is stored so that the HTP-1 WebUI can show it.
- The BEQ catalogue is downloaded once and cached in memory for one hour.

## Errors

The services fail with an error in Home Assistant when:

- neither `title` nor `tmdb_id` is given,
- the HTP-1 is not connected,
- the catalogue cannot be downloaded,
- the TMDB ID cannot be read,
- no catalogue entry matches, or the matching entry has no filters,
- the filter cannot be written to the HTP-1.

## Credits

The BEQ catalogue support was inspired by [version 2.0.0 of the Unfolded Circle integration](https://github.com/mase1981/uc-intg-monoprice-htp1/releases/tag/2.0.0) by [@mase1981](https://github.com/mase1981). The catalogue search and the PEQ slot handling were adapted from that work.
