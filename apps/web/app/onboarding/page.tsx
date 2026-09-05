import { OnboardingPanel } from "../../components/OnboardingPanel";

export const dynamic = "force-dynamic";

export default function OnboardingPage() {
  return (
    <main>
      <h1>Get started (15 min)</h1>
      <p>
        Connect a repo + Sentry, or hit <strong>Load demo data</strong> to walk the
        full loop — inbox → clusters → investigation → draft fix — right now.
      </p>
      <OnboardingPanel />
    </main>
  );
}
