# Demo dashboard customization

Source copied from public Runtime `1eed25e51f1aaf98c86a0360b78b216028798aca` dashboard. No installed Runtime code or upstream repository was changed. This application serves `viewer-ui/dist` using public `DashboardConfig.directory`.

Changes: session detail fetches protected human review, renders its attested fields, disables decisions without a current review, and sends the displayed reference with answer/approval. New Run selects an explicitly allowed demo session instead of generating an unviewable random session ID. Pending links to session detail. The existing live-browser operator remains unchanged.

Build: `npm ci --prefix viewer-ui` then `npm run build --prefix viewer-ui`. The normal build checks TypeScript and preserves upstream/third-party license notices. Do not use the upstream Runtime-package build target here.

UI: open your session, read Review before deciding, enter an answer, then Submit Answer. After the draft completes use the session continuation input to request approval, read the reviewed proposal, and Approve or Deny. Refresh review if a stale-reference conflict is reported. New Run offers dinner, comparison, rice lunch, and vegetable side sessions. Existing sessions continue through their session page.

The mutation client preserves the selected explicit session ID through request and replay state. Browser read failures use availability wording, with paused/terminal guidance; control/input acknowledgement warnings remain separate. Verified by the mutation-browser regression test and production build.

## Browser recordings (public Runtime 923dd567)

The upstream protected `BrowserRecordings` component and optional API capability type were adopted from the pinned Runtime. The campus layout automatically selects a saved video and shows playback in the browser column after completion. Browser capture remains independent of live viewer pixels and purge/reconnect behavior. The Demo-local recording-session preparation endpoint selects a preauthorized immutable session grant before run/resume submission; it never repeats model calls.

The browser workspace is shown only on session detail pages. New Run links to the session; while a request is running it opens a new tab to preserve the request connection. Labels and metadata are collapsed by default within Advanced.

## Stable session workspace and navigation

The navigation rail collapses to named icons with an accessible toggle and persists the desktop setting locally. Below 768 px it uses the compact icon rail automatically without changing that desktop preference. Desktop sessions use a bounded two-column workspace: conversation scrolls independently, the composer remains mounted and disables itself when unavailable, and live view/playback occupy the same browser panel. Smaller screens stack the panels. Protected reviews have their own bounded scroll area.

The conversation retains its cached data across status changes and refreshes in place. Routine browser view refresh uses “Updating view”; pixel purging, ticket renewal, and browser/page identity checks are unchanged. Playback pauses when hidden during a resumed run. New recordings are selected automatically unless the viewer explicitly chooses one.
