/**
 * Zero-cost Gmail -> Bottleneck bridge.
 *
 * Run setupBottleneckGmailBridge() once from Google Apps Script while signed
 * into the mailbox that receives supplier alerts. The cloud trigger then polls
 * unread messages carrying the Gmail label "Bottleneck/Incoming" and sends
 * their verified content to the deployed Cloud Run ingestion endpoint.
 */

const BOTTLENECK_API =
  "https://bottleneck-545600829568.asia-south2.run.app/integrations/email/ingest";
const INCOMING_LABEL = "Bottleneck/Incoming";
const PROCESSED_LABEL = "Bottleneck/Processed";

function setupBottleneckGmailBridge() {
  getOrCreateLabel_(INCOMING_LABEL);
  getOrCreateLabel_(PROCESSED_LABEL);

  ScriptApp.getProjectTriggers()
    .filter((trigger) => trigger.getHandlerFunction() === "syncSupplierFailureEmails")
    .forEach((trigger) => ScriptApp.deleteTrigger(trigger));

  ScriptApp.newTrigger("syncSupplierFailureEmails")
    .timeBased()
    .everyMinutes(1)
    .create();

  return "Bottleneck Gmail bridge installed. Label a supplier email Bottleneck/Incoming.";
}

function syncSupplierFailureEmails() {
  const incoming = getOrCreateLabel_(INCOMING_LABEL);
  const processed = getOrCreateLabel_(PROCESSED_LABEL);
  const threads = GmailApp.search(`label:"${INCOMING_LABEL}" -label:"${PROCESSED_LABEL}"`, 0, 20);

  threads.forEach((thread) => {
    thread.getMessages().forEach((message) => {
      const payload = {
        message_id: message.getId(),
        sender: message.getFrom(),
        subject: message.getSubject(),
        body: message.getPlainBody().slice(0, 20000),
        received_at: message.getDate().toISOString(),
      };
      const response = UrlFetchApp.fetch(BOTTLENECK_API, {
        method: "post",
        contentType: "application/json",
        payload: JSON.stringify(payload),
        muteHttpExceptions: true,
      });
      if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) {
        throw new Error(`Bottleneck rejected Gmail message ${message.getId()}: ${response.getContentText()}`);
      }
    });
    thread.addLabel(processed);
    thread.removeLabel(incoming);
  });
}

function getOrCreateLabel_(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}
