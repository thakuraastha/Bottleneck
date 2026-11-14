# Gmail to Bottleneck (zero-cost cloud bridge)

This integration runs entirely in Google Apps Script and Cloud Run. Nothing
depends on the local machine.

1. Open <https://script.google.com> using the Gmail account that receives
   supplier failure messages.
2. Create a project named `Bottleneck Gmail Bridge`.
3. Paste `Code.gs` into the editor and run `setupBottleneckGmailBridge` once.
4. Approve Gmail read/label and external-request permissions.
5. In Gmail, apply the label `Bottleneck/Incoming` to a supplier failure email.

Within approximately one minute the email appears in the deployed Incidents
tab with `source_system=EMAIL`, its Gmail message ID, sender, subject, body, and
an evidence ID. The processed thread is moved to the
`Bottleneck/Processed` label so it is not submitted twice.
