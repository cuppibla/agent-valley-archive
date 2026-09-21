"use client";
import { useEffect, useRef, useState } from "react";

/** The Archive, cut open — five levels, and the visitor climbing them.
 *
 * Week three drew a street: a row of faces lighting up left to right, because
 * that week was about a flow running. This week draws a building: floors lighting
 * up bottom to top, because this week is about how far a memory reaches.
 *
 * Nothing on the drawing is a control. Each floor carries one label — what it
 * holds right now, in a few words — and the column beside the tower spells the
 * same thing out in full. You change the picture by editing code, not by
 * clicking it.
 *
 * The night art is the other half of the argument. When the process dies, the
 * lamp on the desk is still burning and the shelves above it are not: the two
 * floors backed by a file survive the night, the one held in memory does not.
 */

export type Card = { id: string; text: string; date: string; kind: string };
export type Floors = {
  desk: { lit: boolean; fields: Record<string, string> };
  f1: { lit: boolean; books: number };
  f2: { lit: boolean; fields: Record<string, string> | null; why?: string | null };
  f3: { lit: boolean; cards: Card[]; store: string; topics: string[] | null; why?: string | null };
  f4: { lit: boolean; locked: boolean };
};
type Key = "desk" | "f1" | "f2" | "f3" | "f4";

// Where each level sits on the art, as a fraction of its height. Measured off
// tower-day.jpg: attic, card racks, drawer cabinet, bookshelves, Vesper's desk.
const AT: Record<Key, number> = { f4: 0.13, f3: 0.335, f2: 0.495, f1: 0.635, desk: 0.805 };

