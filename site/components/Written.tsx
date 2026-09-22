"use client";
import type { Card, Floors } from "@/components/Tower";

/** What is written, floor by floor — the tower's labels, spelled out.
 *
 * Read-only on purpose. This column is the same four stores the codelab's
 * table names, in the same order the drawing stacks them, and every line in it
 * is the service reading the code you just saved. There is nothing to press.
 */
export default function Written({ floors, name }: { floors: Floors | null; name: string }) {
  const slip = floors?.desk.fields ?? {};
  const drawer = floors?.f2.fields ?? null;
  const cards: Card[] = floors?.f3.cards ?? [];
  const store = floors?.f3.store ?? "in this process";
  const topics = floors?.f3.topics ?? null;
  const open = Boolean(floors?.f4.lit);

  return (
    <div data-shot="written" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <Block label="the slip · the desk · this visit">
        {Object.keys(slip).length ? <Fields of={slip} /> : <Empty>blank — nothing written yet</Empty>}
      </Block>

      <Block label="your drawer · floor two · this visitor">
        {drawer && Object.keys(drawer).length
          ? <><div style={{ fontSize: 12, color: "var(--sub)", marginBottom: 4 }}>{name}</div><Fields of={drawer} /></>
          : <Empty>{floors?.f2.why ?? "nothing written down yet"}</Empty>}
      </Block>

      <Block label="the cards · floor three · what was said" shot="cards">
        {cards.length
          ? <>
              <div className="mono" style={{ fontSize: 10, color: "var(--faint)", marginBottom: 5 }}>
                {cards.length} card{cards.length === 1 ? "" : "s"} · {store}
                {store === "Memory Bank" && topics?.length
                  ? ` · filtered to ${topics.join(", ").toLowerCase()}` : ""}
              </div>
              {cards.slice(0, 8).map((c) => (
                <div key={c.id} style={{ padding: "4px 0", borderBottom: "1px dotted var(--line)",
                  fontSize: 12.5, color: "var(--sub)", lineHeight: 1.45 }}>
                  {c.text.length > 220 ? c.text.slice(0, 220) + "…" : c.text}
                  <em className="mono" style={{ display: "block", fontSize: 9.5, fontStyle: "normal",
                    color: "var(--violet)" }}>{c.kind}{c.date ? ` · ${c.date}` : ""}</em>
                </div>))}
              {cards.length > 8 && <div className="mono" style={{ fontSize: 10, color: "var(--faint)",
                marginTop: 4 }}>+ {cards.length - 8} more</div>}
            </>
          : <Empty>{floors?.f3.why ?? "nothing filed yet"}</Empty>}
      </Block>

      <Block label="the season · floor four · the whole valley">
        {open
          ? <div style={{ fontSize: 12.5, color: "var(--sub)", lineHeight: 1.5 }}>
              open — ask her <span className="mono" style={{ color: "var(--violet)" }}>
              [season] has anyone else had a q7 lantern go out at night?</span></div>
          : <Empty>locked — bash scripts/season.sh</Empty>}
      </Block>
    </div>
  );
}

function Block({ label, shot, children }: { label: string; shot?: string; children: React.ReactNode }) {
  return (
    <div data-shot={shot} style={{ background: "#fffdf8", border: "1px solid var(--line)",
      borderRadius: 12, padding: "10px 13px 11px" }}>
      <div className="mono" style={{ fontSize: 9.5, letterSpacing: ".14em", textTransform: "uppercase",
        color: "var(--faint)", marginBottom: 6 }}>{label}</div>
      {children}
    </div>
  );
}

function Fields({ of }: { of: Record<string, string> }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "72px 1fr", gap: "2px 8px", fontSize: 12.5 }}>
      {Object.entries(of).map(([k, v]) => (
        <FieldRow key={k} k={k} v={String(v)} />))}
    </div>
  );
}
function FieldRow({ k, v }: { k: string; v: string }) {
  return (
    <>
      <span className="mono" style={{ fontSize: 10.5, color: "var(--faint)", paddingTop: 2 }}>{k}</span>
      <span style={{ color: "var(--ink)", lineHeight: 1.45 }}>{v}</span>
    </>
  );
}
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 12, color: "var(--faint)", fontStyle: "italic", lineHeight: 1.45 }}>{children}</div>
  );
}
