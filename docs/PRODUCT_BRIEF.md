# Jarvis business requirements

Jarvis supports the proprietor of a precision machining company. Its main business workflow is taking an RFQ through drawing review, costing, an owner-selected selling price, a PDF, and an authorized customer email. The owner should be able to continue work while away from the office computer.

These requirements describe business intent. They do not prescribe frontend layout, navigation, renderer, motion, component structure, or libraries. They are not a claim that every capability is implemented.

## Commercial authority and facts

The owner releases prices, delivery dates, purchase commitments, drawings, and customer-visible status. Tools and stored records supply dimensions, hours, mass, rates, money, and dates. Models may propose, plan, and phrase; missing facts remain missing.

The owner chooses the selling price. A margin suggestion never edits it. A suggestion requires at least three won jobs matching primary process and tolerance class. Margin is (selling price - total cost) / selling price; total cost includes machining, material, outsource, and special tooling. Machine-hour rates already include overhead. Margin suggestions stay private and are not spoken to staff.

Delivery dates come from the owner rather than model calculations.

## Drawing and quotation workflow

Regular-customer intake may download drawings and read embedded text. Cloud vision requires customer consent and NDA eligibility; unknown consent denies it. Vision proposes cells. Typed or spoken corrections remain unconfirmed until accepted.

Revision, quantity, and material grade plus condition must be confirmed before handoff and send. They cannot be assumptions. Heat treatment, finish, and GD&T may be labelled assumptions. Assumptions stay visible through the quote and draft PDF.

The business sequence is drawing confirmation, labour-only or with-material scope, supplier enquiries as needed, machining strategy, hours at the machine-hour rate, owner price, labelled assumptions, PDF, and owner send.

A private owner workflow holds one live quote. Another RFQ waits until the live quote is parked or finished. A master-data edit suspends ambiguous send commands until its repeat-back is completed or cancelled. Resuming keeps the quote's step and resolved rates unless the owner explicitly requests repricing.

Assumption release requires the exact customer name from master data, not an alias. Stale or missing raw-material pricing requires that exact name plus the age shown; missing pricing has no age. Raw-material pricing over 30 days is stale. Outsource pricing over 30 days is a warning on the PDF. Backend proof and approval checks remain authoritative.

Customer email accepting an assumption clears its tag. A changed value remains unconfirmed and tagged until accepted. Unreadable replies leave tags intact. Messenger replies do not clear assumption tags.

A send attempt settles as sent, failed, or unknown. Unknown waits for a human decision. An already-sent quote does not send again on repeated authorization. UI feedback must reflect the actual outcome.

## Roles and records

The owner edits master data, distributes drawings, and sets customer-visible status. A marked inspector may release or correct inspection results containing job identity, measurements, and accept/reject/rework; that release carries no price or delivery date and does not change customer status.

Other staff may prepare question-only customer mail and supplier enquiries. Prices, dates, commitments, quote mail, margins, and drawing distribution require the appropriate owner authority. Unauthorized role actions are refused and surfaced to the owner.

Customer-visible states are Order received, In process, Halted, Inspection, Ready, and Dispatched. Missing status or delivery dates are referred to the owner. A Halted reason is shown only when the owner supplied it.

Drawing distribution requires the owner's request, an Active component, and an exact recipient. Only the registered supervisor group is eligible for group distribution; staff cannot pull drawings themselves.

Master-data changes preserve audit history. Rates use dated rows and business-date lookups. Sent quotes retain their proved rates; open quotes keep resolved rates until repriced. Phone edits require repeat-back of record, field, old value, new value, unit, and currency, followed by the exact new value.

## Continuation, voice, and offline work

The product intent includes a private owner phone continuation of the same quote and master records, not a duplicate quote. Messenger transport is not authorized for implementation by this brief; channel setup and scope need an explicit owner task.

With a drawing open, speech should prioritize a quote blocker once. Other replies can be spoken on demand; margin suggestions remain private and silent. Speech failure leaves text usable.

Hermes handles shop planning and tools. Local fallback, when configured, must still obtain business numbers from records. Offline work should allow local drawing review, confirmation, costing from stored records, and draft PDF preparation. Cloud vision is unavailable without connectivity. Restored connectivity must not silently retry unknown effects or release unreviewed offline output.

## Machining boundary

Jarvis may draft programs and setup charts. Human promotion is required. It does not transmit to a controller, DNC link, or machine network, and does not establish that a program is valid for another drawing revision.

## Scope of the UI redesign

Preserve data, capability bindings, confirmation state, provenance, and external-action approval behavior. The presentation and frontend implementation can change substantially. New business workflows require their own implementation task; visual demonstrations do not authorize external actions.
