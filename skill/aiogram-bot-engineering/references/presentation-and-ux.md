# Native Telegram Presentation and UX

Read this reference when the request is about how a native bot looks and feels:
screen composition, banner or cover art, button hierarchy, concise copy,
navigation, state design, accessibility, or removing generated-looking emoji
slop. Always read [dialogs and UI](dialogs-and-ui.md) when the deliverable
includes inline or reply keyboard composition or mechanics, and read
[the custom emoji system](custom-emoji-system.md) when icons are requested.

## Core contract

A polished native bot is a small interaction system, not a decorated message.
Establish hierarchy first; icons, color, and cover art may reinforce it but may
not carry it. Decorative emoji start at zero. Add an icon only when it makes an
action, state, category, or restrained brand accent faster to recognize.

When asked to “make it beautiful,” deliver these artifacts in order:

1. a `PresentationBrief` with the product constraints and art direction;
2. a screen map with navigation and state variants;
3. a state-decision matrix covering loading, empty, error, confirmation,
   success, and destructive behavior, with a reason for every `N/A`;
4. a `ScreenSpec` for each changed screen;
5. rendered message copy and keyboard rows;
6. icon tokens, never improvised Telegram IDs;
7. anti-slop and visual-QA results.

Do not replace this contract with a universal template applied unchanged to
every screen. A home menu, form step, confirmation, error, and receipt serve
different tasks.

Treat requests for “beautiful,” “premium,” or “more” emoji as requests for an
icon system, not permission to sprinkle familiar Unicode symbols. Read
[the custom emoji system](custom-emoji-system.md), define semantic tokens and
one style lock, then render verified assets. Until the registry is available,
show labels plus token annotations such as `Connect VPN [icon: connect]`; do
not make a final-looking mockup from arbitrary lightning, gems, globes,
sparkles, phones, and speech bubbles. Literal Unicode belongs only to an
explicit coherent screen-wide fallback mode.

## PresentationBrief

Record the decisions that keep later screens coherent:

| Field | Decision |
| --- | --- |
| Product and audience | What the bot does, for whom, and their familiarity |
| Top task | The one action the home screen should make easiest |
| Tone | For example calm, technical, playful, or premium; not a list of emoji |
| Surface | Native message/dialog or Mini App, with the reason |
| Cover role | None, brand, context, or content preview |
| Action hierarchy | Primary, secondary, navigation, destructive |
| Icon system | Semantic tokens, coherence group, exact pack lock or deterministic pack priority, capability, fallback mode |
| Lifecycle | Edit in place, send a durable event, or replace stale content |
| Required state decisions | Loading, empty, error, confirmation, success, and destructive: behavior or explicit `N/A` with reason for each |

Never shorten the state decision to only the states that are easy to render.
For every changed screen or flow, mark each of the six canonical states as
applicable with its copy/actions, or `N/A` with a concrete reason such as “this
read-only screen initiates no destructive operation.” An absent row is not an
implicit `N/A`.

Use a native message or dialog for compact menus and conversational flows. A
request for richer styling alone is not a reason to move to a Mini App. Use a
Mini App only when the task needs a genuinely browser-like surface such as a
dense dashboard, direct manipulation, or complex input.

## ScreenSpec

Describe every screen with the following semantic slots. This is an output
contract, not a requirement to expose an internal class named `ScreenSpec`:

```yaml
id: home_active
purpose: expose the connection action and current subscription state
content:
  heading: VPN ready
  status: Active until 24 September
  supporting: 2 of 5 devices connected
primary_action:
  label: Connect VPN
  intent: connection_instructions
  icon_token: connect
secondary_actions:
  - {label: Subscription, intent: subscription_details, icon_token: payment}
  - {label: Devices, intent: device_list, icon_token: devices}
navigation: {back: false, home: false, edit_in_place: true}
state_decisions:
  loading: disable duplicate connection requests and show current operation
  empty: show no connected devices and keep Connect VPN available
  error: preserve settings and offer Try again plus Support
  confirmation: N/A — this screen starts no irreversible operation
  success: show that connection instructions are ready and the next step
  destructive: N/A — no destructive action exists on this screen
```

The label is authoritative. Removing every `icon_token` must leave a complete,
usable screen. Keep trusted status in Telegram text; never place the only copy
of an expiry date, warning, price, or next action inside an image.

## Compose the native screen

### Cover

A cover earns its space when it establishes brand, identifies content, or
helps the user recognize the current area. Keep it quiet: one focal idea,
generous negative space, and no fake buttons or dense instructions. Account for
Telegram crops and dark/light surroundings. Repeating the heading, status, and
call to action in the cover, caption, and keyboard makes the screen noisier,
not clearer.

If localized text or frequently changing data matters, render it as Telegram
text instead of baking it into the image. Provide useful alternative context
in the caption when the image conveys information rather than decoration.

