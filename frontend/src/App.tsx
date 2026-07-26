import { useEffect, useState } from "react";

import { SignIn } from "./SignIn";
import { UNAUTHORIZED_EVENT } from "./lib/apiClient";
import { getStoredApiKey } from "./lib/apiKey";
import { WorkspaceShell } from "./workspace/WorkspaceShell";

/**
 * The auth gate (issue 02, user story 52; reduced to just this by the
 * frontend-rework's workspace-shell slice). Everything the app actually
 * does — the three-pane workspace, the single Report Spec store, the
 * builder/report/Assistant panes — lives in `workspace/WorkspaceShell.tsx`
 * and what it composes; this component's only job is deciding whether the
 * user has a key.
 *
 * Auth failure handling: on a 401 from any `apiFetch` call, `apiClient`
 * clears the stored key and fires `UNAUTHORIZED_EVENT`; the listener below
 * drops back to the sign-in screen. Nothing here touches the URL, so
 * whatever report definition lives in the query string (issue 13) survives
 * the round trip through sign-in (user story 53).
 */
export function App() {
  const [signedIn, setSignedIn] = useState<boolean>(() => getStoredApiKey() !== null);

  useEffect(() => {
    function handleUnauthorized() {
      setSignedIn(false);
    }
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  if (!signedIn) {
    return <SignIn onSignedIn={() => setSignedIn(true)} />;
  }

  return <WorkspaceShell />;
}
