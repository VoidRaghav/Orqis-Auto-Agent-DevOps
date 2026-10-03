"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createSubscription,
  fetchPlans,
  fetchSubscription,
  verifySubscription,
  type Plan,
  type SubscriptionInfo,
} from "@/lib/api";
import { loadRazorpay } from "@/lib/razorpay";
import { Card, Hint, Row, settingsColors } from "./SettingsUi";

// Indian customers default to rupees; everyone else to dollars. The toggle lets
// the user switch, but the amount is always the server's converted price.
function detectCurrency(): string {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    if (tz.includes("Kolkata") || tz.includes("Calcutta")) return "INR";
  } catch {
    // fall through to USD
  }
  return "USD";
}

export default function SettingsBillingCard({ adminToken = "" }: { adminToken?: string }) {
  const [currency, setCurrency] = useState(detectCurrency());
  const [plans, setPlans] = useState<Plan[]>([]);
  const [sub, setSub] = useState<SubscriptionInfo | null>(null);
  const [busy, setBusy] = useState<string | null>(null); // plan id in flight
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const loadSub = useCallback(async () => {
    try {
      setSub(await fetchSubscription(adminToken));
    } catch {
      // backend unreachable — leave default state
    }
  }, [adminToken]);

  const loadPlans = useCallback(async () => {
    try {
      setPlans(await fetchPlans(currency, adminToken));
    } catch {
      setPlans([]);
    }
  }, [currency, adminToken]);

  useEffect(() => {
    loadSub();
  }, [loadSub]);
  useEffect(() => {
    loadPlans();
  }, [loadPlans]);

  async function subscribe(plan: Plan) {
    setMsg(null);
    setBusy(plan.id);
    try {
      const ready = await loadRazorpay();
      if (!ready || !window.Razorpay) {
        setMsg({ kind: "err", text: "Could not load Razorpay checkout." });
        return;
      }
      const { subscription_id, key_id } = await createSubscription(plan.id, currency, adminToken);
      const rzp = new window.Razorpay({
        key: key_id,
        subscription_id,
        name: "Orqis",
        description: `${plan.name} — ${plan.display}/mo`,
        theme: { color: "#00c48c" },
        handler: async (resp) => {
          try {
            await verifySubscription(
              {
                razorpay_payment_id: resp.razorpay_payment_id,
                razorpay_subscription_id: resp.razorpay_subscription_id,
                razorpay_signature: resp.razorpay_signature,
              },
              adminToken,
            );
            setMsg({ kind: "ok", text: `${plan.name} active — thank you.` });
            await loadSub();
          } catch (e) {
            setMsg({ kind: "err", text: `Payment could not be verified: ${String(e)}` });
          }
        },
        modal: { ondismiss: () => setMsg({ kind: "err", text: "Checkout cancelled." }) },
      });
      rzp.on("payment.failed", (r) =>
        setMsg({ kind: "err", text: r.error?.description || "Payment failed." }),
      );
      rzp.open();
    } catch (e) {
      setMsg({ kind: "err", text: String(e) });
    } finally {
      setBusy(null);
    }
  }

  const active = sub?.status === "active";

  return (
    <Card title="Billing" accent={settingsColors.green}>
      {active ? (
        <>
          <Row label="Status" value="Active" tone={settingsColors.green} />
          {sub?.plan && (
            <Row
              label="Plan"
              value={`${sub.plan}${sub.display ? ` · ${sub.display}/mo` : ""}`}
            />
          )}
          {sub?.subscription_id && <Row label="Subscription" value={sub.subscription_id} mono />}
          <Hint>Subscription active for this workspace. Manage or cancel from Razorpay.</Hint>
        </>
      ) : (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Hint>Choose a plan — billed monthly (test mode).</Hint>
            <div style={{ display: "flex", gap: 4 }}>
              {["USD", "INR"].map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCurrency(c)}
                  className="settings-btn settings-btn-ghost"
                  style={{ opacity: currency === c ? 1 : 0.45, fontWeight: currency === c ? 700 : 400 }}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10 }}>
            {plans.map((plan) => (
              <div
                key={plan.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 12px",
                  border: `1px solid ${settingsColors.border}`,
                  borderRadius: 8,
                }}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>{plan.name}</div>
                  <div style={{ color: settingsColors.dim, fontSize: 13 }}>{plan.display}/mo</div>
                </div>
                <button
                  type="button"
                  onClick={() => subscribe(plan)}
                  disabled={busy !== null}
                  className="settings-btn settings-btn-github"
                >
                  {busy === plan.id ? "Opening…" : "Subscribe"}
                </button>
              </div>
            ))}
          </div>
        </>
      )}
      {msg && <Hint tone={msg.kind === "err" ? "warn" : undefined}>{msg.text}</Hint>}
    </Card>
  );
}