### Message

Lead with the current task or state, then the minimum supporting data needed to
choose an action. Prefer short semantic sections over a greeting, slogan,
instructions, status list, legal copy, and call to action all competing in one
message. Put policy or long help behind a dedicated action.

Formatting establishes structure. It does not justify ornamental headings,
emoji bullets, repeated arrows, or “premium” filler such as sparkles, rockets,
fire, gems, and pointing hands.

### Keyboard and emphasis

Use one primary action when the screen has a clear next step. Group secondary
actions by user task, not by visual symmetry alone. Keep Back or Home in a
stable place when the flow needs them.

| Style | Use |
| --- | --- |
| `primary` | The current screen's principal next action |
| `success` | A safe positive completion or explicit confirmation |
| `danger` | An irreversible or high-impact destructive action |
| default | Secondary actions and ordinary navigation |

Never color every button. Color, order, label, and icon must not disagree. For
example, “Open,” “Continue,” and “Pay” are normally primary; they are not
success merely because green looks attractive. A destructive action gets a
confirmation screen with the consequence stated in text.

### Message lifecycle

Edit the existing message for movement inside one compact interface: menus,
filters, pages, details, and back navigation. Send a new message for durable
events the user may need in history, such as a receipt, completed export, or
human support reply. Do not grow a navigation trail by sending a fresh menu on
every click. Acknowledge callbacks and recover stale buttons to a known safe
screen.

## State system

Design non-happy paths at the same time as the main screen:

| State | Required content and action |
| --- | --- |
| Loading | What is happening; prevent duplicate destructive submissions |
| Empty | What is absent and one useful creation or recovery action |
| Error | What failed, what remains safe, and retry or support action |
| Confirmation | Exact consequence, target, and confirm/cancel actions |
| Success | What changed and the next useful action; avoid celebration noise |
| Destructive | Explicit object and consequence; default focus stays safe |

Do not hide an error in a decorative banner. The text must explain the failed
operation and recovery path. Technical details belong in structured logs, not
in the user message.

## Anti-slop gate

Reject or revise the screen when any row fails:

| Check | Pass condition |
| --- | --- |
| Semantic necessity | Every icon maps to an action, state, category, or one deliberate brand accent |
| Coherence | Icons on the screen use one locked visual family or compatible coherence group |
| Independence | Labels, status, and consequences remain clear without icons, color, animation, or cover |
| Hierarchy | One principal action is obvious; secondary and navigation controls are quieter |
| Copy economy | Heading, body, cover, and buttons do not repeat the same claim |
| State completeness | Loading, empty, error, confirmation, success, and destructive each have behavior or a reasoned `N/A` |
| State honesty | Applicable non-happy states are not disguised as the happy state |
| Accessibility | No critical emoji-only control; informative imagery has equivalent text |

Specific rejection signals include emoji used as punctuation, decorative emoji
in every paragraph, a different pack chosen for each button, mixed Unicode and
custom styles without a screen-wide fallback decision, arrows that duplicate
layout, all buttons colored, a text wall before the main action, or critical
information existing only in the cover.

Do not “fix” slop with a universal numeric emoji quota. First remove every
icon, establish the hierarchy, then restore only semantic icons under the
screen's style lock. Prefer no icon to an inconsistent one.

## Visual QA

Static review of the spec is necessary but cannot predict client rendering.
Capture representative screens with production-like copy and verify:

- Telegram light and dark themes;
- iOS and Android clients, plus a narrow viewport;
- the longest supported localization and large dynamic values;
- custom emoji available and completely unavailable;
- active, empty, loading, error, and destructive-confirmation states;
- cover cropping, caption wrapping, keyboard row balance, and tap labels.

Fix hierarchy or copy before compensating with more imagery. The release gate
passes only when the icon-free variant is still understandable and the styled
variant looks like the same product across all tested states.

## Worked native menu

For a VPN home screen, the cover may show one quiet brand motif and the product
name. The message carries the real state:

```text
VPN ready
Subscription active until 24 September
2 of 5 devices connected
```

The first row contains `Connect VPN` as the primary action. Subsequent rows
group `Subscription` with `Devices`, then `Servers` with `Support`. Each label
is complete. The screen may request semantic tokens such as `connect`,
`payment`, `devices`, `servers`, and `support` from one coherent UI pack; it
does not place a second layer of emoji in the message text or illustrate those
tokens with arbitrary Unicode. The expired state
changes the status and primary action to `Choose a plan`. The error state says
which operation failed and offers `Try again` plus `Support`.

For accessibility guidance on emoji alternative text and informative images,
see [W3C technique H86](https://www.w3.org/WAI/WCAG22/Techniques/html/H86.html)
and the [GOV.UK image guidance](https://design-system.service.gov.uk/styles/images/).