export default function Tower({ floors, level, dark, rising, familiar, name }: {
  floors: Floors | null; level: number; dark: boolean;
  rising: string[] | null; familiar: string; name: string;
}) {
  const [flying, setFlying] = useState<{ t: string; k: number }[]>([]);
  const k = useRef(0);

  // What you said, lifting off the desk at closing time. Before the write policy
  // exists it fades halfway; after it, it lands on floor three. One animation,
  // two meanings — which is the whole of chapter 3.
  useEffect(() => {
    if (!rising?.length) return;
    const batch = rising.map((t) => ({ t, k: k.current++ }));
    setFlying(batch);
    const done = setTimeout(() => setFlying([]), 2400);
    return () => clearTimeout(done);
  }, [rising]);

  const lands = Boolean(floors?.f3.lit) || Boolean(rising?.length && floors?.f3.cards.length);
  const perch = floors?.f3.lit ? AT.f3 : floors?.f2.lit ? AT.f2 : AT.desk;
  const where = floors?.f3.lit ? "floor three" : floors?.f2.lit ? "floor two" : "the desk";
  const lines = Object.keys(floors?.desk.fields ?? {}).length;
  const cards = floors?.f3.cards.length ?? 0;
  const books = floors?.f1.books ?? 0;

  return (
    <div data-shot="tower" style={{ position: "relative", borderRadius: 16, overflow: "hidden",
      border: "1px solid var(--line)", background: "linear-gradient(180deg,#e6dff5,#f7ece8)",
      boxShadow: "0 10px 30px rgba(150,130,200,.18)" }}>
      <img src="/world/w4/tower-day.jpg" alt="The Archive, cut open" width="100%"
        style={{ display: "block", width: "100%", height: "auto" }} />
      <img src="/world/w4/tower-night.jpg" alt="" aria-hidden width="100%"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%",
          objectFit: "cover", opacity: dark ? 1 : 0, transition: "opacity .75s ease" }} />

      <Label at={AT.f4} dark={dark} state={floors?.f4.lit ? "lit" : "locked"}
        text={floors?.f4.lit ? "the season · open" : "the season · locked"} />
      <Label at={AT.f3} dark={dark} state={cards ? "lit" : "empty"}
        text={cards ? `the cards · ${cards}` : "the cards · none"} />
      <Label at={AT.f2} dark={dark} state={floors?.f2.lit ? "lit" : "empty"}
        text={floors?.f2.lit ? `your drawer · ${name}` : "your drawer · empty"} />
      <Label at={AT.f1} dark={dark} survives state={books ? "lit" : "empty"}
        text={`the books · ${books}`} />
      <Label at={AT.desk} dark={dark} survives state={lines ? "lit" : "empty"}
        text={lines ? `the slip · ${lines} line${lines === 1 ? "" : "s"}` : "the slip · blank"} />

      {/* the visitor, perched on the highest floor they have reached */}
      <img src={familiar} alt={name} width={42} height={42}
        style={{ position: "absolute", left: 10, top: `${perch * 100}%`, width: 42, height: 42,
          borderRadius: "50%", objectFit: "cover", border: "3px solid var(--gold)",
          boxShadow: "0 6px 16px rgba(185,138,46,.3)", background: "#fff", zIndex: 2,
          transition: "top 1.1s cubic-bezier(.3,.8,.3,1)" }} />
      <span className="mono" style={{ position: "absolute", left: 54,
        top: `calc(${perch * 100}% + 11px)`, fontSize: 9, color: "var(--gold-deep)",
        background: "rgba(255,255,255,.82)", padding: "3px 8px", borderRadius: 999,
        border: "1px solid var(--gold)", whiteSpace: "nowrap", zIndex: 2,
        transition: "top 1.1s cubic-bezier(.3,.8,.3,1)" }}>
        {name} · {where}
      </span>

      {flying.map((f, i) => (
        <span key={f.k} className="mono"
          style={{ position: "absolute", left: "50%", marginLeft: -90, width: 180,
            textAlign: "center", top: `${AT.desk * 100}%`, fontSize: 10,
            color: "var(--violet)", background: "rgba(255,255,255,.92)", padding: "3px 9px",
            borderRadius: 999, overflow: "hidden", textOverflow: "ellipsis",
            whiteSpace: "nowrap", pointerEvents: "none", zIndex: 3,
            boxShadow: "0 2px 10px rgba(105,85,170,.2)",
            animation: `${lands ? "landOn" : "fadeOff"} 2.2s ${i * 0.18}s cubic-bezier(.3,.7,.4,1) both` }}>
          {f.t}
        </span>
      ))}

      <span className="mono" style={{ position: "absolute", right: 10, bottom: 8, fontSize: 9,
        letterSpacing: ".1em", color: "var(--gold-deep)", background: "rgba(255,255,255,.8)",
        padding: "3px 9px", borderRadius: 999, border: "1px solid var(--gold)" }}>
        {level} / 4 LIT
      </span>

      <style jsx>{`
        @keyframes landOn { 0% { top: ${AT.desk * 100}%; opacity: 0 }
          18% { opacity: 1 } 100% { top: ${AT.f3 * 100 + 3}%; opacity: 0 } }
        @keyframes fadeOff { 0% { top: ${AT.desk * 100}%; opacity: 0 }
          22% { opacity: 1 } 100% { top: ${(AT.desk - 0.16) * 100}%; opacity: 0 } }
      `}</style>
    </div>
  );
}

function Label({ at, text, state, dark, survives }: {
  at: number; text: string; state: "lit" | "empty" | "locked"; dark: boolean; survives?: boolean;
}) {
  const tone = state === "lit" ? "#2f8f73" : state === "empty" ? "var(--violet)" : "var(--faint)";
  // The desk and the books are in a file. The night does not touch them.
  const out = dark && !survives;
  return (
    <span style={{ position: "absolute", right: 8, top: `${at * 100 - 1.5}%`,
      display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 10px",
      borderRadius: 999, background: "rgba(255,255,255,.84)", backdropFilter: "blur(6px)",
      zIndex: 2, boxShadow: "0 1px 4px rgba(90,70,150,.14)",
      opacity: out ? 0.12 : 1, transition: "opacity .6s" }}>
      <i style={{ width: 7, height: 7, borderRadius: "50%", display: "inline-block",
        background: state === "lit" ? "var(--mint)" : "transparent",
        border: state === "lit" ? "none" : `1.5px ${state === "empty" ? "dashed" : "solid"} ${tone}` }} />
      <span className="mono" style={{ fontSize: 9.5, color: "var(--sub)", whiteSpace: "nowrap" }}>{text}</span>
    </span>
  );
}
