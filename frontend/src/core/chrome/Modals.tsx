"use client";

import { DrawingViewer } from "@/components/DrawingViewer";
import { ConnectGoogleModal } from "@/components/orchestrator/ConnectGoogleModal";
import { DraftComposeModal } from "@/components/orchestrator/DraftComposeModal";
import { HitlModal } from "@/components/orchestrator/HitlModal";
import { PreferencesPanel } from "@/components/orchestrator/PreferencesPanel";
import * as desk from "@/core/desk/controller";
import { useTurnView } from "@/core/desk/useTurnView";
import { setDesk, useDesk } from "@/core/stores/deskStore";
import { conversationToAttachment } from "@/lib/viewerMatch";

/** Modal tier: HITL, compose, prefs, Google connect and the chat drawing viewer. Never scrolls the page. */
export function Modals() {
  const { hitlAction, composeDraft, confirmListening, busy } = useTurnView();
  const googleStatus = useDesk((s) => s.googleStatus);
  const googleConnectOpen = useDesk((s) => s.googleConnectOpen);
  const prefsOpen = useDesk((s) => s.prefsOpen);
  const prefs = useDesk((s) => s.prefs);
  const drawingChat = useDesk((s) => s.drawingChat);
  const drawingAttachment =
    drawingChat?.open === false
      ? null
      : conversationToAttachment({
          filename: drawingChat?.filename,
          local_name: drawingChat?.local_name,
          local_path: drawingChat?.local_path,
          mime: drawingChat?.mime,
        });

  return (
    <div className="pointer-events-none fixed inset-0 z-modal" data-lenis-prevent data-layer="modal">
      <HitlModal
        action={hitlAction}
        visible={Boolean(hitlAction)}
        listening={confirmListening}
        busy={busy}
        onDecide={(id, approved) => void desk.decide(id, approved)}
      />

      <ConnectGoogleModal
        status={googleStatus}
        visible={googleConnectOpen}
        onLater={() => setDesk({ googleConnectOpen: false })}
        onOpenPreferences={() => setDesk({ googleConnectOpen: false, prefsOpen: true })}
        onPromptInteract={() => {
          if (googleStatus) desk.announceGoogleConnect(googleStatus);
        }}
      />

      <PreferencesPanel
        open={prefsOpen}
        prefs={prefs}
        onClose={() => setDesk({ prefsOpen: false })}
        onSave={desk.savePreferences}
      />

      <DraftComposeModal
        action={composeDraft}
        visible={Boolean(composeDraft)}
        listening={confirmListening}
        busy={busy}
        onFieldsChange={desk.setComposeFields}
        onDecide={(id, approved, fields) => void desk.decide(id, approved, fields)}
      />

      {drawingAttachment && drawingChat ? (
        <div className="pointer-events-auto">
          <DrawingViewer
            chatMode
            notes={drawingChat.notes || ""}
            attachment={drawingAttachment}
            onClose={desk.closeDrawing}
            onWhisper={(line) => desk.showVoice(line)}
          />
        </div>
      ) : null}
    </div>
  );
}
