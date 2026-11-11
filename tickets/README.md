# Service Center ticket templates

One file per NetX360 Service Center form (from the screenshots in
enhancements_sheet.pdf). The chat fills these fields from the advisor's words,
asks only for what is missing, shows a review card laid out like the form, and
sends the ticket. Sending a ticket changes nothing else.

- `category` / `request` / `request_type`: the form's header, sent as is.
- `fields`: the form's fields, with their labels, in form order.
- `ask_order`: the order the chat asks for missing required fields (one card per topic).
- `subject_prefix`: how a drafted Subject starts, in BNY's words ("Stop Payment: check 1043"),
  when the card title differs from the form name.
- `options` / `options_by_destination` / `required_when`: choice lists and conditional
  fields (rollover inquiry: Overnight needs a Tracking #; lockboxes per desk, mock values).
- `one_of`: at least one of these must be filled (Address Update: address or phone).
- `note`: the form's red note, shown on the review card. `note_on_review: false` leaves it
  off when it is only about filling in the form and is already met by then (Address
  Update's "Either the phone number or address are required.").

To connect BNY: map each field `id` to the Service Center API field of the same
form. Adding a form = adding a file here, a tools/<tool>.json schema and a skill
folder under skills/service-center/.

`check_copy.json` is a placeholder until the Check Copy form's screenshot arrives.
